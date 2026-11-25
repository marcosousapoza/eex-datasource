"""Database-backed request cache connected to the gzip archive."""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..client import EEXClient
from .archive import Archive
from .models import ApiFetch, ArchiveObject

logger = logging.getLogger(__name__)


def canonical_request_hash(path: str, query: dict[str, Any] | None) -> str:
    normalized = {
        "method": "GET",
        "path": path,
        "query": {
            key: value
            for key, value in sorted((query or {}).items())
            if value is not None
        },
        "accept": "application/json",
    }
    encoded = json.dumps(
        normalized, sort_keys=True, separators=(",", ":"), default=str
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


class CachedTransport:
    """Transport protocol implementation used by endpoint adapters."""

    def __init__(
        self,
        client: EEXClient,
        session: Session,
        archive: Archive,
        *,
        run_id: str | None = None,
        ttl: timedelta = timedelta(hours=1),
        force: bool = False,
    ) -> None:
        self.client = client
        self.session = session
        self.archive = archive
        self.run_id = run_id
        self.ttl = ttl
        self.force = force
        self.last_fetch_id: str | None = None
        self.last_cache_hit = False

    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        query = {
            key: value for key, value in (params or {}).items() if value is not None
        }
        request_hash = canonical_request_hash(path, query)
        if not self.force:
            cached = self._fresh_fetch(request_hash)
            if cached is not None:
                archive_object = self.session.get(ArchiveObject, cached.content_hash)
                if archive_object and self.archive.exists(archive_object.relative_path):
                    logger.debug("Cache hit for %s", path)
                    cached.cache_hit = True
                    self.session.commit()
                    self.last_fetch_id = cached.id
                    self.last_cache_hit = True
                    return self.archive.load_json(archive_object.relative_path or "")

        response = self.client.get_response(path, query)
        archived = self.archive.store(response.body)
        archive_object = self.session.get(ArchiveObject, archived.content_hash)
        if archive_object is None:
            archive_object = ArchiveObject(
                content_hash=archived.content_hash,
                relative_path=archived.relative_path,
                compressed_size=archived.compressed_size,
                uncompressed_size=archived.uncompressed_size,
                media_type=response.headers.get(
                    "content-type", "application/json"
                ).split(";", 1)[0],
                created_at=response.fetched_at,
                evicted_at=None,
            )
            self.session.add(archive_object)
        elif archive_object.relative_path is None:
            archive_object.relative_path = archived.relative_path
            archive_object.compressed_size = archived.compressed_size
            archive_object.evicted_at = None
        # There is no ORM relationship between the manifest rows, so flush the
        # archive object explicitly before inserting the foreign-key reference.
        self.session.flush()

        fetch_id = str(uuid.uuid4())
        fetch = ApiFetch(
            id=fetch_id,
            run_id=self.run_id,
            request_hash=request_hash,
            content_hash=archived.content_hash,
            path=path,
            query=query,
            url=response.url,
            status_code=response.status_code,
            fetched_at=response.fetched_at,
            record_count=_record_count(response.data),
            cache_hit=False,
        )
        self.session.add(fetch)
        self.session.commit()
        self.last_fetch_id = fetch_id
        self.last_cache_hit = False
        return response.data

    def _fresh_fetch(self, request_hash: str) -> ApiFetch | None:
        cutoff = datetime.now(UTC) - self.ttl
        candidate = self.session.scalars(
            select(ApiFetch)
            .where(
                ApiFetch.request_hash == request_hash,
                ApiFetch.status_code == 200,
            )
            .order_by(ApiFetch.fetched_at.desc())
            .limit(1)
        ).first()
        if candidate is None:
            return None
        fetched_at = candidate.fetched_at
        if fetched_at.tzinfo is None:
            fetched_at = fetched_at.replace(tzinfo=UTC)
        return candidate if fetched_at >= cutoff else None


def _record_count(data: Any) -> int:
    if isinstance(data, list):
        return len(data)
    if isinstance(data, dict):
        return 1
    return 0
