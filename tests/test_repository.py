from __future__ import annotations

from sqlalchemy import func, select

from eex_datasource.storage.database import (
    create_database_engine,
    session_factory,
)
from eex_datasource.storage.models import (
    Base,
    MarketTrade,
    TransparencySeriesPoint,
    UmmRevision,
)
from eex_datasource.storage.repositories import DataRepository


def repository():
    engine = create_database_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = session_factory(engine)()
    return session, DataRepository(session)


def test_market_trade_import_is_idempotent_and_keeps_revision() -> None:
    session, repo = repository()
    original = {
        "TrdDate": "2026-01-02",
        "Cmdty": "POWER",
        "Area": "DE",
        "ShortCode": "DEBM",
        "Maturity": 202602,
        "TrdType": "Exchange",
        "TrdID": 42,
        "Tm": "2026-01-02T10:00:00Z",
        "UpdtAct": "New",
        "Px": 100.2,
        "Sz": 3,
    }
    assert repo.store_market("derivatives", "trades", [original], None) == 1
    assert repo.store_market("derivatives", "trades", [original], None) == 0
    deleted = {**original, "UpdtAct": "Delete"}
    assert repo.store_market("derivatives", "trades", [deleted], None) == 1
    assert session.scalar(select(func.count()).select_from(MarketTrade)) == 2
    session.close()


def test_umm_and_series_revisions_are_preserved() -> None:
    session, repo = repository()
    umm = {
        "messageID": "00000000000000002564#3662_001",
        "commodity": "POWER",
        "area": "DE",
        "modified": "2026-01-02T10:00:00Z",
        "published": "2026-01-02T10:00:01Z",
        "eventStatus": "Active",
    }
    assert repo.store_umms([umm], None) == 1
    assert repo.store_umms([umm], None) == 0
    assert session.scalar(select(func.count()).select_from(UmmRevision)) == 1

    series = {
        "symbol": "AvailableCapacity",
        "commodity": "POWER",
        "area": "DE",
        "timeResolution": "Hourly",
        "unitMeasure": "MW",
        "series": [
            {
                "timeStamp": "2026-01-02T10:00:00Z",
                "modified": "2026-01-02T10:05:00Z",
                "value": 10,
            }
        ],
    }
    assert repo.store_series([series], None) == 1
    assert repo.store_series([series], None) == 0
    corrected = {
        **series,
        "series": [
            {
                "timeStamp": "2026-01-02T10:00:00Z",
                "modified": "2026-01-02T10:10:00Z",
                "value": 11,
            }
        ],
    }
    assert repo.store_series([corrected], None) == 1
    assert (
        session.scalar(select(func.count()).select_from(TransparencySeriesPoint)) == 2
    )
    session.close()
