from __future__ import annotations

from datetime import datetime, time
from decimal import Decimal

import httpx
import pytest

from eex_datasource import (
    AuthenticationError,
    ConfigurationError,
    EEXClient,
    InvalidRequestError,
    RateLimiter,
    ResponseParsingError,
    SuspectedTruncationError,
)


def test_token_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EEX_API_TOKEN", raising=False)
    with pytest.raises(ConfigurationError):
        EEXClient()


def test_environment_token_and_context_manager(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EEX_API_TOKEN", "environment-secret")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer environment-secret"
        assert request.headers["Accept"] == "application/json"
        return httpx.Response(200, json=[])

    with EEXClient(
        retries=0,
        rate_limiter=RateLimiter(interval=0),
        http_transport=httpx.MockTransport(handler),
    ) as client:
        assert client.derivatives.commodities() == []


def test_discovery_trailing_slash(make_client) -> None:  # type: ignore[no-untyped-def]
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v2/rd/derivatives/"
        return httpx.Response(200, json=["Power", "Gas"])

    with make_client(handler) as client:
        assert client.derivatives.commodities() == ["Power", "Gas"]


def test_reserved_path_characters_are_encoded_once(make_client) -> None:  # type: ignore[no-untyped-def]
    def handler(request: httpx.Request) -> httpx.Response:
        assert b"A%2FB" in request.url.raw_path
        assert b"M%2B1" in request.url.raw_path
        assert b"%252F" not in request.url.raw_path
        return httpx.Response(200, json=[])

    with make_client(handler) as client:
        client.derivatives.top_of_book("Power", "A/B", "2026-01-02", symbol="M+1")


def test_decimal_and_unknown_fields_are_preserved(make_client) -> None:  # type: ignore[no-untyped-def]
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=b'[{"Price": 12.34, "FutureField": 0}]',
            headers={"content-type": "application/json", "x-request-id": "abc"},
        )

    with make_client(handler) as client:
        result = client.derivatives.trades("Power", "DE", "2026-01-02")
    assert result[0]["Price"] == Decimal("12.34")
    assert result[0].FutureField == 0
    assert result.raw[0]["FutureField"] == 0
    assert result.metadata.request_id == "abc"


def test_invalid_datetime_is_not_silently_truncated(make_client) -> None:  # type: ignore[no-untyped-def]
    with (
        make_client(lambda request: httpx.Response(200, json=[])) as client,
        pytest.raises(InvalidRequestError, match="not a datetime"),
    ):
        client.derivatives.trades("Power", "DE", datetime(2026, 1, 2))


def test_time_objects_are_encoded_as_iso_times(make_client) -> None:  # type: ignore[no-untyped-def]
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["timeFrom"] == "08:30:15.123000"
        assert request.url.params["timeTo"] == "12:00:00"
        return httpx.Response(200, json=[])

    with make_client(handler) as client:
        client.derivatives.trades(
            "Power",
            "DE",
            "2026-01-02",
            time_from=time(8, 30, 15, 123000),
            time_to=time(12),
        )


def test_datetime_is_rejected_for_time_only_parameter(make_client) -> None:  # type: ignore[no-untyped-def]
    with (
        make_client(lambda request: httpx.Response(200, json=[])) as client,
        pytest.raises(InvalidRequestError, match="must be a time, not a datetime"),
    ):
        client.derivatives.trades(
            "Power",
            "DE",
            "2026-01-02",
            time_from=datetime(2026, 1, 2, 8, 30),
        )


def test_cap_requires_explicit_partial_opt_in(make_client) -> None:  # type: ignore[no-untyped-def]
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[{"id": 1}])

    with make_client(handler) as client:
        with pytest.raises(SuspectedTruncationError) as caught:
            client.derivatives.trades("Power", "DE", "2026-01-02", limit=1)
        assert len(caught.value.result) == 1
        partial = client.derivatives.trades(
            "Power", "DE", "2026-01-02", limit=1, allow_partial=True
        )
    assert partial.metadata.potentially_truncated is True


def test_http_error_and_malformed_shape(make_client) -> None:  # type: ignore[no-untyped-def]
    with make_client(lambda request: httpx.Response(401)) as client:
        with pytest.raises(AuthenticationError) as caught:
            client.derivatives.commodities()
        assert "test-token" not in str(caught.value)

    with (
        make_client(lambda request: httpx.Response(200, json={"not": "a list"})) as client,
        pytest.raises(ResponseParsingError),
    ):
        client.derivatives.commodities()


def test_low_level_request_rejects_absolute_urls(make_client) -> None:  # type: ignore[no-untyped-def]
    with (
        make_client(lambda request: httpx.Response(200, json=[])) as client,
        pytest.raises(InvalidRequestError),
    ):
        client.request("https://attacker.example/data")
