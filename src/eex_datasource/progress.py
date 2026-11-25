"""Optional tqdm integration without a hard dependency."""

from __future__ import annotations

from collections.abc import Iterable

try:
    from tqdm.auto import tqdm as _tqdm
except ImportError:  # pragma: no cover - depends on optional installation
    _tqdm = None


def progress[T](iterable: Iterable[T], **kwargs: object) -> Iterable[T]:
    """Wrap ``iterable`` in tqdm when the optional dependency is installed."""

    if _tqdm is None:
        return iterable
    return _tqdm(iterable, **kwargs)
