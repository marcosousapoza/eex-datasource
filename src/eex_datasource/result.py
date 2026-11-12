"""Predictable collection and record return types."""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Generic, TypeVar, overload

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class Record(Mapping[str, Any]):
    """An immutable record that retains every decoded source field."""

    raw: Mapping[str, Any]

    def __getitem__(self, key: str) -> Any:
        return self.raw[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self.raw)

    def __len__(self) -> int:
        return len(self.raw)

    def __getattr__(self, name: str) -> Any:
        try:
            return self.raw[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def to_pandas(self, *, flatten: bool = True, separator: str = ".") -> Any:
        """Return this record as a one-row DataFrame."""
        return _to_pandas([dict(self)], flatten=flatten, separator=separator)


@dataclass(frozen=True, slots=True)
class RequestMetadata:
    operation: str
    path: str
    retrieved_at: datetime
    parameters: Mapping[str, Any]
    record_count: int
    potentially_truncated: bool = False
    request_id: str | None = None


@dataclass(frozen=True)
class Result(Sequence[T], Generic[T]):
    """A list-like collection with request and completeness metadata."""

    records: tuple[T, ...]
    metadata: RequestMetadata
    raw: Any = field(repr=False)

    @overload
    def __getitem__(self, index: int) -> T: ...

    @overload
    def __getitem__(self, index: slice) -> tuple[T, ...]: ...

    def __getitem__(self, index: int | slice) -> T | tuple[T, ...]:
        return self.records[index]

    def __len__(self) -> int:
        return len(self.records)

    def to_pandas(self, *, flatten: bool = True, separator: str = ".") -> Any:
        """Return a DataFrame without coercing Decimal values to floats.

        Nested mappings are flattened losslessly by default. Nested collections remain object
        columns because exploding them would change record cardinality.
        """
        rows = [dict(item) if isinstance(item, Mapping) else item for item in self.records]
        return _to_pandas(rows, flatten=flatten, separator=separator)


def _to_pandas(rows: list[Any], *, flatten: bool, separator: str) -> Any:
    try:
        import pandas as pd  # type: ignore[import-untyped]
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise ImportError(
            "pandas is optional; install it with `pip install eex-datasource[pandas]`"
        ) from exc
    if flatten:
        return pd.json_normalize(rows, sep=separator)
    return pd.DataFrame(rows)


def metadata(
    operation: str,
    path: str,
    parameters: Mapping[str, Any],
    count: int,
    *,
    truncated: bool = False,
    request_id: str | None = None,
) -> RequestMetadata:
    return RequestMetadata(
        operation=operation,
        path=path,
        retrieved_at=datetime.now(UTC),
        parameters=dict(parameters),
        record_count=count,
        potentially_truncated=truncated,
        request_id=request_id,
    )
