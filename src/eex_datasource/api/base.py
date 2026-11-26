"""Shared adapter helpers."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Protocol
from urllib.parse import quote


class Transport(Protocol):
    """Minimal HTTP interface shared by live and cached transports."""

    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """Return the decoded JSON body of a GET request."""
        ...


def segment(value: str | int | date | datetime) -> str:
    """Encode one path segment, preserving EEX's timestamp and symbol syntax."""
    if isinstance(value, (date, datetime)):
        value = value.isoformat()
    return quote(str(value), safe="+:TZ")


def params(**values: Any) -> dict[str, Any]:
    """Omit absent query values and serialize OpenAPI comma-separated arrays."""
    return {
        key: ",".join(str(item) for item in value)
        if isinstance(value, (list, tuple))
        else value
        for key, value in values.items()
        if value is not None
    }


class BaseAPI:
    """Base for adapters following the snapshots listed in ``specs/README.md``."""

    def __init__(self, transport: Transport) -> None:
        self._transport = transport

    def _get(self, path: str, **query: Any) -> Any:
        return self._transport.get(path, params(**query))
