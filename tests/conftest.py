"""Shared fixtures for offline contract tests and optional live API tests."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import yaml

from eex_datasource import EEXClient
from eex_datasource.config import Settings


@pytest.fixture(scope="session")
def api_specs() -> dict[str, Any]:
    """Load the published OpenAPI snapshots without contacting EEX."""
    directory = Path(__file__).parents[1] / "specs"
    return {
        name: yaml.safe_load((directory / f"{name}.yaml").read_text())
        for name in ("derivatives", "gas_spot", "auctions", "index", "transparency")
    }


@pytest.fixture(scope="module")
def eex_client() -> Iterator[EEXClient]:
    """Share a paced live client; no token means no network requests."""
    settings = Settings.from_env()
    if not settings.access_token or not settings.access_token.strip():
        pytest.skip("set EEX_ACCESS_TOKEN to run live EEX API tests")
    with EEXClient(
        settings.access_token,
        base_url=settings.base_url,
        timeout=settings.timeout,
        # Do not allow a local test configuration to violate EEX's live limit.
        request_interval=max(1.05, settings.request_interval),
        max_retries=1,
    ) as client:
        yield client
