from __future__ import annotations

from datetime import date, time
from typing import Any

from .._utils import clean_params, iso_date, iso_time, segment
from ..exceptions import InvalidRequestError
from ..result import Record, Result
from .base import Service


class DerivativesService(Service):
    """Derivatives discovery, trades, books, statistics, and settlements."""

    _root = "/rd/derivatives"

    def commodities(self) -> list[str]:
        return self._identifiers(f"{self._root}/", "derivatives.commodities")

    def areas(self, commodity: str) -> list[str]:
        path = f"{self._root}/{segment(commodity, 'commodity')}/"
        return self._identifiers(path, "derivatives.areas")

    def trading_dates(self, commodity: str, area: str) -> list[str]:
        path = f"{self._root}/{segment(commodity, 'commodity')}/{segment(area, 'area')}/"
        return self._identifiers(path, "derivatives.trading_dates")

    def shortcodes(
        self,
        commodity: str,
        area: str,
        trade_date: date | str,
        *,
        instrument_type: str | None = None,
        product_type: str | None = None,
    ) -> list[str]:
        path = self._dated(self._root, commodity, area, trade_date) + "/"
        params = clean_params(instrumentType=instrument_type, productType=product_type)
        return self._identifiers(path, "derivatives.shortcodes", params)

    def maturities(
        self,
        commodity: str,
        area: str,
        trade_date: date | str,
        shortcode: str,
        *,
        instrument_type: str | None = None,
    ) -> list[str]:
        path = self._dated(self._root, commodity, area, trade_date)
        path += f"/{segment(shortcode, 'shortcode')}/"
        return self._identifiers(
            path,
            "derivatives.maturities",
            clean_params(instrumentType=instrument_type),
        )

    def reference_data(
        self,
        commodity: str,
        area: str,
        trade_date: date | str,
        *,
        shortcode: str | None = None,
        maturity: str | None = None,
        instrument_type: str | None = None,
        product_type: str | None = None,
        limit: int | None = None,
        fields: list[str] | None = None,
        allow_partial: bool = False,
    ) -> Result[Record]:
        path = self._dated(self._root, commodity, area, trade_date)
        path = self._selectors(path, shortcode, maturity)
        params = clean_params(
            instrumentType=instrument_type,
            productType=product_type if shortcode is None else None,
            limit=limit if shortcode is None else None,
            fields=fields,
        )
        return self._records(
            path, "derivatives.reference_data", params, allow_partial=allow_partial
        )

    def trades(
        self,
        commodity: str,
        area: str,
        trade_date: date | str,
        *,
        shortcode: str | None = None,
        maturity: str | None = None,
        time_from: time | str | None = None,
        time_to: time | str | None = None,
        trade_type: str | None = None,
        instrument_type: str | None = None,
        product_type: str | None = None,
        maturity_offset: int | None = None,
        limit: int | None = None,
        fields: list[str] | None = None,
        allow_partial: bool = False,
    ) -> Result[Record]:
        path = self._selectors(
            self._dated("/trd/derivatives", commodity, area, trade_date), shortcode, maturity
        )
        params = clean_params(
            timeFrom=iso_time(time_from, "time_from") if time_from is not None else None,
            timeTo=iso_time(time_to, "time_to") if time_to is not None else None,
            trdType=trade_type,
            instrumentType=instrument_type,
            productType=product_type if shortcode is None else None,
            maturityOffset=maturity_offset if maturity is not None else None,
            limit=limit,
            fields=fields,
        )
        return self._records(path, "derivatives.trades", params, allow_partial=allow_partial)

    def trade_history(
        self,
        commodity: str,
        area: str,
        date_from: date | str,
        date_to: date | str,
        *,
        shortcode: str | None = None,
        maturity: str | None = None,
        trade_type: str | None = None,
        instrument_type: str | None = None,
        product_type: str | None = None,
        maturity_offset: int | None = None,
        limit: int | None = None,
        fields: list[str] | None = None,
        allow_partial: bool = False,
    ) -> Result[Record]:
        path = self._market("/trds/derivatives", commodity, area)
        path = self._selectors(path, shortcode, maturity)
        params = clean_params(
            trdType=trade_type,
            instrumentType=instrument_type,
            productType=product_type if shortcode is None else None,
            **{"from": iso_date(date_from, "date_from"), "to": iso_date(date_to, "date_to")},
            maturityOffset=maturity_offset if maturity is not None else None,
            limit=limit,
            fields=fields,
        )
        return self._records(path, "derivatives.trade_history", params, allow_partial=allow_partial)

    def top_of_book(
        self,
        commodity: str,
        area: str,
        trade_date: date | str,
        *,
        symbol: str | None = None,
        shortcode: str | None = None,
        maturity: str | None = None,
        instrument_type: str | None = None,
        product_type: str | None = None,
        time_to: time | str | None = None,
        maturity_offset: int | None = None,
        fields: list[str] | None = None,
        allow_partial: bool = False,
    ) -> Result[Record]:
        path = self._dated("/tob/derivatives", commodity, area, trade_date)
        path = self._book_selector(path, symbol, shortcode, maturity, required=False)
        params = clean_params(
            instrumentType=instrument_type,
            productType=product_type if not any((symbol, shortcode, maturity)) else None,
            timeTo=iso_time(time_to, "time_to") if time_to is not None else None,
            maturityOffset=maturity_offset if maturity is not None else None,
            fields=fields,
        )
        return self._records(path, "derivatives.top_of_book", params, allow_partial=allow_partial)

    def top_of_book_history(
        self,
        commodity: str,
        area: str,
        trade_date: date | str,
        *,
        symbol: str | None = None,
        shortcode: str | None = None,
        maturity: str | None = None,
        time_from: time | str,
        time_to: time | str | None = None,
        instrument_type: str | None = None,
        maturity_offset: int | None = None,
        limit: int | None = None,
        fields: list[str] | None = None,
        allow_partial: bool = False,
    ) -> Result[Record]:
        path = self._dated("/tobs/derivatives", commodity, area, trade_date)
        path = self._book_selector(path, symbol, shortcode, maturity, required=True)
        params = clean_params(
            timeFrom=iso_time(time_from, "time_from"),
            timeTo=iso_time(time_to, "time_to") if time_to is not None else None,
            instrumentType=instrument_type,
            maturityOffset=maturity_offset if maturity is not None else None,
            limit=limit,
            fields=fields,
        )
        return self._records(
            path, "derivatives.top_of_book_history", params, allow_partial=allow_partial
        )

    def statistics(
        self, commodity: str, area: str, trade_date: date | str, **kwargs: Any
    ) -> Result[Record]:
        return self._dated_dataset(
            "/stat/derivatives", "derivatives.statistics", commodity, area, trade_date, **kwargs
        )

    def statistics_history(
        self, commodity: str, area: str, date_from: date | str, date_to: date | str, **kwargs: Any
    ) -> Result[Record]:
        return self._history_dataset(
            "/stats/derivatives",
            "derivatives.statistics_history",
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
            "/spr/derivatives", "derivatives.settlements", commodity, area, trade_date, **kwargs
        )

    def settlement_history(
        self, commodity: str, area: str, date_from: date | str, date_to: date | str, **kwargs: Any
    ) -> Result[Record]:
        return self._history_dataset(
            "/sprs/derivatives",
            "derivatives.settlement_history",
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
        maturity: str | None = None,
        instrument_type: str | None = None,
        product_type: str | None = None,
        maturity_offset: int | None = None,
        limit: int | None = None,
        fields: list[str] | None = None,
        allow_partial: bool = False,
    ) -> Result[Record]:
        path = self._selectors(self._dated(root, commodity, area, trade_date), shortcode, maturity)
        params = clean_params(
            instrumentType=instrument_type,
            productType=product_type if shortcode is None else None,
            maturityOffset=maturity_offset if maturity else None,
            limit=limit,
            fields=fields,
        )
        return self._records(path, operation, params, allow_partial=allow_partial)

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
        maturity: str | None = None,
        instrument_type: str | None = None,
        product_type: str | None = None,
        maturity_offset: int | None = None,
        limit: int | None = None,
        fields: list[str] | None = None,
        allow_partial: bool = False,
    ) -> Result[Record]:
        path = self._selectors(self._market(root, commodity, area), shortcode, maturity)
        params = clean_params(
            instrumentType=instrument_type,
            productType=product_type if shortcode is None else None,
            **{"from": iso_date(date_from, "date_from"), "to": iso_date(date_to, "date_to")},
            maturityOffset=maturity_offset if maturity else None,
            limit=limit,
            fields=fields,
        )
        return self._records(path, operation, params, allow_partial=allow_partial)

    @staticmethod
    def _market(root: str, commodity: str, area: str) -> str:
        return f"{root}/{segment(commodity, 'commodity')}/{segment(area, 'area')}"

    @classmethod
    def _dated(cls, root: str, commodity: str, area: str, value: date | str) -> str:
        return f"{cls._market(root, commodity, area)}/{iso_date(value, 'trade_date')}"

    @staticmethod
    def _selectors(path: str, shortcode: str | None, maturity: str | None) -> str:
        if maturity is not None and shortcode is None:
            raise InvalidRequestError("maturity requires shortcode")
        if shortcode is not None:
            path += f"/{segment(shortcode, 'shortcode')}"
        if maturity is not None:
            path += f"/{segment(maturity, 'maturity')}"
        return path

    @classmethod
    def _book_selector(
        cls,
        path: str,
        symbol: str | None,
        shortcode: str | None,
        maturity: str | None,
        *,
        required: bool,
    ) -> str:
        if symbol and (shortcode or maturity):
            raise InvalidRequestError("use symbol or shortcode and maturity, not both")
        if symbol:
            return path + f"/{segment(symbol, 'symbol')}"
        if shortcode is not None and maturity is not None:
            return cls._selectors(path, shortcode, maturity)
        if required:
            raise InvalidRequestError("symbol or both shortcode and maturity are required")
        if shortcode is not None or maturity is not None:
            raise InvalidRequestError("both shortcode and maturity are required")
        return path
