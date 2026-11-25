"""Exceptions raised by :mod:`eex_datasource`."""

from __future__ import annotations

from typing import Any


class EEXError(Exception):
    """Base package exception."""


class EEXConfigurationError(EEXError):
    """The client or synchronizer is not configured correctly."""


class EEXAPIError(EEXError):
    """The EEX API returned an unsuccessful response."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        path: str | None = None,
        body: Any = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.path = path
        self.body = body


class EEXAuthenticationError(EEXAPIError):
    """Authentication failed."""


class EEXRateLimitError(EEXAPIError):
    """The rate limit was exhausted after retries."""


class EEXNotFoundError(EEXAPIError):
    """The requested resource was not found."""


class EEXTruncationError(EEXError):
    """A response may have been truncated at the EEX row limit."""
