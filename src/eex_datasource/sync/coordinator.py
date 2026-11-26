"""High-level, restart-safe synchronization workflows."""

from __future__ import annotations

import hashlib
import json
import logging
import socket
import uuid
from collections.abc import Callable, Iterable
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, sessionmaker

from ..api.auctions import AuctionsAPI
from ..api.derivatives import DerivativesAPI
from ..api.gas_spot import GasSpotAPI
from ..api.indices import IndicesAPI
from ..api.transparency import TransparencyAPI
from ..client import EEXClient
from ..errors import EEXNotFoundError, EEXTruncationError
from ..progress import progress
from ..storage.archive import Archive
from ..storage.cache import CachedTransport
from ..storage.models import ApiFetch, SyncLease, SyncRun, SyncState
from ..storage.repositories import DataRepository

logger = logging.getLogger(__name__)

ROW_LIMIT = 60_000


class Synchronizer:
    """Run paced, cached imports while recording run status and watermarks.

    Jobs return their run ID. Imports are idempotent, acquire a database lease,
    and fail rather than accepting potentially truncated leaf responses.
    Request shapes follow the EEX OpenAPI snapshots in ``specs/``.
    """

    def __init__(
        self,
        client: EEXClient,
        sessions: sessionmaker[Session],
        archive: Archive,
        *,
        cache_ttl: timedelta = timedelta(hours=1),
        force: bool = False,
    ) -> None:
        self.client = client
        self.sessions = sessions
        self.archive = archive
        self.cache_ttl = cache_ttl
        self.force = force

    def market(
        self,
        market: str,
        commodity: str,
        area: str,
        date_from: date,
        date_to: date,
    ) -> str:
        """Import daily market resources for available dates in an inclusive range."""
        if market not in {"derivatives", "gas_spot"}:
            raise ValueError("market must be derivatives or gas_spot")
        parameters = {
            "market": market,
            "commodity": commodity,
            "area": area,
            "from": date_from.isoformat(),
            "to": date_to.isoformat(),
        }

        def work(session: Session, run: SyncRun) -> int:
            transport = self._transport(session, run.id)
            api: DerivativesAPI | GasSpotAPI
            api = (
                DerivativesAPI(transport)
                if market == "derivatives"
                else GasSpotAPI(transport)
            )
            repository = DataRepository(session)
            count = 0
            available_dates = set(api.trade_dates(commodity, area))
            dates = [
                item
                for item in _dates(date_from, date_to)
                if item.isoformat() in available_dates
            ]
            logger.info(
                "Discovered %d valid %s business dates in requested range",
                len(dates),
                market,
            )
            for business_date in progress(dates, desc=f"{market} {commodity}/{area}"):
                try:
                    count += self._market_day(
                        api,
                        repository,
                        transport,
                        market,
                        commodity,
                        area,
                        business_date.isoformat(),
                    )
                except EEXNotFoundError:
                    logger.info(
                        "No %s data for %s/%s on %s",
                        market,
                        commodity,
                        area,
                        business_date,
                    )
                self._save_state(
                    session,
                    f"market:{market}",
                    {
                        "commodity": commodity,
                        "area": area,
                    },
                    business_date.isoformat(),
                    run.id,
                )
            return count

        return self._run(f"sync-{market}", parameters, work)

    def _market_day(
        self,
        api: DerivativesAPI | GasSpotAPI,
        repository: DataRepository,
        transport: CachedTransport,
        market: str,
        commodity: str,
        area: str,
        business_date: str,
    ) -> int:
        count = 0
        methods = {
            "reference": api.reference_data,
            "trades": api.trades,
            "top_of_book": api.top_of_book,
            "statistics": api.statistics,
            "settlements": api.settlements,
        }
        for resource, method in methods.items():
            if market == "gas_spot" and resource == "top_of_book":
                # The API has no area-wide spot TOB route. Store each response
                # separately so its rows retain the correct fetch provenance.
                for shortcode in api.shortcodes(commodity, area, business_date):
                    try:
                        records = method(commodity, area, business_date, shortcode)
                    except EEXNotFoundError:
                        continue
                    if len(records) >= ROW_LIMIT:
                        raise EEXTruncationError(
                            f"top_of_book shortcode response reached "
                            f"{ROW_LIMIT}: {shortcode}"
                        )
                    count += repository.store_market(
                        market, resource, records, transport.last_fetch_id
                    )
                continue
            try:
                records = method(commodity, area, business_date, limit=ROW_LIMIT)
            except EEXNotFoundError:
                logger.debug("No %s records on %s", resource, business_date)
                continue
            if len(records) < ROW_LIMIT:
                count += repository.store_market(
                    market, resource, records, transport.last_fetch_id
                )
                continue
            logger.warning(
                "%s response reached %d rows; partitioning by shortcode",
                resource,
                ROW_LIMIT,
            )
            shortcodes = api.shortcodes(commodity, area, business_date)
            for shortcode in shortcodes:
                subset = method(
                    commodity,
                    area,
                    business_date,
                    shortcode,
                    limit=ROW_LIMIT,
                )
                if (
                    len(subset) >= ROW_LIMIT
                    and market == "derivatives"
                    and resource != "top_of_book"
                ):
                    maturities = api.maturities(
                        commodity, area, business_date, shortcode
                    )
                    for maturity in maturities:
                        leaf = method(
                            commodity,
                            area,
                            business_date,
                            shortcode,
                            maturity,
                            limit=ROW_LIMIT,
                        )
                        if len(leaf) >= ROW_LIMIT:
                            raise EEXTruncationError(
                                f"{resource} leaf still reached {ROW_LIMIT}: "
                                f"{commodity}/{area}/{business_date}/"
                                f"{shortcode}/{maturity}"
                            )
                        count += repository.store_market(
                            market,
                            resource,
                            leaf,
                            transport.last_fetch_id,
                        )
                else:
                    if len(subset) >= ROW_LIMIT:
                        raise EEXTruncationError(
                            f"{resource} shortcode response still reached "
                            f"{ROW_LIMIT}: {shortcode}"
                        )
                    count += repository.store_market(
                        market,
                        resource,
                        subset,
                        transport.last_fetch_id,
                    )
        return count

    def auctions(
        self,
        commodity: str,
        area: str,
        date_from: date,
        date_to: date,
    ) -> str:
        """Import auction reference records, results, and revenues by date."""
        parameters = {
            "commodity": commodity,
            "area": area,
            "from": date_from.isoformat(),
            "to": date_to.isoformat(),
        }

        def work(session: Session, run: SyncRun) -> int:
            transport = self._transport(session, run.id)
            api = AuctionsAPI(transport)
            repository = DataRepository(session)
            count = 0
            available_dates = set(api.auction_dates(commodity, area))
            for auction_date in progress(
                [
                    item
                    for item in _dates(date_from, date_to)
                    if item.isoformat() in available_dates
                ],
                desc="auctions",
            ):
                day = auction_date.isoformat()
                for resource, method in (
                    ("reference", api.reference_data),
                    ("results", api.results),
                    ("revenues", api.revenues),
                ):
                    try:
                        records = method(commodity, area, day, limit=ROW_LIMIT)
                    except EEXNotFoundError:
                        continue
                    if len(records) >= ROW_LIMIT:
                        raise EEXTruncationError(
                            f"auction {resource} reached {ROW_LIMIT} rows"
                        )
                    count += repository.store_auctions(
                        resource, records, transport.last_fetch_id
                    )
                self._save_state(
                    session,
                    "auctions",
                    {"commodity": commodity, "area": area},
                    day,
                    run.id,
                )
            return count

        return self._run("sync-auctions", parameters, work)

    def top_of_book_history(
        self,
        market: str,
        commodity: str,
        area: str,
        trade_date: date,
        time_from: time,
        time_to: time,
        *,
        shortcode: str | None = None,
        maturity: str | int | None = None,
        symbol: str | None = None,
    ) -> str:
        """Store every top-of-book change in a bounded intraday interval."""

        if time_to <= time_from:
            raise ValueError("time-to must be later than time-from")
        parameters = {
            "market": market,
            "commodity": commodity,
            "area": area,
            "trade_date": trade_date.isoformat(),
            "time_from": time_from.isoformat(),
            "time_to": time_to.isoformat(),
            "shortcode": shortcode,
            "maturity": maturity,
            "symbol": symbol,
        }

        def work(session: Session, run: SyncRun) -> int:
            transport = self._transport(session, run.id)
            repository = DataRepository(session)
            start = datetime.combine(trade_date, time_from)
            end = datetime.combine(trade_date, time_to)
            count = 0
            if market == "derivatives":
                api = DerivativesAPI(transport)
                fetch = lambda left, right: api.top_of_book_history(
                    commodity,
                    area,
                    trade_date.isoformat(),
                    time_from=left.time().isoformat(),
                    time_to=right.time().isoformat(),
                    shortcode=shortcode,
                    maturity=maturity,
                    symbol=symbol,
                    limit=ROW_LIMIT,
                )
            elif market == "gas_spot":
                if shortcode is None:
                    raise ValueError("gas spot book history requires shortcode")
                spot_api = GasSpotAPI(transport)
                fetch = lambda left, right: spot_api.top_of_book_history(
                    commodity,
                    area,
                    trade_date.isoformat(),
                    shortcode,
                    time_from=left.time().isoformat(),
                    time_to=right.time().isoformat(),
                    limit=ROW_LIMIT,
                )
            else:
                raise ValueError("market must be derivatives or gas_spot")

            # Hourly windows stay comfortably below the API cap in ordinary
            # markets and produce useful restart/cache boundaries.
            for left, right in _time_windows(start, end, timedelta(hours=1)):
                records = fetch(left, right)
                if len(records) >= ROW_LIMIT:
                    raise EEXTruncationError(
                        "hourly top-of-book window reached the row limit; "
                        "request a smaller interval"
                    )
                count += repository.store_market(
                    market,
                    "top_of_book",
                    records,
                    transport.last_fetch_id,
                )
                self._save_state(
                    session,
                    f"top-of-book:{market}",
                    {
                        "commodity": commodity,
                        "area": area,
                        "shortcode": shortcode,
                        "maturity": maturity,
                        "symbol": symbol,
                    },
                    right.isoformat(),
                    run.id,
                )
            return count

        return self._run("sync-top-of-book", parameters, work)

    def indices(
        self,
        date_from: date,
        date_to: date,
        *,
        commodity: str | None = None,
        area: str | None = None,
        index: str | None = None,
    ) -> str:
        """Import index observations, discovering any omitted scope components."""
        parameters = {
            "commodity": commodity,
            "area": area,
            "index": index,
            "from": date_from.isoformat(),
            "to": date_to.isoformat(),
        }

        def work(session: Session, run: SyncRun) -> int:
            transport = self._transport(session, run.id)
            api = IndicesAPI(transport)
            repository = DataRepository(session)
            count = 0
            commodities = [commodity] if commodity else api.commodities()
            for cmdty in commodities:
                areas = [area] if area else api.areas(cmdty)
                for market_area in areas:
                    indexes = [index] if index else api.indexes(cmdty, market_area)
                    for code in indexes:
                        records = api.series(
                            cmdty,
                            market_area,
                            code,
                            date_from=date_from.isoformat(),
                            date_to=date_to.isoformat(),
                            limit=ROW_LIMIT,
                        )
                        if len(records) >= ROW_LIMIT:
                            for day in _dates(date_from, date_to):
                                daily = api.day(
                                    cmdty,
                                    market_area,
                                    code,
                                    day.isoformat(),
                                    limit=ROW_LIMIT,
                                )
                                if len(daily) >= ROW_LIMIT:
                                    raise EEXTruncationError(
                                        f"index {code} reached {ROW_LIMIT} "
                                        f"rows on {day}"
                                    )
                                count += repository.store_indices(
                                    daily, transport.last_fetch_id
                                )
                        else:
                            count += repository.store_indices(
                                records, transport.last_fetch_id
                            )
                        self._save_state(
                            session,
                            "indices",
                            {
                                "commodity": cmdty,
                                "area": market_area,
                                "index": code,
                            },
                            date_to.isoformat(),
                            run.id,
                        )
            return count

        return self._run("sync-indices", parameters, work)

    def transparency_reference(
        self, commodity: str, area: str, validity_date: date
    ) -> str:
        """Import an asset reference tree and snapshots for one validity date."""
        parameters = {
            "commodity": commodity,
            "area": area,
            "validity_date": validity_date.isoformat(),
        }

        def work(session: Session, run: SyncRun) -> int:
            transport = self._transport(session, run.id)
            records = TransparencyAPI(transport).reference_tree(
                commodity, area, validity_date.isoformat()
            )
            if len(records) >= ROW_LIMIT:
                raise EEXTruncationError(
                    "transparency reference tree reached row limit"
                )
            count = DataRepository(session).store_transparency_reference(
                records,
                transport.last_fetch_id,
                validity_date=validity_date,
            )
            self._save_state(
                session,
                "transparency-reference",
                {"commodity": commodity, "area": area},
                validity_date.isoformat(),
                run.id,
            )
            return count

        return self._run("sync-transparency-reference", parameters, work)

    def transparency_umms(
        self,
        commodity: str,
        modified_from: datetime,
        modified_to: datetime,
        *,
        area: str | None = None,
        facility_type: str | None = None,
        adhoc: bool = False,
    ) -> str:
        """Import UMM/ad-hoc revisions in bounded modification-time windows."""
        parameters = {
            "commodity": commodity,
            "area": area,
            "facility_type": facility_type,
            "modified_from": modified_from.isoformat(),
            "modified_to": modified_to.isoformat(),
            "adhoc": adhoc,
        }

        def work(session: Session, run: SyncRun) -> int:
            transport = self._transport(session, run.id)
            api = TransparencyAPI(transport)
            repository = DataRepository(session)
            count = 0
            for start, end in _time_windows(
                modified_from, modified_to, timedelta(days=1)
            ):
                if adhoc:
                    records = api.adhoc_updates(
                        _iso_z(start),
                        modified_to=_iso_z(end),
                        limit=ROW_LIMIT,
                    )
                else:
                    records = api.umm_updates(
                        commodity,
                        _iso_z(start),
                        area=area,
                        facility_type=facility_type,
                        modified_to=_iso_z(end),
                        limit=ROW_LIMIT,
                    )
                if len(records) >= ROW_LIMIT:
                    raise EEXTruncationError(
                        "UMM daily window reached the row limit; use a "
                        "smaller explicit interval"
                    )
                count += repository.store_umms(
                    records,
                    transport.last_fetch_id,
                    kind="adhoc" if adhoc else "umm",
                )
                self._save_state(
                    session,
                    "transparency-umm",
                    {
                        "commodity": commodity,
                        "area": area,
                        "facility_type": facility_type,
                        "adhoc": adhoc,
                    },
                    _iso_z(end),
                    run.id,
                )
            return count

        return self._run("sync-transparency-umm", parameters, work)

    def transparency_series(
        self,
        commodity: str,
        area: str,
        symbol: str,
        date_from: datetime,
        date_to: datetime,
        *,
        eurowind: bool = False,
        filters: dict[str, Any] | None = None,
    ) -> str:
        """Import versioned transparency/EuroWind points in weekly windows."""
        parameters = {
            "commodity": commodity,
            "area": area,
            "symbol": symbol,
            "from": date_from.isoformat(),
            "to": date_to.isoformat(),
            "eurowind": eurowind,
            "filters": filters or {},
        }

        def work(session: Session, run: SyncRun) -> int:
            transport = self._transport(session, run.id)
            api = TransparencyAPI(transport)
            repository = DataRepository(session)
            count = 0
            for start, end in _time_windows(date_from, date_to, timedelta(days=7)):
                records = api.time_series(
                    commodity,
                    area,
                    symbol,
                    _iso_z(start),
                    date_to=_iso_z(end),
                    eurowind=eurowind,
                    limit=ROW_LIMIT,
                    **(filters or {}),
                )
                point_count = sum(len(record.get("series", [])) for record in records)
                if len(records) >= ROW_LIMIT or point_count >= ROW_LIMIT:
                    raise EEXTruncationError(
                        "transparency series window reached row limit"
                    )
                count += repository.store_series(
                    records,
                    transport.last_fetch_id,
                    source="eurowind" if eurowind else "transparency",
                )
                self._save_state(
                    session,
                    "transparency-series",
                    {
                        "commodity": commodity,
                        "area": area,
                        "symbol": symbol,
                        "eurowind": eurowind,
                        "filters": filters or {},
                    },
                    _iso_z(end),
                    run.id,
                )
            return count

        return self._run("sync-transparency-series", parameters, work)

    def _transport(self, session: Session, run_id: str) -> CachedTransport:
        return CachedTransport(
            self.client,
            session,
            self.archive,
            run_id=run_id,
            ttl=self.cache_ttl,
            force=self.force,
        )

    def _run(
        self,
        job: str,
        parameters: dict[str, Any],
        work: Callable[[Session, SyncRun], int],
    ) -> str:
        run_id = str(uuid.uuid4())
        with self.sessions() as session:
            self._acquire_lease(session)
            run = SyncRun(
                id=run_id,
                job=job,
                parameters=parameters,
                status="running",
                started_at=datetime.now(UTC),
                finished_at=None,
                fetched_count=0,
                record_count=0,
                error=None,
            )
            session.add(run)
            session.commit()
            try:
                run.record_count = work(session, run)
                run.fetched_count = (
                    session.scalar(
                        select(func.count())
                        .select_from(ApiFetch)
                        .where(ApiFetch.run_id == run.id)
                    )
                    or 0
                )
                run.status = "succeeded"
                logger.info("%s completed: %d new records", job, run.record_count)
            except Exception as exc:
                session.rollback()
                run = session.get(SyncRun, run_id)
                assert run is not None
                run.status = "failed"
                run.error = str(exc)
                logger.exception("%s failed", job)
                raise
            finally:
                run.finished_at = datetime.now(UTC)
                session.execute(
                    delete(SyncLease).where(SyncLease.lease_key == "eex-api-user")
                )
                session.commit()
        return run_id

    @staticmethod
    def _acquire_lease(session: Session) -> None:
        now = datetime.now(UTC)
        session.execute(
            delete(SyncLease).where(
                SyncLease.lease_key == "eex-api-user",
                SyncLease.expires_at < now,
            )
        )
        existing = session.get(SyncLease, "eex-api-user")
        if existing is not None:
            raise RuntimeError(
                f"Another sync process holds the EEX lease: {existing.owner}"
            )
        session.add(
            SyncLease(
                lease_key="eex-api-user",
                owner=f"{socket.gethostname()}:{uuid.uuid4()}",
                acquired_at=now,
                expires_at=now + timedelta(days=7),
            )
        )
        session.commit()

    @staticmethod
    def _save_state(
        session: Session,
        job: str,
        scope: dict[str, Any],
        watermark: str,
        run_id: str,
    ) -> None:
        encoded = json.dumps(scope, sort_keys=True, separators=(",", ":"))
        key = hashlib.sha256(f"{job}:{encoded}".encode()).hexdigest()
        state = session.get(SyncState, key)
        if state is None:
            state = SyncState(
                state_key=key,
                job=job,
                scope=scope,
                watermark=watermark,
                updated_at=datetime.now(UTC),
                last_run_id=run_id,
            )
            session.add(state)
        else:
            state.watermark = watermark
            state.updated_at = datetime.now(UTC)
            state.last_run_id = run_id
        session.commit()


def _dates(start: date, end: date) -> Iterable[date]:
    if end < start:
        raise ValueError("end date must not be before start date")
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def _time_windows(
    start: datetime, end: datetime, size: timedelta
) -> Iterable[tuple[datetime, datetime]]:
    if end < start:
        raise ValueError("end timestamp must not be before start timestamp")
    current = start
    while current < end:
        boundary = min(end, current + size)
        yield current, boundary
        current = boundary


def _iso_z(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
