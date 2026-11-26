"""EEX Transparency Platform endpoints from ``specs/transparency.yaml``.

Source: https://eds.eex-group.com/api-spec/transparency.yaml
"""

from __future__ import annotations

from typing import Any

from .base import BaseAPI, segment


class TransparencyAPI(BaseAPI):
    """Retrieve asset master data, market messages, and capacity time series."""

    def commodities(self) -> list[str]:
        """List entitled transparency commodities."""
        return self._get("/rd/transparency/")

    def areas(self, commodity: str) -> list[str]:
        """List available countries for a commodity."""
        return self._get(f"/rd/transparency/{segment(commodity)}/")

    def validity_dates(self, commodity: str, area: str) -> list[str]:
        """List available master-data validity dates."""
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
        """Fetch an asset tree or a complete company/facility/unit subpath.

        Each child ID requires its parent ID. ``capacities=True`` selects the
        trailing-slash capacity route and requires all three IDs.
        ``limit`` is a compatibility argument, not an OpenAPI query parameter.
        """
        if facility_id is not None and company_id is None:
            raise ValueError("facility_id requires company_id")
        if unit_id is not None and facility_id is None:
            raise ValueError("unit_id requires facility_id")
        if capacities and unit_id is None:
            raise ValueError("capacities requires company_id, facility_id and unit_id")
        path = (
            f"/rd/transparency/{segment(commodity)}/{segment(area)}/"
            f"{segment(validity_date)}"
        )
        for value in (company_id, facility_id, unit_id):
            if value is not None:
                path += f"/{segment(value)}"
        if capacities:
            path += "/"
        return self._get(path, **filters)

    def companies(
        self,
        commodity: str,
        area: str,
        validity_date: str,
        **filters: Any,
    ) -> list[dict[str, Any]]:
        """List companies on a validity date using the discovery route."""
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
        """List facilities belonging to a company."""
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
        """List units belonging to a facility."""
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
        """Fetch installed/working capacity records for a specific unit."""
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
        """Fetch UMM revisions by modification time.

        Supply both ``area`` and ``facility_type`` to use the scoped route,
        or neither for commodity-wide updates. Extra filters use OpenAPI names.
        """
        if (area is None) != (facility_type is None):
            raise ValueError("area and facility_type must be supplied together")
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
        validity_from: str,
        validity_to: str | None = None,
        limit: int = 60_000,
        **filters: Any,
    ) -> list[dict[str, Any]]:
        """Fetch UMMs affecting the required ``validity_from`` time interval."""
        return self._get(
            f"/umm/transparency/{segment(commodity)}/{segment(area)}/"
            f"{segment(facility_type)}",
            validityFrom=validity_from,
            validityTo=validity_to,
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
        """Fetch ad-hoc message revisions by modification time."""
        return self._get(
            f"/umm/transparency/other/{segment(modified_from)}",
            modifiedTo=modified_to,
            limit=limit,
            **filters,
        )

    def current_adhoc(
        self,
        *,
        validity_from: str,
        validity_to: str | None = None,
        limit: int = 60_000,
        **filters: Any,
    ) -> list[dict[str, Any]]:
        """Fetch ad-hoc messages affecting the required validity interval."""
        return self._get(
            "/umm/transparency/other",
            validityFrom=validity_from,
            validityTo=validity_to,
            limit=limit,
            **filters,
        )

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
        """Fetch transparency or EuroWind series from an ISO-8601 timestamp.

        The OpenAPI series routes do not accept ``limit``. It is retained as a
        compatibility argument for callers pooling bounded requests; constrain
        responses using ``date_to`` and documented query filters instead.
        """
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
