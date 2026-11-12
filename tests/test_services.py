from __future__ import annotations

import httpx


def test_derivatives_history_parameters(make_client) -> None:  # type: ignore[no-untyped-def]
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v2/trds/derivatives/Power/DE/DEBM/202612"
        assert request.url.params["from"] == "2026-01-01"
        assert request.url.params["to"] == "2026-01-31"
        assert request.url.params["maturityOffset"] == "1"
        return httpx.Response(200, json=[])

    with make_client(handler) as client:
        client.derivatives.trade_history(
            "Power",
            "DE",
            "2026-01-01",
            "2026-01-31",
            shortcode="DEBM",
            maturity="202612",
            maturity_offset=1,
        )


def test_gas_spot_single_book_is_record(make_client) -> None:  # type: ignore[no-untyped-def]
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v2/tob/spot/Gas/TTF/2026-01-02/GND"
        return httpx.Response(200, json={"Bid": 10, "Ask": 11})

    with make_client(handler) as client:
        book = client.gas_spot.top_of_book("Gas", "TTF", "2026-01-02", "GND")
    assert book.Bid == 10


def test_auctions_index_and_transparency_paths(make_client) -> None:  # type: ignore[no-untyped-def]
    paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        return httpx.Response(200, json=[])

    with make_client(handler) as client:
        client.auctions.revenue_history("EUA", "EU", "2026-01-01", "2026-01-31")
        client.indices.history("Gas", "EGSI", "EGSI", "2026-01-01", "2026-01-31")
        client.transparency.capacities("Power", "DE", "2026-01-01", "company", "facility", "unit")
    assert paths == [
        "/v2/revs/auctions/EUA/EU",
        "/v2/idxs/Gas/EGSI/EGSI",
        "/v2/rd/transparency/Power/DE/2026-01-01/company/facility/unit/",
    ]


def test_transparency_modified_query_variants(make_client) -> None:  # type: ignore[no-untyped-def]
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v2/umm/transparency/Power/DE/Production/2026-01-01T00:00:00Z"
        assert request.url.params["companyID"] == "abc"
        assert request.url.params["limit"] == "60000"
        return httpx.Response(200, json=[])

    with make_client(handler) as client:
        client.transparency.events_modified(
            "Power",
            "2026-01-01T00:00:00Z",
            area="DE",
            facility_type="Production",
            company_id="abc",
        )
