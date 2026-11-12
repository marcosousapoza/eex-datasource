from __future__ import annotations

from datetime import date

from .._utils import clean_params, iso_date, segment
from ..result import Record, Result
from .base import Service


class AuctionsService(Service):
    _rd = "/rd/auctions"

    def commodities(self) -> list[str]:
        return self._identifiers(f"{self._rd}/", "auctions.commodities")

    def areas(self, commodity: str) -> list[str]:
        return self._identifiers(f"{self._rd}/{segment(commodity, 'commodity')}/", "auctions.areas")

    def auction_dates(self, commodity: str, area: str) -> list[str]:
        return self._identifiers(
            self._market(self._rd, commodity, area) + "/", "auctions.auction_dates"
        )

    def auction_ids(self, commodity: str, area: str, auction_date: date | str) -> list[str]:
        return self._identifiers(
            self._dated(self._rd, commodity, area, auction_date) + "/",
            "auctions.auction_ids",
        )

    def reference_data(
        self,
        commodity: str,
        area: str,
        auction_date: date | str,
        *,
        auction_id: str | None = None,
        fields: list[str] | None = None,
        allow_partial: bool = False,
    ) -> Result[Record]:
        path = self._select(self._dated(self._rd, commodity, area, auction_date), auction_id)
        return self._records(
            path,
            "auctions.reference_data",
            clean_params(fields=fields),
            allow_partial=allow_partial,
        )

    def results(
        self,
        commodity: str,
        area: str,
        auction_date: date | str,
        *,
        auction_id: str | None = None,
        limit: int | None = None,
        fields: list[str] | None = None,
        allow_partial: bool = False,
    ) -> Result[Record]:
        path = self._select(
            self._dated("/rslt/auctions", commodity, area, auction_date), auction_id
        )
        return self._records(
            path,
            "auctions.results",
            clean_params(limit=limit, fields=fields),
            allow_partial=allow_partial,
        )

    def result_history(
        self,
        commodity: str,
        area: str,
        date_from: date | str,
        date_to: date | str,
        *,
        limit: int | None = None,
        fields: list[str] | None = None,
        allow_partial: bool = False,
    ) -> Result[Record]:
        params = clean_params(
            **{"from": iso_date(date_from, "date_from"), "to": iso_date(date_to, "date_to")},
            limit=limit,
            fields=fields,
        )
        return self._records(
            self._market("/rslts/auctions", commodity, area),
            "auctions.result_history",
            params,
            allow_partial=allow_partial,
        )

    def revenues(
        self,
        commodity: str,
        area: str,
        auction_date: date | str,
        *,
        auction_id: str | None = None,
        limit: int | None = None,
        fields: list[str] | None = None,
        allow_partial: bool = False,
    ) -> Result[Record]:
        path = self._select(self._dated("/rev/auctions", commodity, area, auction_date), auction_id)
        return self._records(
            path,
            "auctions.revenues",
            clean_params(limit=limit, fields=fields),
            allow_partial=allow_partial,
        )

    def revenue_history(
        self,
        commodity: str,
        area: str,
        date_from: date | str,
        date_to: date | str,
        *,
        limit: int | None = None,
        fields: list[str] | None = None,
        allow_partial: bool = False,
    ) -> Result[Record]:
        params = clean_params(
            **{"from": iso_date(date_from, "date_from"), "to": iso_date(date_to, "date_to")},
            limit=limit,
            fields=fields,
        )
        return self._records(
            self._market("/revs/auctions", commodity, area),
            "auctions.revenue_history",
            params,
            allow_partial=allow_partial,
        )

    @staticmethod
    def _market(root: str, commodity: str, area: str) -> str:
        return f"{root}/{segment(commodity, 'commodity')}/{segment(area, 'area')}"

    @classmethod
    def _dated(cls, root: str, commodity: str, area: str, value: date | str) -> str:
        return cls._market(root, commodity, area) + f"/{iso_date(value, 'auction_date')}"

    @staticmethod
    def _select(path: str, auction_id: str | None) -> str:
        return path if auction_id is None else path + f"/{segment(auction_id, 'auction_id')}"
