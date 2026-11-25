"""Normalization and idempotent persistence of EEX response records."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import (
    Auction,
    AuctionResult,
    AuctionRevenue,
    IndexDefinition,
    IndexObservation,
    InstrumentSnapshot,
    MarketInstrument,
    MarketStatistic,
    MarketTrade,
    Settlement,
    TopOfBook,
    TransparencyCapacity,
    TransparencyCompany,
    TransparencyFacility,
    TransparencyReferenceSnapshot,
    TransparencySeries,
    TransparencySeriesPoint,
    TransparencyUnit,
    UmmCapacityInterval,
    UmmRevision,
    UmmThread,
)


def record_hash(record: Any) -> str:
    encoded = json.dumps(
        record,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def stable_key(*values: Any) -> str:
    return hashlib.sha256(
        "|".join("" if value is None else str(value) for value in values).encode()
    ).hexdigest()


def as_date(value: Any) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    return date.fromisoformat(str(value)[:10])


def as_datetime(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).replace("Z", "+00:00")
    return datetime.fromisoformat(text)


def as_decimal(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _id() -> str:
    return str(uuid.uuid4())


class DataRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def store_market(
        self,
        market: str,
        resource: str,
        records: list[dict[str, Any]],
        source_fetch_id: str | None,
    ) -> int:
        handlers = {
            "reference": self._instruments,
            "trades": self._trades,
            "top_of_book": self._top_of_book,
            "statistics": self._statistics,
            "settlements": self._settlements,
        }
        count = handlers[resource](market, records, source_fetch_id)
        self.session.commit()
        return count

    def _instruments(
        self,
        market: str,
        records: list[dict[str, Any]],
        source_fetch_id: str | None,
    ) -> int:
        inserted = 0
        now = datetime.now(UTC)
        for item in records:
            key = stable_key(
                market,
                item.get("InstrumentISIN"),
                item.get("Cmdty"),
                item.get("Area"),
                item.get("ShortCode"),
                item.get("Maturity") or item.get("DeliveryDay"),
                item.get("StrikePx"),
                item.get("OptionType"),
            )
            instrument = self.session.scalar(
                select(MarketInstrument).where(MarketInstrument.instrument_key == key)
            )
            if instrument is None:
                instrument = MarketInstrument(
                    id=_id(),
                    instrument_key=key,
                    market=market,
                    instrument_isin=item.get("InstrumentISIN"),
                    product_isin=item.get("ProductISIN"),
                    commodity=item.get("Cmdty"),
                    area=item.get("Area"),
                    shortcode=item.get("ShortCode"),
                    maturity=str(item.get("Maturity") or item.get("DeliveryDay") or "")
                    or None,
                    long_name=item.get("LongName"),
                    first_seen_at=now,
                    last_seen_at=now,
                    payload=item,
                )
                self.session.add(instrument)
            else:
                instrument.last_seen_at = now
                instrument.payload = item
            business_date = as_date(item.get("TrdDate"))
            if business_date is None:
                continue
            digest = record_hash(item)
            exists = self.session.scalar(
                select(InstrumentSnapshot.id).where(
                    InstrumentSnapshot.instrument_id == instrument.id,
                    InstrumentSnapshot.business_date == business_date,
                    InstrumentSnapshot.record_hash == digest,
                )
            )
            if exists is None:
                self.session.add(
                    InstrumentSnapshot(
                        id=_id(),
                        instrument_id=instrument.id,
                        business_date=business_date,
                        record_hash=digest,
                        source_fetch_id=source_fetch_id,
                        observed_at=now,
                        payload=item,
                    )
                )
                inserted += 1
        return inserted

    def _trades(
        self,
        market: str,
        records: list[dict[str, Any]],
        source_fetch_id: str | None,
    ) -> int:
        inserted = 0
        for item in records:
            digest = record_hash(item)
            exists = self.session.scalar(
                select(MarketTrade.id).where(
                    MarketTrade.market == market,
                    MarketTrade.record_hash == digest,
                )
            )
            if exists is not None:
                continue
            source_key = "|".join(
                str(item.get(key, ""))
                for key in (
                    "TrdDate",
                    "ShortCode",
                    "Maturity",
                    "TrdType",
                    "TrdID",
                    "GroupID",
                    "TrdVersion",
                )
            )
            self.session.add(
                MarketTrade(
                    id=_id(),
                    market=market,
                    source_key=source_key,
                    record_hash=digest,
                    business_date=as_date(item.get("TrdDate")),
                    event_time=as_datetime(item.get("Tm")),
                    commodity=item.get("Cmdty"),
                    area=item.get("Area"),
                    shortcode=item.get("ShortCode"),
                    maturity=_text(item.get("Maturity")),
                    trade_id=_text(item.get("TrdID")),
                    group_id=_text(item.get("GroupID")),
                    version=_text(item.get("TrdVersion")),
                    update_action=item.get("UpdtAct"),
                    price=as_decimal(item.get("Px")),
                    size=as_decimal(item.get("Sz")),
                    volume=as_decimal(item.get("TrdVol")),
                    source_fetch_id=source_fetch_id,
                    payload=item,
                )
            )
            inserted += 1
        return inserted

    def _top_of_book(
        self,
        market: str,
        records: list[dict[str, Any]],
        source_fetch_id: str | None,
    ) -> int:
        inserted = 0
        for item in records:
            digest = record_hash(item)
            if self.session.scalar(
                select(TopOfBook.id).where(
                    TopOfBook.market == market, TopOfBook.record_hash == digest
                )
            ):
                continue
            self.session.add(
                TopOfBook(
                    id=_id(),
                    market=market,
                    record_hash=digest,
                    business_date=as_date(item.get("TrdDate")),
                    event_time=as_datetime(item.get("Tm")),
                    commodity=item.get("Cmdty"),
                    area=item.get("Area"),
                    shortcode=item.get("ShortCode"),
                    maturity=_text(item.get("Maturity")),
                    bid_price=as_decimal(item.get("BidPx")),
                    bid_size=as_decimal(item.get("BidSz")),
                    ask_price=as_decimal(item.get("AskPx")),
                    ask_size=as_decimal(item.get("AskSz")),
                    source_fetch_id=source_fetch_id,
                    payload=item,
                )
            )
            inserted += 1
        return inserted

    def _statistics(
        self,
        market: str,
        records: list[dict[str, Any]],
        source_fetch_id: str | None,
    ) -> int:
        inserted = 0
        for item in records:
            digest = record_hash(item)
            if self.session.scalar(
                select(MarketStatistic.id).where(
                    MarketStatistic.market == market,
                    MarketStatistic.record_hash == digest,
                )
            ):
                continue
            self.session.add(
                MarketStatistic(
                    id=_id(),
                    market=market,
                    record_hash=digest,
                    business_date=as_date(item.get("TrdDate")),
                    commodity=item.get("Cmdty"),
                    area=item.get("Area"),
                    shortcode=item.get("ShortCode"),
                    maturity=_text(item.get("Maturity")),
                    open_price=as_decimal(item.get("OpenPx")),
                    high_price=as_decimal(item.get("HighPx")),
                    low_price=as_decimal(item.get("LowPx")),
                    last_price=as_decimal(item.get("LastPx")),
                    trade_count=item.get("NumberOfTrd"),
                    total_size=as_decimal(item.get("TotTrdSz")),
                    total_volume=as_decimal(item.get("TotTrdVol")),
                    source_fetch_id=source_fetch_id,
                    payload=item,
                )
            )
            inserted += 1
        return inserted

    def _settlements(
        self,
        market: str,
        records: list[dict[str, Any]],
        source_fetch_id: str | None,
    ) -> int:
        inserted = 0
        for item in records:
            digest = record_hash(item)
            if self.session.scalar(
                select(Settlement.id).where(
                    Settlement.market == market,
                    Settlement.record_hash == digest,
                )
            ):
                continue
            self.session.add(
                Settlement(
                    id=_id(),
                    market=market,
                    record_hash=digest,
                    business_date=as_date(item.get("TrdDate")),
                    event_time=as_datetime(item.get("Tm")),
                    commodity=item.get("Cmdty"),
                    area=item.get("Area"),
                    shortcode=item.get("ShortCode"),
                    maturity=_text(item.get("Maturity")),
                    price=as_decimal(item.get("Px")),
                    update_action=item.get("UpdtAct"),
                    source_fetch_id=source_fetch_id,
                    payload=item,
                )
            )
            inserted += 1
        return inserted

    def store_auctions(
        self,
        resource: str,
        records: list[dict[str, Any]],
        source_fetch_id: str | None,
    ) -> int:
        inserted = 0
        for item in records:
            auction_id = int(item["AuctID"])
            auction = self.session.get(Auction, auction_id)
            if auction is None:
                auction = Auction(
                    auction_id=auction_id,
                    auction_date=as_date(item["AuctDate"]),
                    commodity=item.get("Cmdty"),
                    area=item.get("Area"),
                    shortcode=item.get("ShortCode"),
                    status=item.get("AuctStatus"),
                    payload=item,
                    record_hash=record_hash(item),
                    source_fetch_id=source_fetch_id,
                )
                self.session.add(auction)
                inserted += 1
            elif resource == "reference":
                auction.status = item.get("AuctStatus")
                auction.payload = item
                auction.record_hash = record_hash(item)
            if resource == "results":
                inserted += self._auction_result(auction_id, item, source_fetch_id)
            elif resource == "revenues":
                auctioneers = item.get("Auctioneers") or [item]
                for detail in auctioneers:
                    merged = {**item, **detail}
                    merged.pop("Auctioneers", None)
                    inserted += self._auction_revenue(
                        auction_id, merged, source_fetch_id
                    )
        self.session.commit()
        return inserted

    def _auction_result(
        self, auction_id: int, item: dict[str, Any], source_fetch_id: str | None
    ) -> int:
        digest = record_hash(item)
        if self.session.scalar(
            select(AuctionResult.id).where(
                AuctionResult.auction_id == auction_id,
                AuctionResult.record_hash == digest,
            )
        ):
            return 0
        self.session.add(
            AuctionResult(
                id=_id(),
                auction_id=auction_id,
                record_hash=digest,
                event_time=as_datetime(item.get("Tm")),
                price=as_decimal(item.get("AuctPx")),
                traded_volume=as_decimal(item.get("AuctTrdVol")),
                total_revenue=as_decimal(item.get("TotalAuctRev")),
                source_fetch_id=source_fetch_id,
                payload=item,
            )
        )
        return 1

    def _auction_revenue(
        self, auction_id: int, item: dict[str, Any], source_fetch_id: str | None
    ) -> int:
        digest = record_hash(item)
        if self.session.scalar(
            select(AuctionRevenue.id).where(
                AuctionRevenue.auction_id == auction_id,
                AuctionRevenue.record_hash == digest,
            )
        ):
            return 0
        self.session.add(
            AuctionRevenue(
                id=_id(),
                auction_id=auction_id,
                record_hash=digest,
                auctioneer_name=item.get("AuctioneerName"),
                volume=as_decimal(item.get("AuctioneerVol") or item.get("AuctTrdVol")),
                revenue=as_decimal(
                    item.get("AuctioneerRev") or item.get("TotalAuctRev")
                ),
                source_fetch_id=source_fetch_id,
                payload=item,
            )
        )
        return 1

    def store_indices(
        self, records: list[dict[str, Any]], source_fetch_id: str | None
    ) -> int:
        inserted = 0
        for item in records:
            ticks = item.get("Ticks")
            if ticks is None:
                ticks = [item]
            definition = self._index_definition(item)
            for tick in ticks:
                merged = {**item, **tick}
                merged.pop("Ticks", None)
                digest = record_hash(merged)
                if self.session.scalar(
                    select(IndexObservation.id).where(
                        IndexObservation.definition_id == definition.id,
                        IndexObservation.record_hash == digest,
                    )
                ):
                    continue
                trade_date = as_date(merged.get("TrdDate"))
                if trade_date is None:
                    continue
                self.session.add(
                    IndexObservation(
                        id=_id(),
                        definition_id=definition.id,
                        trade_date=trade_date,
                        event_time=as_datetime(merged.get("Tm")),
                        record_hash=digest,
                        price=as_decimal(merged.get("Px")),
                        volume=as_decimal(merged.get("Vol")),
                        update_action=merged.get("UpdtAct"),
                        source_fetch_id=source_fetch_id,
                        payload=merged,
                    )
                )
                inserted += 1
        self.session.commit()
        return inserted

    def _index_definition(self, item: dict[str, Any]) -> IndexDefinition:
        definition = self.session.scalar(
            select(IndexDefinition).where(
                IndexDefinition.commodity == item.get("Cmdty"),
                IndexDefinition.area == item.get("Area"),
                IndexDefinition.index_code == item.get("Index"),
            )
        )
        if definition is None:
            definition = IndexDefinition(
                id=_id(),
                commodity=item.get("Cmdty") or "",
                area=item.get("Area") or "",
                index_code=item.get("Index") or "",
                long_name=item.get("LongName"),
                unit=item.get("UOM"),
                currency=item.get("Currency"),
                payload=item,
            )
            self.session.add(definition)
        return definition

    def store_transparency_reference(
        self,
        records: list[dict[str, Any]],
        source_fetch_id: str | None,
        validity_date: date | None = None,
    ) -> int:
        count = 0
        for company_data in records:
            company_id = company_data.get("companyID")
            if not company_id:
                continue
            company = self.session.get(TransparencyCompany, company_id)
            values = {
                "name": company_data.get("companyName"),
                "country": company_data.get("companyCountry"),
                "ace": company_data.get("ace"),
                "modified_at": as_datetime(company_data.get("modified")),
                "payload": company_data,
            }
            if company is None:
                company = TransparencyCompany(company_id=company_id, **values)
                self.session.add(company)
                count += 1
            else:
                for key, value in values.items():
                    setattr(company, key, value)
            count += self._reference_snapshot(
                "company",
                company_id,
                company_data,
                validity_date,
                source_fetch_id,
                nested_key="facilities",
            )
            for facility_data in company_data.get("facilities", []):
                count += self._facility(
                    company_id,
                    facility_data,
                    validity_date,
                    source_fetch_id,
                )
        self.session.commit()
        return count

    def _facility(
        self,
        company_id: str,
        item: dict[str, Any],
        validity_date: date | None,
        source_fetch_id: str | None,
    ) -> int:
        facility_id = item.get("facilityID")
        if not facility_id:
            return 0
        count = 0
        facility = self.session.get(TransparencyFacility, facility_id)
        values = {
            "company_id": company_id,
            "name": item.get("facilityName"),
            "area": item.get("area"),
            "latitude": as_decimal(item.get("latitude")),
            "longitude": as_decimal(item.get("longitude")),
            "modified_at": as_datetime(item.get("modified")),
            "payload": item,
        }
        if facility is None:
            facility = TransparencyFacility(facility_id=facility_id, **values)
            self.session.add(facility)
            count += 1
        else:
            for key, value in values.items():
                setattr(facility, key, value)
        count += self._reference_snapshot(
            "facility",
            facility_id,
            item,
            validity_date,
            source_fetch_id,
            nested_key="units",
        )
        for unit_data in item.get("units", []):
            count += self._unit(facility_id, unit_data, validity_date, source_fetch_id)
        return count

    def _unit(
        self,
        facility_id: str,
        item: dict[str, Any],
        validity_date: date | None,
        source_fetch_id: str | None,
    ) -> int:
        unit_id = item.get("unitID")
        if not unit_id:
            return 0
        count = 0
        unit = self.session.get(TransparencyUnit, unit_id)
        values = {
            "facility_id": facility_id,
            "name": item.get("unitName"),
            "commodity": item.get("commodity"),
            "facility_type": item.get("facilityType"),
            "fuel_type": item.get("fuelType"),
            "eic": item.get("eic"),
            "modified_at": as_datetime(item.get("modified")),
            "payload": item,
        }
        if unit is None:
            unit = TransparencyUnit(unit_id=unit_id, **values)
            self.session.add(unit)
            count += 1
        else:
            for key, value in values.items():
                setattr(unit, key, value)
        count += self._reference_snapshot(
            "unit",
            unit_id,
            item,
            validity_date,
            source_fetch_id,
            nested_key="capacities",
        )
        for capacity in item.get("capacities", []):
            digest = record_hash(capacity)
            if not self.session.scalar(
                select(TransparencyCapacity.id).where(
                    TransparencyCapacity.unit_id == unit_id,
                    TransparencyCapacity.record_hash == digest,
                )
            ):
                self.session.add(
                    TransparencyCapacity(
                        id=_id(),
                        unit_id=unit_id,
                        record_hash=digest,
                        valid_from=as_datetime(capacity.get("validFrom")),
                        modified_at=as_datetime(capacity.get("modified")),
                        installed=as_decimal(capacity.get("installedCapacity")),
                        working=as_decimal(capacity.get("workingCapacity")),
                        unit_measure=capacity.get("unitMeasure"),
                        payload=capacity,
                    )
                )
                count += 1
            count += self._reference_snapshot(
                "capacity",
                unit_id,
                capacity,
                validity_date,
                source_fetch_id,
            )
        return count

    def _reference_snapshot(
        self,
        entity_type: str,
        entity_id: str,
        item: dict[str, Any],
        validity_date: date | None,
        source_fetch_id: str | None,
        *,
        nested_key: str | None = None,
    ) -> int:
        if validity_date is None:
            return 0
        payload = dict(item)
        if nested_key:
            payload.pop(nested_key, None)
        digest = record_hash(payload)
        exists = self.session.scalar(
            select(TransparencyReferenceSnapshot.id).where(
                TransparencyReferenceSnapshot.entity_type == entity_type,
                TransparencyReferenceSnapshot.entity_id == entity_id,
                TransparencyReferenceSnapshot.validity_date == validity_date,
                TransparencyReferenceSnapshot.record_hash == digest,
            )
        )
        if exists is not None:
            return 0
        self.session.add(
            TransparencyReferenceSnapshot(
                id=_id(),
                entity_type=entity_type,
                entity_id=entity_id,
                validity_date=validity_date,
                record_hash=digest,
                source_fetch_id=source_fetch_id,
                payload=payload,
            )
        )
        return 1

    def store_umms(
        self,
        records: list[dict[str, Any]],
        source_fetch_id: str | None,
        *,
        kind: str = "umm",
    ) -> int:
        inserted = 0
        for item in records:
            message_id = item.get("messageID")
            if not message_id:
                continue
            thread_id, _, version = message_id.rpartition("_")
            if not thread_id:
                thread_id = message_id
            modified = as_datetime(item.get("modified"))
            thread = self.session.get(UmmThread, thread_id)
            if thread is None:
                thread = UmmThread(
                    thread_id=thread_id,
                    kind=kind,
                    commodity=item.get("commodity"),
                    area=item.get("area"),
                    latest_message_id=message_id,
                    latest_modified_at=modified,
                    status=item.get("eventStatus"),
                )
                self.session.add(thread)
            elif (
                thread.latest_modified_at is None
                or modified is None
                or _utc(modified) >= _utc(thread.latest_modified_at)
            ):
                thread.latest_message_id = message_id
                thread.latest_modified_at = modified
                thread.status = item.get("eventStatus")
            if self.session.get(UmmRevision, message_id) is not None:
                continue
            revision = UmmRevision(
                message_id=message_id,
                thread_id=thread_id,
                version=version or None,
                modified_at=modified,
                published_at=as_datetime(item.get("published")),
                event_start=as_datetime(item.get("eventStart")),
                event_stop=as_datetime(item.get("eventStop")),
                record_hash=record_hash(item),
                source_fetch_id=source_fetch_id,
                payload=item,
            )
            self.session.add(revision)
            for interval in (item.get("capacity") or {}).get("capacityIntervals", []):
                start = as_datetime(interval.get("intervalStart"))
                stop = as_datetime(interval.get("intervalStop"))
                if start and stop:
                    self.session.add(
                        UmmCapacityInterval(
                            id=_id(),
                            message_id=message_id,
                            interval_start=start,
                            interval_stop=stop,
                            available=as_decimal(interval.get("availableCapacity")),
                            unavailable=as_decimal(interval.get("unavailableCapacity")),
                        )
                    )
            inserted += 1
        self.session.commit()
        return inserted

    def store_series(
        self,
        records: list[dict[str, Any]],
        source_fetch_id: str | None,
        *,
        source: str = "transparency",
    ) -> int:
        inserted = 0
        for item in records:
            key = stable_key(
                item.get("facilityType"),
                item.get("fuelType"),
                item.get("unitID"),
                item.get("controlArea"),
                item.get("marketArea"),
                item.get("timeResolution"),
                item.get("unitMeasure"),
            )
            series = self.session.scalar(
                select(TransparencySeries).where(
                    TransparencySeries.source == source,
                    TransparencySeries.commodity == item.get("commodity"),
                    TransparencySeries.area == item.get("area"),
                    TransparencySeries.symbol == item.get("symbol"),
                    TransparencySeries.series_key == key,
                )
            )
            if series is None:
                series = TransparencySeries(
                    id=_id(),
                    source=source,
                    commodity=item.get("commodity") or "",
                    area=item.get("area") or "",
                    symbol=item.get("symbol") or "",
                    series_key=key,
                    facility_type=item.get("facilityType"),
                    fuel_type=item.get("fuelType"),
                    unit_id=item.get("unitID"),
                    resolution=item.get("timeResolution"),
                    unit_measure=item.get("unitMeasure"),
                    payload={
                        key: value for key, value in item.items() if key != "series"
                    },
                )
                self.session.add(series)
            for point in item.get("series", []):
                timestamp = as_datetime(point.get("timeStamp"))
                modified = as_datetime(point.get("modified"))
                value = as_decimal(point.get("value"))
                if timestamp is None or modified is None or value is None:
                    continue
                exists = self.session.scalar(
                    select(TransparencySeriesPoint.id).where(
                        TransparencySeriesPoint.series_id == series.id,
                        TransparencySeriesPoint.timestamp == timestamp,
                        TransparencySeriesPoint.modified_at == modified,
                    )
                )
                if exists is None:
                    self.session.add(
                        TransparencySeriesPoint(
                            id=_id(),
                            series_id=series.id,
                            timestamp=timestamp,
                            modified_at=modified,
                            value=value,
                            source_fetch_id=source_fetch_id,
                        )
                    )
                    inserted += 1
        self.session.commit()
        return inserted


def _text(value: Any) -> str | None:
    return None if value in (None, "") else str(value)


def _utc(value: datetime) -> datetime:
    """Normalize SQLite's timezone-naive round trips for comparisons."""

    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
