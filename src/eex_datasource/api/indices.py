"""EEX index endpoints from ``specs/index.yaml``.

Source: https://eds.eex-group.com/api-spec/index.yaml
"""

from __future__ import annotations

from typing import Any

from .base import BaseAPI, segment


class IndicesAPI(BaseAPI):
    """Discover index definitions and retrieve daily or historical observations."""

    def commodities(self) -> list[str]:
        """List entitled index commodities."""
        return self._get("/idx/")

    def areas(self, commodity: str) -> list[str]:
        """List index areas for a commodity."""
        return self._get(f"/idx/{segment(commodity)}/")

    def indexes(self, commodity: str, area: str) -> list[str]:
        """List available index codes for a commodity and area."""
        return self._get(f"/idx/{segment(commodity)}/{segment(area)}/")

    def trade_dates(self, commodity: str, area: str, index: str) -> list[str]:
        """List dates on which the specified index is available."""
        return self._get(f"/idx/{segment(commodity)}/{segment(area)}/{segment(index)}/")

    def day(
        self,
        commodity: str,
        area: str,
        index: str,
        trade_date: str,
        *,
        limit: int = 60_000,
    ) -> list[dict[str, Any]]:
        """Fetch ``/idx`` observations for one business date."""
        return self._get(
            f"/idx/{segment(commodity)}/{segment(area)}/{segment(index)}/"
            f"{segment(trade_date)}",
            limit=limit,
        )

    def series(
        self,
        commodity: str,
        area: str,
        index: str,
        *,
        date_from: str,
        date_to: str,
        limit: int = 60_000,
    ) -> list[dict[str, Any]]:
        """Fetch ``/idxs`` observations between the required date bounds."""
        return self._get(
            f"/idxs/{segment(commodity)}/{segment(area)}/{segment(index)}",
            **{"from": date_from, "to": date_to, "limit": limit},
        )
