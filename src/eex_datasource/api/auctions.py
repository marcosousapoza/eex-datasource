"""EU ETS auction endpoints."""

from __future__ import annotations

from typing import Any

from .base import BaseAPI, segment


class AuctionsAPI(BaseAPI):
    def commodities(self) -> list[str]:
        return self._get("/rd/auctions/")

    def areas(self, commodity: str) -> list[str]:
        return self._get(f"/rd/auctions/{segment(commodity)}/")

    def auction_dates(self, commodity: str, area: str) -> list[str]:
        return self._get(f"/rd/auctions/{segment(commodity)}/{segment(area)}/")

    def reference_data(
        self,
        commodity: str,
        area: str,
        auction_date: str,
        auction_id: int | None = None,
        *,
        limit: int = 60_000,
    ) -> list[dict[str, Any]]:
        path = (
            f"/rd/auctions/{segment(commodity)}/{segment(area)}/{segment(auction_date)}"
        )
        if auction_id is not None:
            path += f"/{segment(auction_id)}"
        return self._get(path, limit=limit)

    def auction_ids(self, commodity: str, area: str, auction_date: str) -> list[int]:
        return self._get(
            f"/rd/auctions/{segment(commodity)}/{segment(area)}/"
            f"{segment(auction_date)}/"
        )

    def _day_resource(
        self,
        resource: str,
        commodity: str,
        area: str,
        auction_date: str,
        auction_id: int | None = None,
        *,
        limit: int = 60_000,
    ) -> list[dict[str, Any]]:
        path = (
            f"/{resource}/auctions/{segment(commodity)}/{segment(area)}/"
            f"{segment(auction_date)}"
        )
        if auction_id is not None:
            path += f"/{segment(auction_id)}"
        return self._get(path, limit=limit)

    def results(self, *args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        return self._day_resource("rslt", *args, **kwargs)

    def revenues(self, *args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        return self._day_resource("rev", *args, **kwargs)

    def history(
        self,
        resource: str,
        commodity: str,
        area: str,
        *,
        date_from: str | None = None,
        date_to: str | None = None,
        limit: int = 60_000,
    ) -> list[dict[str, Any]]:
        plural = {"rslt": "rslts", "rev": "revs"}[resource]
        return self._get(
            f"/{plural}/auctions/{segment(commodity)}/{segment(area)}",
            **{"from": date_from, "to": date_to, "limit": limit},
        )

    def auction_day(
        self,
        commodity: str,
        area: str,
        auction_date: str,
        *,
        limit: int = 60_000,
    ) -> dict[str, Any]:
        return {
            "reference": self.reference_data(
                commodity, area, auction_date, limit=limit
            ),
            "results": self.results(commodity, area, auction_date, limit=limit),
            "revenues": self.revenues(commodity, area, auction_date, limit=limit),
        }
