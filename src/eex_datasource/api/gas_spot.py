"""Gas Spot endpoints from ``specs/gas_spot.yaml``.

Source: https://eds.eex-group.com/api-spec/gas_spot.yaml
"""

from __future__ import annotations

from typing import Any

from .base import segment
from .market import MarketAPI


class GasSpotAPI(MarketAPI):
    """Discover and retrieve gas spot contracts and daily market records."""

    market = "spot"

    def areas(self, commodity: str = "NATGAS") -> list[str]:
        """List gas market areas; the specified commodity defaults to NATGAS."""
        return super().areas(commodity)

    def reference_data(
        self,
        commodity: str,
        area: str,
        trade_date: str,
        shortcode: str | None = None,
        *,
        limit: int = 60_000,
        **filters: Any,
    ) -> list[dict[str, Any]]:
        """Fetch ``/rd`` contracts, optionally scoped to a gas shortcode.

        Extra filters use OpenAPI query names, such as ``fields``.
        """
        return self._day_resource(
            "rd",
            commodity,
            area,
            trade_date,
            shortcode,
            limit=limit,
            **filters,
        )

    def history(
        self,
        resource: str,
        commodity: str,
        area: str,
        shortcode: str | None = None,
        *,
        date_from: str | None = None,
        date_to: str | None = None,
        limit: int = 60_000,
        **filters: Any,
    ) -> list[dict[str, Any]]:
        """Fetch a date range for ``trd``, ``stat``, or ``spr`` records."""
        return self._history(
            resource,
            commodity,
            area,
            shortcode,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
            **filters,
        )

    def top_of_book(
        self,
        commodity: str,
        area: str,
        trade_date: str,
        shortcode: str | None = None,
        *,
        limit: int = 60_000,
        **filters: Any,
    ) -> list[dict[str, Any]]:
        """Fetch latest ``/tob`` snapshots, discovering shortcodes if omitted.

        The Gas Spot OpenAPI only defines a shortcode-scoped snapshot route.
        ``limit`` is accepted for pooled calls but is not sent to this route.
        """
        shortcodes = (
            [shortcode]
            if shortcode is not None
            else self.shortcodes(commodity, area, trade_date)
        )
        return [
            record
            for code in shortcodes
            for record in self._day_resource(
                "tob", commodity, area, trade_date, code, limit=limit, **filters
            )
        ]

    def top_of_book_history(
        self,
        commodity: str,
        area: str,
        trade_date: str,
        shortcode: str,
        *,
        time_from: str,
        time_to: str | None = None,
        limit: int = 60_000,
        **filters: Any,
    ) -> list[dict[str, Any]]:
        """Fetch every ``/tobs`` change for a shortcode in market-time bounds."""
        return self._get(
            f"/tobs/spot/{segment(commodity)}/{segment(area)}/"
            f"{segment(trade_date)}/{segment(shortcode)}",
            timeFrom=time_from,
            timeTo=time_to,
            limit=limit,
            **filters,
        )
