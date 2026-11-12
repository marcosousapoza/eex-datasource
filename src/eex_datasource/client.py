from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from typing import Any

import httpx

from .rate_limit import RateLimiter
from .services import (
    AuctionsService,
    DerivativesService,
    GasSpotService,
    IndicesService,
    TransparencyService,
)
from .transport import BASE_URL, Transport


class EEXClient:
    """Synchronous client for EEX Group DataSource REST API v2."""

    def __init__(
        self,
        token: str | None = None,
        *,
        base_url: str = BASE_URL,
        timeout: httpx.Timeout | None = None,
        retries: int = 3,
        max_retry_delay: float = 30.0,
        rate_limiter: RateLimiter | None = None,
        sleeper: Callable[[float], None] = time.sleep,
        http_transport: httpx.BaseTransport | None = None,
        verify: bool = True,
    ) -> None:
        self._transport = Transport(
            token,
            base_url=base_url,
            timeout=timeout,
            retries=retries,
            max_retry_delay=max_retry_delay,
            rate_limiter=rate_limiter,
            sleeper=sleeper,
            http_transport=http_transport,
            verify=verify,
        )
        self.derivatives = DerivativesService(self._transport)
        self.gas_spot = GasSpotService(self._transport)
        self.auctions = AuctionsService(self._transport)
        self.indices = IndicesService(self._transport)
        self.transparency = TransparencyService(self._transport)

    def request(self, path: str, *, params: Mapping[str, Any] | None = None) -> Any:
        """Make a low-level GET request while retaining all transport policies."""
        payload, _ = self._transport.request(path, operation="client.request", params=params)
        return payload

    def close(self) -> None:
        self._transport.close()

    def __enter__(self) -> EEXClient:
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        self.close()
