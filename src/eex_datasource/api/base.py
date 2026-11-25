"""Shared adapter helpers."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Protocol
from urllib.parse import quote


class Transport(Protocol):
    def get(self, path: str, params: dict[str, Any] | None = None) -> Any: ...


def segment(value: str | int | date | datetime) -> str:
    if isinstance(value, (date, datetime)):
        value = value.isoformat()
    return quote(str(value), safe="+:TZ")


def params(**values: Any) -> dict[str, Any]:
    return {
        key: ",".join(str(item) for item in value)
        if isinstance(value, (list, tuple))
        else value
        for key, value in values.items()
        if value is not None
    }


class BaseAPI:
    def __init__(self, transport: Transport) -> None:
        self._transport = transport

    def _get(self, path: str, **query: Any) -> Any:
        return self._transport.get(path, params(**query))
