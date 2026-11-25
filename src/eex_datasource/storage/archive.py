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
    content_hash: str
    relative_path: str
    compressed_size: int
    uncompressed_size: int


class Archive:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    @staticmethod
    def content_hash(body: bytes) -> str:
        return hashlib.sha256(body).hexdigest()

    def store(self, body: bytes) -> ArchivedObject:
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
        with gzip.open(self.root / relative_path, "rb") as source:
            return source.read()

    def load_json(self, relative_path: str) -> Any:
        return json.loads(self.load_bytes(relative_path))

    def exists(self, relative_path: str | None) -> bool:
        return bool(relative_path and (self.root / relative_path).is_file())

    def delete(self, relative_path: str) -> None:
        (self.root / relative_path).unlink(missing_ok=True)
