from __future__ import annotations

from datetime import date, time
from typing import Any

from .._utils import clean_params, iso_date, iso_time, segment
from ..result import Record, Result
from .base import Service


class GasSpotService(Service):
    _rd = "/rd/spot"

    def commodities(self) -> list[str]:
        return self._identifiers(f"{self._rd}/", "gas_spot.commodities")

    def areas(self, commodity: str) -> list[str]:
        return self._identifiers(f"{self._rd}/{segment(commodity, 'commodity')}/", "gas_spot.areas")

    def trading_dates(self, commodity: str, area: str) -> list[str]:
        return self._identifiers(
            self._market(self._rd, commodity, area) + "/", "gas_spot.trading_dates"
        )

    def shortcodes(self, commodity: str, area: str, trade_date: date | str) -> list[str]:
        return self._identifiers(
            self._dated(self._rd, commodity, area, trade_date) + "/", "gas_spot.shortcodes"
        )

    def reference_data(
        self,
        commodity: str,
        area: str,
        trade_date: date | str,
        *,
        shortcode: str | None = None,
        limit: int | None = None,
        fields: list[str] | None = None,
        allow_partial: bool = False,
    ) -> Result[Record]:
        path = self._select(self._dated(self._rd, commodity, area, trade_date), shortcode)
        return self._records(
            path,
            "gas_spot.reference_data",
            clean_params(limit=limit, fields=fields),
            allow_partial=allow_partial,
        )

    def trades(
        self,
        commodity: str,
        area: str,
        trade_date: date | str,
        *,
        shortcode: str | None = None,
        time_from: time | str | None = None,
        time_to: time | str | None = None,
        limit: int | None = None,
        fields: list[str] | None = None,
        allow_partial: bool = False,
    ) -> Result[Record]:
        path = self._select(self._dated("/trd/spot", commodity, area, trade_date), shortcode)
        return self._records(
            path,
            "gas_spot.trades",
            clean_params(
                timeFrom=iso_time(time_from, "time_from") if time_from is not None else None,
                timeTo=iso_time(time_to, "time_to") if time_to is not None else None,
                limit=limit,
                fields=fields,
            ),
            allow_partial=allow_partial,
        )

    def trade_history(
        self,
        commodity: str,
        area: str,
        date_from: date | str,
        date_to: date | str | None = None,
        *,
        shortcode: str | None = None,
        limit: int | None = None,
        fields: list[str] | None = None,
        allow_partial: bool = False,
    ) -> Result[Record]:
        path = self._select(self._market("/trds/spot", commodity, area), shortcode)
        params = clean_params(
            **{
                "from": iso_date(date_from, "date_from"),
                "to": iso_date(date_to, "date_to") if date_to is not None else None,
            },
            limit=limit,
            fields=fields,
        )
        return self._records(path, "gas_spot.trade_history", params, allow_partial=allow_partial)

    def top_of_book(
        self,
        commodity: str,
        area: str,
        trade_date: date | str,
        shortcode: str,
        *,
        time_to: time | str | None = None,
        fields: list[str] | None = None,
    ) -> Record:
        path = self._select(self._dated("/tob/spot", commodity, area, trade_date), shortcode)
        return self._record(
            path,
            "gas_spot.top_of_book",
            clean_params(
                timeTo=iso_time(time_to, "time_to") if time_to is not None else None,
                fields=fields,
            ),
        )

    def top_of_book_history(
        self,
        commodity: str,
        area: str,
        trade_date: date | str,
        shortcode: str,
        time_from: time | str,
        *,
        time_to: time | str | None = None,
        limit: int | None = None,
        fields: list[str] | None = None,
        allow_partial: bool = False,
    ) -> Result[Record]:
        path = self._select(self._dated("/tobs/spot", commodity, area, trade_date), shortcode)
        return self._records(
            path,
            "gas_spot.top_of_book_history",
            clean_params(
                timeFrom=iso_time(time_from, "time_from"),
                timeTo=iso_time(time_to, "time_to") if time_to is not None else None,
                limit=limit,
                fields=fields,
            ),
            allow_partial=allow_partial,
        )

    def statistics(
        self, commodity: str, area: str, trade_date: date | str, **kwargs: Any
    ) -> Result[Record]:
        return self._dated_dataset(
            "/stat/spot", "gas_spot.statistics", commodity, area, trade_date, **kwargs
        )

    def statistics_history(
        self, commodity: str, area: str, date_from: date | str, date_to: date | str, **kwargs: Any
    ) -> Result[Record]:
        return self._history_dataset(
            "/stats/spot",
            "gas_spot.statistics_history",
            commodity,
            area,
            date_from,
            date_to,
            **kwargs,
        )

    def settlements(
        self, commodity: str, area: str, trade_date: date | str, **kwargs: Any
    ) -> Result[Record]:
        return self._dated_dataset(
            "/spr/spot", "gas_spot.settlements", commodity, area, trade_date, **kwargs
        )

    def settlement_history(
        self, commodity: str, area: str, date_from: date | str, date_to: date | str, **kwargs: Any
    ) -> Result[Record]:
        return self._history_dataset(
            "/sprs/spot",
            "gas_spot.settlement_history",
            commodity,
            area,
            date_from,
            date_to,
            **kwargs,
        )

    def _dated_dataset(
        self,
        root: str,
        operation: str,
        commodity: str,
        area: str,
        trade_date: date | str,
        *,
        shortcode: str | None = None,
        limit: int | None = None,
        fields: list[str] | None = None,
        allow_partial: bool = False,
    ) -> Result[Record]:
        path = self._select(self._dated(root, commodity, area, trade_date), shortcode)
        return self._records(
            path, operation, clean_params(limit=limit, fields=fields), allow_partial=allow_partial
        )

    def _history_dataset(
        self,
        root: str,
        operation: str,
        commodity: str,
        area: str,
        date_from: date | str,
        date_to: date | str,
        *,
        shortcode: str | None = None,
        limit: int | None = None,
        fields: list[str] | None = None,
        allow_partial: bool = False,
    ) -> Result[Record]:
        path = self._select(self._market(root, commodity, area), shortcode)
        params = clean_params(
            **{"from": iso_date(date_from, "date_from"), "to": iso_date(date_to, "date_to")},
            limit=limit,
            fields=fields,
        )
        return self._records(path, operation, params, allow_partial=allow_partial)

    @staticmethod
    def _market(root: str, commodity: str, area: str) -> str:
        return f"{root}/{segment(commodity, 'commodity')}/{segment(area, 'area')}"

    @classmethod
    def _dated(cls, root: str, commodity: str, area: str, value: date | str) -> str:
        return cls._market(root, commodity, area) + f"/{iso_date(value, 'trade_date')}"

    @staticmethod
    def _select(path: str, shortcode: str | None) -> str:
        return path if shortcode is None else path + f"/{segment(shortcode, 'shortcode')}"
