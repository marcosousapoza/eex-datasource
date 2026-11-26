"""Configuration loaded from explicit values or environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Settings:
    """Immutable client/storage settings; see the README configuration table."""

    access_token: str | None = None
    database_url: str = "sqlite:///eex-datasource.db"
    archive_dir: Path = Path("eex-archive")
    base_url: str = "https://api.eex-group.com/v2"
    request_interval: float = 1.05
    timeout: float = 60.0
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> Settings:
        """Load EEX_* environment variables, falling back to package defaults."""
        return cls(
            access_token=os.getenv("EEX_ACCESS_TOKEN"),
            database_url=os.getenv("EEX_DATABASE_URL", "sqlite:///eex-datasource.db"),
            archive_dir=Path(os.getenv("EEX_ARCHIVE_DIR", "eex-archive")),
            base_url=os.getenv("EEX_BASE_URL", "https://api.eex-group.com/v2").rstrip(
                "/"
            ),
            request_interval=float(os.getenv("EEX_REQUEST_INTERVAL", "1.05")),
            timeout=float(os.getenv("EEX_TIMEOUT", "60")),
            log_level=os.getenv("EEX_LOG_LEVEL", "INFO").upper(),
        )
