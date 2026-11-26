from __future__ import annotations

from typing import Any

import pytest

from eex_datasource.api.auctions import AuctionsAPI
from eex_datasource.api.base import params, segment
from eex_datasource.api.derivatives import DerivativesAPI
from eex_datasource.api.gas_spot import GasSpotAPI
from eex_datasource.api.indices import IndicesAPI
from eex_datasource.api.transparency import TransparencyAPI


class RecordingTransport:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any] | None]] = []

    def get(self, path: str, params: dict[str, Any] | None = None) -> list[Any]:
        self.calls.append((path, params))
        return []


def test_endpoint_paths_match_openapi() -> None:
    transport = RecordingTransport()
    AuctionsAPI(transport).results("ENVIRONMENTALS", "EU", "2026-01-02", 42)
    IndicesAPI(transport).series(
        "NATGAS",
        "THE",
        "EGSI_D",
        date_from="2026-01-01",
        date_to="2026-01-02",
    )
    TransparencyAPI(transport).time_series(
        "POWER",
        "DE",
        "AvailableCapacity",
        "2026-01-01T00:00:00Z",
        date_to="2026-01-02T00:00:00Z",
    )
    assert transport.calls[0][0] == ("/rslt/auctions/ENVIRONMENTALS/EU/2026-01-02/42")
    assert transport.calls[1][0] == "/idxs/NATGAS/THE/EGSI_D"
    assert transport.calls[2][0] == (
        "/series/transparency/POWER/DE/AvailableCapacity/2026-01-01T00:00:00Z"
    )
    assert "limit" not in (transport.calls[2][1] or {})

    DerivativesAPI(transport).top_of_book_history(
        "POWER",
        "DE",
        "2026-01-02",
        shortcode="DEBM",
        maturity=202602,
        time_from="08:00:00",
        time_to="09:00:00",
    )
    assert transport.calls[3][0] == (
        "/tobs/derivatives/POWER/DE/2026-01-02/DEBM/202602"
    )
    assert transport.calls[3][1]["timeFrom"] == "08:00:00"


@pytest.mark.parametrize("adapter", [DerivativesAPI, GasSpotAPI, AuctionsAPI])
def test_invalid_history_resource_fails_before_request(adapter) -> None:
    transport = RecordingTransport()
    with pytest.raises(ValueError, match="resource must be"):
        adapter(transport).history("unknown", "POWER", "DE")
    assert transport.calls == []


@pytest.mark.parametrize(
    "method", ["reference_data", "trades", "statistics", "settlements"]
)
def test_maturity_requires_shortcode(method: str) -> None:
    transport = RecordingTransport()
    with pytest.raises(ValueError, match="maturity requires shortcode"):
        getattr(DerivativesAPI(transport), method)(
            "POWER",
            "DE",
            "2026-01-02",
            maturity=202602,
        )
    assert transport.calls == []


def test_history_maturity_requires_shortcode() -> None:
    transport = RecordingTransport()
    with pytest.raises(ValueError, match="maturity requires shortcode"):
        DerivativesAPI(transport).history("trd", "POWER", "DE", maturity=202602)
    assert transport.calls == []


@pytest.mark.parametrize(
    "kwargs",
    [
        {"facility_id": "facility"},
        {"company_id": "company", "unit_id": "unit"},
        {"capacities": True},
        {"company_id": "company", "facility_id": "facility", "capacities": True},
    ],
)
def test_transparency_rejects_incomplete_asset_path(kwargs) -> None:
    transport = RecordingTransport()
    with pytest.raises(ValueError, match="requires"):
        TransparencyAPI(transport).reference_data("POWER", "DE", "2026-01-02", **kwargs)
    assert transport.calls == []


@pytest.mark.parametrize("kwargs", [{"area": "DE"}, {"facility_type": "Producer"}])
def test_umm_filters_are_not_silently_ignored(kwargs) -> None:
    transport = RecordingTransport()
    with pytest.raises(ValueError, match="supplied together"):
        TransparencyAPI(transport).umm_updates(
            "POWER", "2026-01-02T00:00:00Z", **kwargs
        )
    assert transport.calls == []


@pytest.mark.parametrize(
    "kwargs",
    [
        {},
        {"shortcode": "DEBM"},
        {"maturity": 202602},
        {"symbol": "DEBM+1", "shortcode": "DEBM", "maturity": 202602},
    ],
)
def test_book_history_requires_unambiguous_instrument(kwargs) -> None:
    transport = RecordingTransport()
    with pytest.raises(ValueError):
        DerivativesAPI(transport).top_of_book_history(
            "POWER",
            "DE",
            "2026-01-02",
            time_from="08:00:00",
            **kwargs,
        )
    assert transport.calls == []


@pytest.mark.parametrize("adapter", [DerivativesAPI, GasSpotAPI])
def test_market_day_pools_public_operations(adapter) -> None:
    class MarketTransport(RecordingTransport):
        def get(self, path, params=None):
            super().get(path, params)
            if path.endswith("2026-01-02/"):
                return ["TTFDA", "TTFWD"]
            return [{"path": path}]

    transport = MarketTransport()
    is_spot = adapter is GasSpotAPI
    api = adapter(transport)
    result = api.market_day(
        "NATGAS" if is_spot else "POWER",
        "TTF" if is_spot else "DE",
        "2026-01-02",
        limit=10,
    )
    assert list(result) == [
        "reference",
        "trades",
        "top_of_book",
        "statistics",
        "settlements",
    ]
    assert len(result["top_of_book"]) == (2 if is_spot else 1)
    assert len(transport.calls) == (7 if is_spot else 5)
    for path, query in transport.calls:
        if path.startswith("/tob/"):
            assert query == {}
        elif not path.endswith("/"):
            assert query == {"limit": 10}
    if is_spot:
        assert [item["path"].rsplit("/", 1)[-1] for item in result["top_of_book"]] == [
            "TTFDA",
            "TTFWD",
        ]


def test_query_serialization_and_path_encoding() -> None:
    assert params(fields=["TrdDate", "Area"], omitted=None, limit=0) == {
        "fields": "TrdDate,Area",
        "limit": 0,
    }
    assert segment("DEBM+1") == "DEBM+1"
    assert segment("a/b c") == "a%2Fb%20c"


def test_history_query_names_follow_openapi() -> None:
    transport = RecordingTransport()
    DerivativesAPI(transport).history(
        "trd",
        "POWER",
        "DE",
        "DEBM",
        202602,
        date_from="2026-01-01",
        fields=["TrdDate", "Px"],
        limit=5,
    )
    assert transport.calls == [
        (
            "/trds/derivatives/POWER/DE/DEBM/202602",
            {"from": "2026-01-01", "fields": "TrdDate,Px", "limit": 5},
        )
    ]


def test_gas_spot_areas_keeps_default_commodity() -> None:
    transport = RecordingTransport()
    GasSpotAPI(transport).areas()
    assert transport.calls == [("/rd/spot/NATGAS/", {})]
