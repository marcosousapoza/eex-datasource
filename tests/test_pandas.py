from __future__ import annotations

from decimal import Decimal

import pytest

from eex_datasource.result import Record, Result, metadata

pd = pytest.importorskip("pandas")


def test_result_converts_to_dataframe_without_losing_decimals() -> None:
    raw = [
        {"TrdID": 1, "Px": Decimal("12.34"), "Tm": "2026-01-02T08:30:00Z"},
        {"TrdID": 2, "Px": None, "Tm": "2026-01-02T08:31:00Z"},
    ]
    result = Result(
        tuple(Record(item) for item in raw),
        metadata("derivatives.trades", "/trd/derivatives/test", {}, len(raw)),
        raw,
    )

    frame = result.to_pandas()

    assert list(frame.columns) == ["TrdID", "Px", "Tm"]
    assert frame.loc[0, "Px"] == Decimal("12.34")
    assert frame.loc[1, "Px"] is None
    assert frame.loc[0, "Tm"] == "2026-01-02T08:30:00Z"


def test_nested_objects_are_flattened_without_exploding_collections() -> None:
    raw = [
        {
            "messageID": "event-1",
            "capacity": {"available": Decimal("12.5"), "unit": "MW"},
            "shareholders": [{"name": "Example", "share": 1}],
        }
    ]
    result = Result(
        tuple(Record(item) for item in raw),
        metadata("transparency.events", "/events", {}, 1),
        raw,
    )

    frame = result.to_pandas()

    assert "capacity" not in frame.columns
    assert frame.loc[0, "capacity.available"] == Decimal("12.5")
    assert frame.loc[0, "capacity.unit"] == "MW"
    assert frame.loc[0, "shareholders"] == [{"name": "Example", "share": 1}]


def test_flattening_can_be_disabled() -> None:
    record = Record({"id": 1, "details": {"status": "active"}})

    frame = record.to_pandas(flatten=False)

    assert frame.loc[0, "details"] == {"status": "active"}


def test_single_record_converts_to_flattened_dataframe() -> None:
    record = Record({"id": 1, "details": {"status": "active"}})

    frame = record.to_pandas()

    assert frame.shape == (1, 2)
    assert frame.loc[0, "details.status"] == "active"


def test_empty_result_converts_to_empty_dataframe() -> None:
    result = Result((), metadata("test.empty", "/empty", {}, 0), [])

    frame = result.to_pandas()

    assert frame.empty
    assert len(frame.columns) == 0
