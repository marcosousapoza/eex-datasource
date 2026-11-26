"""Content-addressed, deterministic gzip JSON response archive."""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class ArchivedObject:
    """Content digest, relative location, and sizes of a stored gzip body."""

    content_hash: str
    relative_path: str
    compressed_size: int
    uncompressed_size: int


class Archive:
    """Store exact API bytes in atomic, content-addressed gzip objects."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    @staticmethod
    def content_hash(body: bytes) -> str:
        """Return the SHA-256 of the original, uncompressed response bytes."""
        return hashlib.sha256(body).hexdigest()

    def store(self, body: bytes) -> ArchivedObject:
        """Atomically store a body, reusing an existing object with its digest."""
        digest = self.content_hash(body)
        relative = Path("sha256") / digest[:2] / digest[2:4] / f"{digest}.json.gz"
        destination = self.root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            fd, temporary_name = tempfile.mkstemp(
                prefix=f".{digest}.", dir=destination.parent
            )
            try:
                with (
                    os.fdopen(fd, "wb") as raw,
                    gzip.GzipFile(
                        filename="", mode="wb", fileobj=raw, mtime=0
                    ) as compressed,
                ):
                    compressed.write(body)
                os.replace(temporary_name, destination)
            finally:
                if os.path.exists(temporary_name):
                    os.unlink(temporary_name)
        return ArchivedObject(
            content_hash=digest,
            relative_path=relative.as_posix(),
            compressed_size=destination.stat().st_size,
            uncompressed_size=len(body),
        )

    def load_bytes(self, relative_path: str) -> bytes:
        """Decompress an object path relative to the archive root."""
        with gzip.open(self.root / relative_path, "rb") as source:
            return source.read()

    def load_json(self, relative_path: str) -> Any:
        """Decode JSON from an archived response."""
        return json.loads(self.load_bytes(relative_path))

    def exists(self, relative_path: str | None) -> bool:
        """Return whether a non-evicted object exists on disk."""
        return bool(relative_path and (self.root / relative_path).is_file())

    def delete(self, relative_path: str) -> None:
        """Remove a body if present, leaving database metadata untouched."""
        (self.root / relative_path).unlink(missing_ok=True)
