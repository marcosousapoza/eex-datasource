from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import quote

from .exceptions import InvalidRequestError


def segment(value: object, name: str) -> str:
    text = str(value)
    if not text or text in {".", ".."}:
        raise InvalidRequestError(f"{name} must be a non-empty identifier")
    return quote(text, safe="")


def iso_date(value: date | str, name: str) -> str:
    if isinstance(value, datetime):
        raise InvalidRequestError(f"{name} must be a date, not a datetime")
    if isinstance(value, date):
        return value.isoformat()
    if not isinstance(value, str):
        raise InvalidRequestError(f"{name} must be a date or ISO date string")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise InvalidRequestError(f"{name} must be an ISO date in YYYY-MM-DD form") from exc
    if parsed.isoformat() != value:
        raise InvalidRequestError(f"{name} must be an ISO date in YYYY-MM-DD form")
    return value


def iso_time(value: time | str, name: str) -> str:
    """Normalize a time-only argument without discarding a date component."""
    if isinstance(value, datetime):
        raise InvalidRequestError(f"{name} must be a time, not a datetime")
    if isinstance(value, time):
        return value.isoformat()
    if not isinstance(value, str):
        raise InvalidRequestError(f"{name} must be a time or ISO time string")
    try:
        time.fromisoformat(value)
    except ValueError as exc:
        raise InvalidRequestError(f"{name} must be a valid ISO time") from exc
    return value


def clean_params(**values: Any) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in values.items():
        if value is None:
            continue
        if isinstance(value, (datetime, date)):
            result[key] = value.isoformat()
        elif isinstance(value, (list, tuple)):
            result[key] = ",".join(map(str, value))
        else:
            result[key] = value
    return result


def decode_number(value: Any) -> Any:
    """Utility available to model parsers that need exact decimal conversion."""
    if not isinstance(value, str):
        return value
    try:
        return Decimal(value)
    except InvalidOperation:
        return value
