"""EEX Transparency Platform endpoints."""

from __future__ import annotations

from typing import Any

from .base import BaseAPI, segment


class TransparencyAPI(BaseAPI):
    def commodities(self) -> list[str]:
        return self._get("/rd/transparency/")

    def areas(self, commodity: str) -> list[str]:
        return self._get(f"/rd/transparency/{segment(commodity)}/")

    def validity_dates(self, commodity: str, area: str) -> list[str]:
        return self._get(f"/rd/transparency/{segment(commodity)}/{segment(area)}/")

    def reference_data(
        self,
        commodity: str,
        area: str,
        validity_date: str,
        *,
        company_id: str | None = None,
        facility_id: str | None = None,
        unit_id: str | None = None,
        capacities: bool = False,
        limit: int = 60_000,
        **filters: Any,
    ) -> list[dict[str, Any]]:
        path = (
            f"/rd/transparency/{segment(commodity)}/{segment(area)}/"
            f"{segment(validity_date)}"
        )
        for value in (company_id, facility_id, unit_id):
            if value is not None:
                path += f"/{segment(value)}"
        if capacities:
            path += "/"
        return self._get(path, limit=limit, **filters)

    def companies(
        self,
        commodity: str,
        area: str,
        validity_date: str,
        **filters: Any,
    ) -> list[dict[str, Any]]:
        return self._get(
            f"/rd/transparency/{segment(commodity)}/{segment(area)}/"
            f"{segment(validity_date)}/",
            **filters,
        )

    def facilities(
        self,
        commodity: str,
        area: str,
        validity_date: str,
        company_id: str,
        **filters: Any,
    ) -> list[dict[str, Any]]:
        return self._get(
            f"/rd/transparency/{segment(commodity)}/{segment(area)}/"
            f"{segment(validity_date)}/{segment(company_id)}/",
            **filters,
        )

    def units(
        self,
        commodity: str,
        area: str,
        validity_date: str,
        company_id: str,
        facility_id: str,
        **filters: Any,
    ) -> list[dict[str, Any]]:
        return self._get(
            f"/rd/transparency/{segment(commodity)}/{segment(area)}/"
            f"{segment(validity_date)}/{segment(company_id)}/"
            f"{segment(facility_id)}/",
            **filters,
        )

    def capacities(
        self,
        commodity: str,
        area: str,
        validity_date: str,
        company_id: str,
        facility_id: str,
        unit_id: str,
        **filters: Any,
    ) -> list[dict[str, Any]]:
        return self.reference_data(
            commodity,
            area,
            validity_date,
            company_id=company_id,
            facility_id=facility_id,
            unit_id=unit_id,
            capacities=True,
            **filters,
        )

    def umm_updates(
        self,
        commodity: str,
        modified_from: str,
        *,
        area: str | None = None,
        facility_type: str | None = None,
        modified_to: str | None = None,
        limit: int = 60_000,
        **filters: Any,
    ) -> list[dict[str, Any]]:
        if area is not None and facility_type is not None:
            path = (
                f"/umm/transparency/{segment(commodity)}/{segment(area)}/"
                f"{segment(facility_type)}/{segment(modified_from)}"
            )
        else:
            path = f"/umm/transparency/{segment(commodity)}/{segment(modified_from)}"
        return self._get(path, modifiedTo=modified_to, limit=limit, **filters)

    def current_umms(
        self,
        commodity: str,
        area: str,
        facility_type: str,
        *,
        limit: int = 60_000,
        **filters: Any,
    ) -> list[dict[str, Any]]:
        return self._get(
            f"/umm/transparency/{segment(commodity)}/{segment(area)}/"
            f"{segment(facility_type)}",
            limit=limit,
            **filters,
        )

    def adhoc_updates(
        self,
        modified_from: str,
        *,
        modified_to: str | None = None,
        limit: int = 60_000,
        **filters: Any,
    ) -> list[dict[str, Any]]:
        return self._get(
            f"/umm/transparency/other/{segment(modified_from)}",
            modifiedTo=modified_to,
            limit=limit,
            **filters,
        )

    def current_adhoc(
        self, *, limit: int = 60_000, **filters: Any
    ) -> list[dict[str, Any]]:
        return self._get("/umm/transparency/other", limit=limit, **filters)

    def time_series(
        self,
        commodity: str,
        area: str,
        symbol: str,
        date_from: str,
        *,
        date_to: str | None = None,
        eurowind: bool = False,
        limit: int = 60_000,
        **filters: Any,
    ) -> list[dict[str, Any]]:
        source = "eurowind" if eurowind else "transparency"
        return self._get(
            f"/series/{source}/{segment(commodity)}/{segment(area)}/"
            f"{segment(symbol)}/{segment(date_from)}",
            to=date_to,
            **filters,
        )

    def reference_tree(
        self, commodity: str, area: str, validity_date: str
    ) -> list[dict[str, Any]]:
        """Return the nested company/facility/unit master-data tree."""

        return self.reference_data(commodity, area, validity_date)
