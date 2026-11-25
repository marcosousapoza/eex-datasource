from __future__ import annotations

from typing import Any

from eex_datasource.api.auctions import AuctionsAPI
from eex_datasource.api.derivatives import DerivativesAPI
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
