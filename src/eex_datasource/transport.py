"""Authenticated HTTP transport with throttling, retries, and error translation."""

from __future__ import annotations

import os
import time
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from decimal import Decimal
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

from .exceptions import (
    APIError,
    AuthenticationError,
    AuthorizationError,
    ConfigurationError,
    InvalidRequestError,
    NotFoundError,
    RateLimitError,
    ResponseParsingError,
    TransportError,
)
from .rate_limit import RateLimiter, jitter

BASE_URL = "https://api.eex-group.com/v2"


class Transport:
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
        resolved_token = token or os.environ.get("EEX_API_TOKEN")
        if not resolved_token:
            raise ConfigurationError(
                "An API token is required via token= or the EEX_API_TOKEN environment variable"
            )
        if retries < 0:
            raise ConfigurationError("retries cannot be negative")
        parsed = httpx.URL(base_url)
        if parsed.scheme != "https" or not parsed.host:
            raise ConfigurationError("base_url must be an absolute HTTPS URL")
        self._token = resolved_token
        self._base_origin = (parsed.scheme, parsed.host, parsed.port)
        self._retries = retries
        self._max_retry_delay = max_retry_delay
        self._limiter = rate_limiter or RateLimiter(sleeper=sleeper)
        self._sleep = sleeper
        self._client = httpx.Client(
            base_url=str(parsed).rstrip("/") + "/",
            timeout=timeout or httpx.Timeout(30.0, connect=10.0),
            transport=http_transport,
            verify=verify,
            follow_redirects=False,
            headers={"Accept": "application/json", "Authorization": f"Bearer {resolved_token}"},
        )

    def close(self) -> None:
        self._client.close()

    def request(
        self,
        path: str,
        *,
        operation: str,
        params: Mapping[str, Any] | None = None,
    ) -> tuple[Any, str | None]:
        if not path.startswith("/") or path.startswith("//") or "://" in path:
            raise InvalidRequestError("Only relative API paths beginning with '/' are allowed")
        safe_params = dict(params or {})
        for attempt in range(self._retries + 1):
            self._limiter.wait()
            try:
                response = self._client.get(path.lstrip("/"), params=safe_params)
            except httpx.RequestError as exc:
                if attempt < self._retries:
                    self._sleep(self._backoff(attempt))
                    continue
                raise TransportError(
                    "Network request failed",
                    operation=operation,
                    parameters=safe_params,
                ) from exc

            if response.is_redirect:
                raise TransportError(
                    "Redirects are not followed to protect authorization credentials",
                    status_code=response.status_code,
                    operation=operation,
                    parameters=safe_params,
                )
            if response.status_code == 429 or 500 <= response.status_code <= 599:
                if attempt < self._retries:
                    self._sleep(self._retry_delay(response, attempt))
                    continue
                cls = RateLimitError if response.status_code == 429 else TransportError
                raise cls(
                    "Rate limit retry budget exhausted"
                    if response.status_code == 429
                    else "Server retry budget exhausted",
                    status_code=response.status_code,
                    operation=operation,
                    parameters=safe_params,
                    request_id=self._request_id(response),
                )
            self._raise_for_status(response, operation, safe_params)
            try:
                payload = response.json(parse_float=Decimal)
            except (ValueError, TypeError) as exc:
                raise ResponseParsingError(
                    "Response was not valid JSON",
                    status_code=response.status_code,
                    operation=operation,
                    parameters=safe_params,
                    request_id=self._request_id(response),
                ) from exc
            return payload, self._request_id(response)
        raise AssertionError("unreachable")

    def _raise_for_status(
        self, response: httpx.Response, operation: str, params: dict[str, Any]
    ) -> None:
        if response.status_code < 400:
            return
        classes: dict[int, type[APIError]] = {
            400: InvalidRequestError,
            401: AuthenticationError,
            403: AuthorizationError,
            404: NotFoundError,
        }
        cls = classes.get(response.status_code, APIError)
        raise cls(
            "API request failed",
            status_code=response.status_code,
            operation=operation,
            parameters=params,
            request_id=self._request_id(response),
        )

    @staticmethod
    def _request_id(response: httpx.Response) -> str | None:
        value = response.headers.get("x-request-id") or response.headers.get("request-id")
        return str(value) if value is not None else None

    def _backoff(self, attempt: int) -> float:
        return float(min(self._max_retry_delay, (2**attempt) + jitter()))

    def _retry_delay(self, response: httpx.Response, attempt: int) -> float:
        value = response.headers.get("Retry-After")
        if value:
            try:
                return min(self._max_retry_delay, max(0.0, float(value)))
            except ValueError:
                try:
                    target = parsedate_to_datetime(value)
                    if target.tzinfo is None:
                        target = target.replace(tzinfo=UTC)
                    return min(
                        self._max_retry_delay,
                        max(0.0, (target - datetime.now(UTC)).total_seconds()),
                    )
                except (TypeError, ValueError):
                    pass
        return self._backoff(attempt)
