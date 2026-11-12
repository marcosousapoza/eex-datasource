from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest

from eex_datasource import EEXClient, RateLimiter


@pytest.fixture
def make_client() -> Callable[[Callable[[httpx.Request], httpx.Response]], EEXClient]:
    def factory(handler: Callable[[httpx.Request], httpx.Response]) -> EEXClient:
        return EEXClient(
            "test-token",
            retries=0,
            rate_limiter=RateLimiter(interval=0),
            http_transport=httpx.MockTransport(handler),
        )

    return factory
