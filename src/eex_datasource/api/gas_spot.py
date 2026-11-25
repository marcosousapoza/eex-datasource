"""Gas Spot endpoints."""

from __future__ import annotations

from typing import Any

from .base import BaseAPI, segment


class GasSpotAPI(BaseAPI):
    def commodities(self) -> list[str]:
        return self._get("/rd/spot/")

    def areas(self, commodity: str = "NATGAS") -> list[str]:
        return self._get(f"/rd/spot/{segment(commodity)}/")

    def trade_dates(self, commodity: str, area: str) -> list[str]:
        return self._get(f"/rd/spot/{segment(commodity)}/{segment(area)}/")

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
        path = f"/rd/spot/{segment(commodity)}/{segment(area)}/{segment(trade_date)}"
        if shortcode is not None:
            path += f"/{segment(shortcode)}"
        return self._get(path, limit=limit, **filters)

    def shortcodes(self, commodity: str, area: str, trade_date: str) -> list[str]:
        return self._get(
            f"/rd/spot/{segment(commodity)}/{segment(area)}/{segment(trade_date)}/"
        )

    def _day_resource(
        self,
        resource: str,
        commodity: str,
        area: str,
        trade_date: str,
        shortcode: str | None = None,
        *,
        limit: int = 60_000,
        **filters: Any,
    ) -> list[dict[str, Any]]:
        path = (
            f"/{resource}/spot/{segment(commodity)}/{segment(area)}/"
            f"{segment(trade_date)}"
        )
        if shortcode is not None:
            path += f"/{segment(shortcode)}"
        return self._get(path, limit=limit, **filters)

    def trades(self, *args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        return self._day_resource("trd", *args, **kwargs)

    def top_of_book(self, *args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        return self._day_resource("tob", *args, **kwargs)

    def statistics(self, *args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        return self._day_resource("stat", *args, **kwargs)

    def settlements(self, *args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        return self._day_resource("spr", *args, **kwargs)

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
        plural = {"trd": "trds", "stat": "stats", "spr": "sprs"}
        if resource not in plural:
            raise ValueError(
                "resource must be 'trd', 'stat', or 'spr'; use "
                "top_of_book_history() for order-book history"
            )
        path = f"/{plural[resource]}/spot/{segment(commodity)}/{segment(area)}"
        if shortcode is not None:
            path += f"/{segment(shortcode)}"
        return self._get(
            path,
            **{"from": date_from, "to": date_to, "limit": limit, **filters},
        )

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
        return self._get(
            f"/tobs/spot/{segment(commodity)}/{segment(area)}/"
            f"{segment(trade_date)}/{segment(shortcode)}",
            timeFrom=time_from,
            timeTo=time_to,
            limit=limit,
            **filters,
        )

    def market_day(
        self,
        commodity: str,
        area: str,
        trade_date: str,
        *,
        limit: int = 60_000,
    ) -> dict[str, Any]:
        return {
            "reference": self.reference_data(commodity, area, trade_date, limit=limit),
            "trades": self.trades(commodity, area, trade_date, limit=limit),
            "top_of_book": self.top_of_book(commodity, area, trade_date, limit=limit),
            "statistics": self.statistics(commodity, area, trade_date, limit=limit),
            "settlements": self.settlements(commodity, area, trade_date, limit=limit),
        }
