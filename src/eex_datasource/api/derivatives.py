"""Derivatives endpoints from ``specs/derivatives.yaml``.

Source: https://eds.eex-group.com/api-spec/derivatives.yaml
"""

from __future__ import annotations

from typing import Any

from .base import segment
from .market import MarketAPI


class DerivativesAPI(MarketAPI):
    """Discover and retrieve derivative contracts, trades, and prices."""

    market = "derivatives"

    def reference_data(
        self,
        commodity: str,
        area: str,
        trade_date: str,
        shortcode: str | None = None,
        maturity: str | int | None = None,
        *,
        limit: int = 60_000,
        **filters: Any,
    ) -> list[dict[str, Any]]:
        """Fetch ``/rd`` contract records, optionally scoped to a maturity.

        ``maturity`` requires ``shortcode``. Extra filters use the query names
        in the OpenAPI snapshot, such as ``productType`` and ``fields``.
        ``limit`` is only sent to the unscoped daily route.
        """
        return self._day_resource(
            "rd",
            commodity,
            area,
            trade_date,
            shortcode,
            maturity,
            limit=limit,
            **filters,
        )

    def maturities(
        self, commodity: str, area: str, trade_date: str, shortcode: str
    ) -> list[int]:
        """List maturities for a shortcode (the trailing-slash ``/rd`` route)."""
        return self._get(
            f"/rd/derivatives/{segment(commodity)}/{segment(area)}/"
            f"{segment(trade_date)}/{segment(shortcode)}/"
        )

    def history(
        self,
        resource: str,
        commodity: str,
        area: str,
        shortcode: str | None = None,
        maturity: str | int | None = None,
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
            maturity,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
            **filters,
        )

    def top_of_book_history(
        self,
        commodity: str,
        area: str,
        trade_date: str,
        *,
        time_from: str,
        time_to: str | None = None,
        symbol: str | None = None,
        shortcode: str | None = None,
        maturity: str | int | None = None,
        limit: int = 60_000,
        **filters: Any,
    ) -> list[dict[str, Any]]:
        """Fetch every ``/tobs`` change using a symbol or shortcode/maturity.

        ``time_from`` is required by OpenAPI; times are in market time.
        """
        if symbol is not None and (shortcode is not None or maturity is not None):
            raise ValueError("provide symbol or shortcode/maturity, not both")
        if symbol is not None:
            path = (
                f"/tobs/derivatives/{segment(commodity)}/{segment(area)}/"
                f"{segment(trade_date)}/{segment(symbol)}"
            )
        elif shortcode is not None and maturity is not None:
            path = (
                f"/tobs/derivatives/{segment(commodity)}/{segment(area)}/"
                f"{segment(trade_date)}/{segment(shortcode)}/"
                f"{segment(maturity)}"
            )
        else:
            raise ValueError("provide either symbol or both shortcode and maturity")
        return self._get(
            path,
            timeFrom=time_from,
            timeTo=time_to,
            limit=limit,
            **filters,
        )
