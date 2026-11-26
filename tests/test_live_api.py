"""Small read-only checks against EEX; enabled only by EEX_ACCESS_TOKEN.

Endpoints and response shapes follow the snapshots in ``specs/``. Dates and
identifiers are discovered instead of assuming a particular subscription or
historical retention period. Authentication/server failures remain failures.
"""

from __future__ import annotations

from typing import Any

import pytest

from eex_datasource import EEXClient
from eex_datasource.errors import EEXAPIError

pytestmark = pytest.mark.integration


def available(values: Any, description: str) -> list[str]:
    """Check the documented discovery shape; skip empty entitlements."""
    assert isinstance(values, list)
    assert all(isinstance(value, str) for value in values)
    if not values:
        pytest.skip(f"no entitled {description} returned")
    return values


@pytest.mark.parametrize(
    "name",
    ["derivatives", "gas_spot", "auctions", "indices", "transparency"],
)
def test_live_discovery_and_data(eex_client: EEXClient, name: str) -> None:
    """Check discovery and bounded data (or flat transparency master data)."""
    api = getattr(eex_client, name)
    try:
        commodity = available(api.commodities(), f"{name} commodities")[0]
        area = available(api.areas(commodity), f"{name} areas")[0]
        if name == "indices":
            index = available(api.indexes(commodity, area), "indices")[0]
            day = max(available(api.trade_dates(commodity, area, index), "index dates"))
            records = api.day(commodity, area, index, day, limit=1)
        else:
            dates = (
                api.auction_dates
                if name == "auctions"
                else api.validity_dates
                if name == "transparency"
                else api.trade_dates
            )
            day = max(available(dates(commodity, area), f"{name} dates"))
            if name == "auctions":
                records = api.results(commodity, area, day, limit=1)
            elif name == "transparency":
                # Reference trees do not support limit; avoid downloading one.
                records = api.companies(commodity, area, day, fields=["companyID"])
            else:
                records = api.reference_data(commodity, area, day, limit=1)
    except EEXAPIError as exc:
        if exc.status_code == 403:
            pytest.skip(f"token is not entitled to {name}")
        raise

    assert isinstance(records, list)
    assert records, "a discovered dataset should contain at least one record"
    assert all(isinstance(record, dict) for record in records)
