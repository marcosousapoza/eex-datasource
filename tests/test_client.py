from __future__ import annotations

import httpx
import pytest

from eex_datasource import EEXClient
from eex_datasource.errors import EEXAuthenticationError
from eex_datasource.rate_limit import RateLimiter


def test_client_builds_authenticated_derivatives_request() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=[{"TrdID": 1}], request=request)

    with EEXClient(
        "secret",
        request_interval=0,
        transport=httpx.MockTransport(handler),
    ) as client:
        result = client.derivatives.trades("POWER", "DE", "2026-01-02", "DEBM", 202602)

    assert result == [{"TrdID": 1}]
    assert seen[0].url.path == ("/v2/trd/derivatives/POWER/DE/2026-01-02/DEBM/202602")
    assert seen[0].headers["authorization"] == "Bearer secret"
    assert seen[0].url.params["limit"] == "60000"


def test_authentication_error_does_not_expose_token() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"detail": "no"}, request=request)

    with (
        EEXClient(
            "super-secret",
            request_interval=0,
            transport=httpx.MockTransport(handler),
        ) as client,
        pytest.raises(EEXAuthenticationError) as caught,
    ):
        client.indices.commodities()
    assert "super-secret" not in str(caught.value)


def test_rate_limiter_spaces_calls() -> None:
    now = [10.0]
    sleeps: list[float] = []

    def sleep(delay: float) -> None:
        sleeps.append(delay)
        now[0] += delay

    limiter = RateLimiter(1.0, clock=lambda: now[0], sleep=sleep)
    limiter.wait()
    now[0] += 0.25
    limiter.wait()
    assert sleeps == [0.75]
