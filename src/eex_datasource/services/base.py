from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..exceptions import ResponseParsingError, SuspectedTruncationError
from ..result import Record, Result, metadata
from ..transport import Transport


class Service:
    def __init__(self, transport: Transport, *, record_cap: int = 60_000) -> None:
        self._transport = transport
        self._record_cap = record_cap

    def _identifiers(
        self, path: str, operation: str, params: Mapping[str, Any] | None = None
    ) -> list[str]:
        payload, _ = self._transport.request(path, operation=operation, params=params)
        if not isinstance(payload, list) or any(not isinstance(item, str) for item in payload):
            raise ResponseParsingError(
                "Expected a JSON array of identifiers",
                operation=operation,
                parameters=dict(params or {}),
            )
        return payload

    def _record(self, path: str, operation: str, params: Mapping[str, Any] | None = None) -> Record:
        payload, _ = self._transport.request(path, operation=operation, params=params)
        if not isinstance(payload, dict):
            raise ResponseParsingError(
                "Expected a JSON object", operation=operation, parameters=dict(params or {})
            )
        return Record(payload)

    def _records(
        self,
        path: str,
        operation: str,
        params: Mapping[str, Any] | None = None,
        *,
        allow_partial: bool = False,
    ) -> Result[Record]:
        sent = dict(params or {})
        payload, request_id = self._transport.request(path, operation=operation, params=sent)
        if not isinstance(payload, list) or any(not isinstance(item, dict) for item in payload):
            raise ResponseParsingError(
                "Expected a JSON array of objects", operation=operation, parameters=sent
            )
        records = tuple(Record(item) for item in payload)
        requested_limit = sent.get("limit")
        threshold = int(requested_limit) if requested_limit is not None else self._record_cap
        truncated = len(records) >= threshold
        result = Result(
            records,
            metadata(
                operation,
                path,
                sent,
                len(records),
                truncated=truncated,
                request_id=request_id,
            ),
            payload,
        )
        if truncated and not allow_partial:
            raise SuspectedTruncationError(
                result,
                operation=operation,
                parameters=sent,
                request_id=request_id,
            )
        return result
