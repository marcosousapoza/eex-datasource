"""Shared Derivatives and Gas Spot operations.

See ``specs/derivatives.yaml`` and ``specs/gas_spot.yaml``. Trailing slashes
select discovery endpoints, while paths without them return data records.
"""

from __future__ import annotations

from typing import Any

from .base import BaseAPI, segment


class MarketAPI(BaseAPI):
    """Common market operations; subclasses supply the OpenAPI market name."""

    market: str

    def _path(self, resource: str, *parts: str | int | None) -> str:
        """Build a hierarchical path without silently skipping a parent."""
        present = []
        for part in parts:
            if part is None:
                break
            present.append(segment(part))
        if any(part is not None for part in parts[len(present) :]):
            raise ValueError("maturity requires shortcode")
        return "/".join(("", resource, self.market, *present))

    def commodities(self) -> list[str]:
        """List entitled commodities (``GET /rd/{market}/``)."""
        return self._get(self._path("rd") + "/")

    def areas(self, commodity: str) -> list[str]:
        """List entitled market areas for a commodity."""
        return self._get(self._path("rd", commodity) + "/")

    def trade_dates(self, commodity: str, area: str) -> list[str]:
        """List available business dates, not calendar dates."""
        return self._get(self._path("rd", commodity, area) + "/")

    def shortcodes(self, commodity: str, area: str, trade_date: str) -> list[str]:
        """List available product shortcodes for a business date."""
        return self._get(self._path("rd", commodity, area, trade_date) + "/")

    def _day_resource(
        self,
        resource: str,
        commodity: str,
        area: str,
        trade_date: str,
        shortcode: str | None = None,
        maturity: str | int | None = None,
        *,
        limit: int = 60_000,
        **filters: Any,
    ) -> list[dict[str, Any]]:
        if self.market == "spot" and maturity is not None:
            raise ValueError("gas spot endpoints do not accept maturity")
        path = self._path(resource, commodity, area, trade_date, shortcode, maturity)
        # Snapshot TOB routes and scoped derivative reference routes have no
        # limit parameter in their OpenAPI definitions.
        if resource == "tob" or (
            self.market == "derivatives" and resource == "rd" and shortcode is not None
        ):
            return self._get(path, **filters)
        return self._get(path, limit=limit, **filters)

    def trades(self, *args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        """Fetch ``/trd`` records; arguments follow ``reference_data``."""
        return self._day_resource("trd", *args, **kwargs)

    def top_of_book(self, *args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        """Fetch latest ``/tob`` snapshots, not every intraday change.

        Arguments follow ``reference_data``. For derivatives, the fourth path
        argument can also be a rolling symbol (e.g. ``DEBM+1``); ``limit`` is
        accepted for pooled calls but is not sent to snapshot endpoints.
        """
        return self._day_resource("tob", *args, **kwargs)

    def statistics(self, *args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        """Fetch ``/stat`` records; arguments follow ``reference_data``."""
        return self._day_resource("stat", *args, **kwargs)

    def settlements(self, *args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        """Fetch ``/spr`` records; arguments follow ``reference_data``."""
        return self._day_resource("spr", *args, **kwargs)

    def _history(
        self,
        resource: str,
        *parts: str | int | None,
        date_from: str | None,
        date_to: str | None,
        limit: int,
        **filters: Any,
    ) -> list[dict[str, Any]]:
        plural = {"trd": "trds", "stat": "stats", "spr": "sprs"}
        if resource not in plural:
            raise ValueError(
                "resource must be 'trd', 'stat', or 'spr'; use "
                "top_of_book_history() for order-book history"
            )
        return self._get(
            self._path(plural[resource], *parts),
            **{"from": date_from, "to": date_to, "limit": limit, **filters},
        )

    def market_day(
        self,
        commodity: str,
        area: str,
        trade_date: str,
        *,
        limit: int = 60_000,
    ) -> dict[str, Any]:
        """Fetch reference data and the four daily market resources sequentially."""
        return {
            name: getattr(self, method)(commodity, area, trade_date, limit=limit)
            for name, method in (
                ("reference", "reference_data"),
                ("trades", "trades"),
                ("top_of_book", "top_of_book"),
                ("statistics", "statistics"),
                ("settlements", "settlements"),
            )
        }
