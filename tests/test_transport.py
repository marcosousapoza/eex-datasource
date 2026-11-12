from __future__ import annotations

import httpx

from eex_datasource import EEXClient, RateLimiter


class FakeTime:
    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def clock(self) -> float:
        return self.now

    def sleep(self, duration: float) -> None:
        self.sleeps.append(duration)
        self.now += duration


def test_shared_rate_limiter_spaces_clients() -> None:
    fake = FakeTime()
    limiter = RateLimiter(interval=1.0, clock=fake.clock, sleeper=fake.sleep)
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=[]))
    one = EEXClient("a", retries=0, rate_limiter=limiter, http_transport=transport)
    two = EEXClient("b", retries=0, rate_limiter=limiter, http_transport=transport)
    try:
        one.derivatives.commodities()
        two.derivatives.commodities()
    finally:
        one.close()
        two.close()
    assert fake.sleeps == [1.0]


def test_retry_after_and_limiter_apply_to_retry() -> None:
    fake = FakeTime()
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, headers={"Retry-After": "2"})
        return httpx.Response(200, json=[])

    client = EEXClient(
        "token",
        retries=1,
        max_retry_delay=10,
        rate_limiter=RateLimiter(interval=1, clock=fake.clock, sleeper=fake.sleep),
        sleeper=fake.sleep,
        http_transport=httpx.MockTransport(handler),
    )
    try:
        assert client.derivatives.commodities() == []
    finally:
        client.close()
    assert calls == 2
    assert fake.sleeps == [2.0]
