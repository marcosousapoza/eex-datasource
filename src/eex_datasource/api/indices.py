"""EEX index endpoints."""

from __future__ import annotations

from typing import Any

from .base import BaseAPI, segment


class IndicesAPI(BaseAPI):
    def commodities(self) -> list[str]:
        return self._get("/idx/")

    def areas(self, commodity: str) -> list[str]:
        return self._get(f"/idx/{segment(commodity)}/")

    def indexes(self, commodity: str, area: str) -> list[str]:
        return self._get(f"/idx/{segment(commodity)}/{segment(area)}/")

    def trade_dates(self, commodity: str, area: str, index: str) -> list[str]:
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
        return self._get(
            f"/idxs/{segment(commodity)}/{segment(area)}/{segment(index)}",
            **{"from": date_from, "to": date_to, "limit": limit},
        )
