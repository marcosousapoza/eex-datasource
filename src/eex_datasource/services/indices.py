from __future__ import annotations

from datetime import date

from .._utils import clean_params, iso_date, segment
from ..result import Record, Result
from .base import Service


class IndicesService(Service):
    _root = "/idx"

    def commodities(self) -> list[str]:
        return self._identifiers(f"{self._root}/", "indices.commodities")

    def areas(self, commodity: str) -> list[str]:
        return self._identifiers(
            f"{self._root}/{segment(commodity, 'commodity')}/", "indices.areas"
        )

    def indices(self, commodity: str, area: str) -> list[str]:
        return self._identifiers(self._market(self._root, commodity, area) + "/", "indices.indices")

    def trading_dates(self, commodity: str, area: str, index: str) -> list[str]:
        path = self._market(self._root, commodity, area) + f"/{segment(index, 'index')}/"
        return self._identifiers(path, "indices.trading_dates")

    def values(
        self,
        commodity: str,
        area: str,
        index: str,
        trade_date: date | str,
        *,
        delivery_day: date | str | None = None,
        limit: int | None = None,
        fields: list[str] | None = None,
        allow_partial: bool = False,
    ) -> Result[Record]:
        path = self._market(self._root, commodity, area)
        path += f"/{segment(index, 'index')}/{iso_date(trade_date, 'trade_date')}"
        params = clean_params(
            deliveryDay=iso_date(delivery_day, "delivery_day") if delivery_day else None,
            limit=limit,
            fields=fields,
        )
        return self._records(path, "indices.values", params, allow_partial=allow_partial)

    def history(
        self,
        commodity: str,
        area: str,
        index: str,
        date_from: date | str,
        date_to: date | str,
        *,
        delivery_day: date | str | None = None,
        limit: int | None = None,
        fields: list[str] | None = None,
        allow_partial: bool = False,
    ) -> Result[Record]:
        path = self._market("/idxs", commodity, area) + f"/{segment(index, 'index')}"
        params = clean_params(
            deliveryDay=iso_date(delivery_day, "delivery_day") if delivery_day else None,
            **{"from": iso_date(date_from, "date_from"), "to": iso_date(date_to, "date_to")},
            limit=limit,
            fields=fields,
        )
        return self._records(path, "indices.history", params, allow_partial=allow_partial)

    @staticmethod
    def _market(root: str, commodity: str, area: str) -> str:
        return f"{root}/{segment(commodity, 'commodity')}/{segment(area, 'area')}"
