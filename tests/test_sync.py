from __future__ import annotations

from datetime import date, timedelta

import httpx
from sqlalchemy import func, select

from eex_datasource import EEXClient
from eex_datasource.storage.archive import Archive
from eex_datasource.storage.database import (
    create_database_engine,
    session_factory,
)
from eex_datasource.storage.models import (
    ApiFetch,
    Base,
    MarketInstrument,
    MarketTrade,
    SyncRun,
    TopOfBook,
)
from eex_datasource.sync import Synchronizer


def test_market_sync_archives_normalizes_and_is_idempotent(tmp_path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        common = {
            "TrdDate": "2026-01-02",
            "Cmdty": "POWER",
            "Area": "DE",
            "ShortCode": "DEBM",
            "Maturity": 202602,
        }
        path = request.url.path
        if path.endswith("/rd/derivatives/POWER/DE/"):
            payload = ["2026-01-02"]
        elif "/rd/" in path:
            payload = [{**common, "InstrumentISIN": "DE000TEST001"}]
        elif "/trd/" in path:
            payload = [
                {
                    **common,
                    "TrdID": 1,
                    "TrdType": "Exchange",
                    "Tm": "2026-01-02T10:00:00Z",
                    "Px": 100.0,
                }
            ]
        elif "/tob/" in path:
            payload = [
                {
                    **common,
                    "Tm": "2026-01-02T10:00:00Z",
                    "BidPx": 99.0,
                    "AskPx": 101.0,
                }
            ]
        elif "/stat/" in path:
            payload = [{**common, "OpenPx": 100.0, "LastPx": 101.0}]
        elif "/spr/" in path:
            payload = [{**common, "Px": 101.0, "UpdtAct": "New"}]
        else:  # pragma: no cover - shows unexpected endpoint in failure
            return httpx.Response(404, request=request)
        return httpx.Response(200, json=payload, request=request)

    engine = create_database_engine("sqlite://")
    Base.metadata.create_all(engine)
    sessions = session_factory(engine)
    with EEXClient(
        "token",
        request_interval=0,
        transport=httpx.MockTransport(handler),
    ) as client:
        sync = Synchronizer(
            client,
            sessions,
            Archive(tmp_path),
            cache_ttl=timedelta(days=1),
        )
        sync.market(
            "derivatives",
            "POWER",
            "DE",
            date(2026, 1, 2),
            date(2026, 1, 2),
        )
        sync.market(
            "derivatives",
            "POWER",
            "DE",
            date(2026, 1, 2),
            date(2026, 1, 2),
        )

    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(MarketInstrument)) == 1
        assert session.scalar(select(func.count()).select_from(MarketTrade)) == 1
        runs = session.scalars(select(SyncRun).order_by(SyncRun.started_at)).all()
        assert [run.status for run in runs] == ["succeeded", "succeeded"]
        assert runs[0].fetched_count == 6
    assert runs[1].fetched_count == 0


def test_spot_book_sync_preserves_per_shortcode_provenance(tmp_path) -> None:
    """Each scoped Gas Spot book response must have its own source manifest."""

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/v2/rd/spot/NATGAS/TTF/":
            payload = ["2026-01-02"]
        elif path == "/v2/rd/spot/NATGAS/TTF/2026-01-02/":
            payload = ["TTFDA", "TTFWD"]
        elif path.startswith("/v2/tob/spot/"):
            assert path.rsplit("/", 1)[-1] in {"TTFDA", "TTFWD"}
            assert not request.url.params
            payload = [
                {
                    "TrdDate": "2026-01-02",
                    "Cmdty": "NATGAS",
                    "Area": "TTF",
                    "ShortCode": path.rsplit("/", 1)[-1],
                    "BidPx": 30,
                }
            ]
        else:
            payload = []
        return httpx.Response(200, json=payload, request=request)

    engine = create_database_engine("sqlite://")
    Base.metadata.create_all(engine)
    sessions = session_factory(engine)
    with EEXClient(
        "token",
        request_interval=0,
        transport=httpx.MockTransport(handler),
    ) as client:
        Synchronizer(client, sessions, Archive(tmp_path)).market(
            "gas_spot",
            "NATGAS",
            "TTF",
            date(2026, 1, 2),
            date(2026, 1, 2),
        )

    with sessions() as session:
        books = session.scalars(select(TopOfBook)).all()
        assert {book.shortcode for book in books} == {"TTFDA", "TTFWD"}
        assert len({book.source_fetch_id for book in books}) == 2
        for book in books:
            fetch = session.get(ApiFetch, book.source_fetch_id)
            assert fetch is not None
            assert fetch.path.endswith(f"/{book.shortcode}")
