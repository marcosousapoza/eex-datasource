"""Archive verification and retention operations."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .archive import Archive
from .models import ArchiveObject

logger = logging.getLogger(__name__)


def verify_archive(session: Session, archive: Archive) -> tuple[int, int]:
    """Return counts of checked and missing/hash-mismatched archive objects."""
    checked = 0
    invalid = 0
    for item in session.scalars(
        select(ArchiveObject).where(ArchiveObject.relative_path.is_not(None))
    ):
        checked += 1
        if not archive.exists(item.relative_path):
            logger.error("Missing archive object %s", item.content_hash)
            invalid += 1
            continue
        body = archive.load_bytes(item.relative_path or "")
        if archive.content_hash(body) != item.content_hash:
            logger.error("Hash mismatch for %s", item.content_hash)
            invalid += 1
    return checked, invalid


def prune_archive(session: Session, archive: Archive, older_than: timedelta) -> int:
    """Evict bodies older than a duration; commit metadata and return the count."""
    cutoff = datetime.now(UTC) - older_than
    count = 0
    for item in session.scalars(
        select(ArchiveObject).where(
            ArchiveObject.relative_path.is_not(None),
            ArchiveObject.created_at < cutoff,
        )
    ):
        archive.delete(item.relative_path or "")
        item.relative_path = None
        item.evicted_at = datetime.now(UTC)
        count += 1
    session.commit()
    return count
