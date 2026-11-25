"""HTTP client for EEX Group DataSource REST API v2."""

from __future__ import annotations

import email.utils
import logging
import random
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Self

import httpx

from .api.auctions import AuctionsAPI
from .api.derivatives import DerivativesAPI
from .api.gas_spot import GasSpotAPI
from .api.indices import IndicesAPI
from .api.transparency import TransparencyAPI
from .errors import (
    EEXAPIError,
    EEXAuthenticationError,
    EEXConfigurationError,
    EEXNotFoundError,
    EEXRateLimitError,
)
from .rate_limit import RateLimiter

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class APIResponse:
    data: Any
    body: bytes
    url: str
    path: str
    status_code: int
    headers: dict[str, str]
    fetched_at: datetime


class EEXClient:
    """Synchronous, rate-limit aware EEX API client.

    The client deliberately remains synchronous: the upstream allowance is one
    request per second per user, so concurrent calls provide no useful
    throughput and make accidental throttling easier.
    """

    def __init__(
        self,
        access_token: str | None,
        *,
        base_url: str = "https://api.eex-group.com/v2",
        timeout: float = 60.0,
        request_interval: float = 1.05,
        max_retries: int = 5,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if not access_token:
            raise EEXConfigurationError(
                "An EEX access token is required (set EEX_ACCESS_TOKEN)."
            )
        self.base_url = base_url.rstrip("/")
        self.max_retries = max_retries
        self.rate_limiter = RateLimiter(request_interval)
        self._http = httpx.Client(
            base_url=self.base_url,
            timeout=timeout,
            transport=transport,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
                "User-Agent": "eex-datasource/0.1.0",
            },
        )
        self.derivatives = DerivativesAPI(self)
        self.gas_spot = GasSpotAPI(self)
        self.auctions = AuctionsAPI(self)
        self.indices = IndicesAPI(self)
        self.transparency = TransparencyAPI(self)

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        self._http.close()

    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        return self.get_response(path, params=params).data

    def get_response(
        self, path: str, params: dict[str, Any] | None = None
    ) -> APIResponse:
        clean_params = {
            key: value for key, value in (params or {}).items() if value is not None
        }
        last_response: httpx.Response | None = None
        for attempt in range(self.max_retries + 1):
            self.rate_limiter.wait()
            logger.debug("GET %s params=%s", path, clean_params)
            try:
                response = self._http.get(path, params=clean_params)
            except httpx.TransportError as exc:
                if attempt >= self.max_retries:
                    raise EEXAPIError(
                        f"Request failed after retries: {exc}", path=path
                    ) from exc
                self._backoff(attempt)
                continue

            last_response = response
            if response.status_code == 429 or response.status_code >= 500:
                if attempt >= self.max_retries:
                    break
                self._backoff(attempt, response.headers.get("Retry-After"))
                continue
            if response.is_error:
                self._raise_for_response(response, path)

            try:
                data = response.json()
            except ValueError as exc:
                raise EEXAPIError(
                    "EEX returned a non-JSON response",
                    status_code=response.status_code,
                    path=path,
                    body=response.text[:1000],
                ) from exc
            return APIResponse(
                data=data,
                body=response.content,
                url=str(response.url),
                path=path,
                status_code=response.status_code,
                headers=dict(response.headers),
                fetched_at=datetime.now(UTC),
            )

        assert last_response is not None
        if last_response.status_code == 429:
            raise EEXRateLimitError(
                "EEX rate limit exhausted after retries",
                status_code=429,
                path=path,
            )
        self._raise_for_response(last_response, path)
        raise AssertionError("unreachable")

    @staticmethod
    def _retry_after(value: str | None) -> float | None:
        if not value:
            return None
        try:
            return max(0.0, float(value))
        except ValueError:
            try:
                retry_at = email.utils.parsedate_to_datetime(value)
                return max(
                    0.0,
                    (retry_at - datetime.now(retry_at.tzinfo or UTC)).total_seconds(),
                )
            except (TypeError, ValueError):
                return None

    def _backoff(self, attempt: int, retry_after: str | None = None) -> None:
        delay = self._retry_after(retry_after)
        if delay is None:
            delay = min(30.0, 2**attempt) + random.uniform(0.0, 0.25)
        logger.warning("Retrying EEX request in %.2fs", delay)
        time.sleep(delay)

    @staticmethod
    def _raise_for_response(response: httpx.Response, path: str) -> None:
        body: Any
        try:
            body = response.json()
        except ValueError:
            body = response.text[:1000]
        kwargs = {
            "status_code": response.status_code,
            "path": path,
            "body": body,
        }
        if response.status_code == 401:
            raise EEXAuthenticationError("EEX authentication failed", **kwargs)
        if response.status_code == 404:
            raise EEXNotFoundError("EEX resource not found", **kwargs)
        if response.status_code == 429:
            raise EEXRateLimitError("EEX rate limit exceeded", **kwargs)
        raise EEXAPIError(f"EEX API returned HTTP {response.status_code}", **kwargs)

    def fetch_market_day(
        self,
        market: str,
        commodity: str,
        area: str,
        trade_date: str,
        *,
        limit: int = 60_000,
    ) -> dict[str, Any]:
        """Pool the principal calls needed for one market and business day."""

        if market == "derivatives":
            api = self.derivatives
        elif market in {"gas_spot", "gas-spot", "spot"}:
            api = self.gas_spot
        else:
            raise ValueError("market must be 'derivatives' or 'gas_spot'")
        return api.market_day(commodity, area, trade_date, limit=limit)
