from __future__ import annotations

from datetime import date, datetime
from typing import Any

from .._utils import clean_params, iso_date, segment
from ..result import Record, Result
from .base import Service


class TransparencyService(Service):
    _rd = "/rd/transparency"

    def commodities(self) -> list[str]:
        return self._identifiers(f"{self._rd}/", "transparency.commodities")

    def areas(self, commodity: str) -> list[str]:
        return self._identifiers(
            f"{self._rd}/{segment(commodity, 'commodity')}/", "transparency.areas"
        )

    def validity_dates(self, commodity: str, area: str) -> list[str]:
        return self._identifiers(self._market(commodity, area) + "/", "transparency.validity_dates")

    def companies(
        self,
        commodity: str,
        area: str,
        validity_date: date | str,
        *,
        only_modified: bool | None = None,
        fields: list[str] | None = None,
    ) -> list[str]:
        path = self._dated(commodity, area, validity_date) + "/"
        return self._identifiers(
            path,
            "transparency.companies",
            clean_params(onlyModified=only_modified, fields=fields),
        )

    def company_records(
        self,
        commodity: str,
        area: str,
        validity_date: date | str,
        *,
        only_modified: bool | None = None,
        fields: list[str] | None = None,
        allow_partial: bool = False,
    ) -> Result[Record]:
        return self._records(
            self._dated(commodity, area, validity_date),
            "transparency.company_records",
            clean_params(onlyModified=only_modified, fields=fields),
            allow_partial=allow_partial,
        )

    def company(
        self,
        commodity: str,
        area: str,
        validity_date: date | str,
        company_id: str,
        *,
        fields: list[str] | None = None,
    ) -> Record:
        return self._record(
            self._entity_path(commodity, area, validity_date, company_id),
            "transparency.company",
            clean_params(fields=fields),
        )

    def facilities(
        self,
        commodity: str,
        area: str,
        validity_date: date | str,
        company_id: str,
        *,
        fields: list[str] | None = None,
    ) -> list[str]:
        return self._identifiers(
            self._entity_path(commodity, area, validity_date, company_id) + "/",
            "transparency.facilities",
            clean_params(fields=fields),
        )

    def facility(
        self,
        commodity: str,
        area: str,
        validity_date: date | str,
        company_id: str,
        facility_id: str,
        *,
        fields: list[str] | None = None,
    ) -> Record:
        path = self._entity_path(commodity, area, validity_date, company_id, facility_id)
        return self._record(path, "transparency.facility", clean_params(fields=fields))

    def units(
        self,
        commodity: str,
        area: str,
        validity_date: date | str,
        company_id: str,
        facility_id: str,
        *,
        fields: list[str] | None = None,
    ) -> list[str]:
        path = self._entity_path(commodity, area, validity_date, company_id, facility_id) + "/"
        return self._identifiers(path, "transparency.units", clean_params(fields=fields))

    def unit(
        self,
        commodity: str,
        area: str,
        validity_date: date | str,
        company_id: str,
        facility_id: str,
        unit_id: str,
        *,
        fields: list[str] | None = None,
    ) -> Record:
        path = self._entity_path(commodity, area, validity_date, company_id, facility_id, unit_id)
        return self._record(path, "transparency.unit", clean_params(fields=fields))

    def capacities(
        self,
        commodity: str,
        area: str,
        validity_date: date | str,
        company_id: str,
        facility_id: str,
        unit_id: str,
        *,
        fields: list[str] | None = None,
        allow_partial: bool = False,
    ) -> Result[Record]:
        path = (
            self._entity_path(commodity, area, validity_date, company_id, facility_id, unit_id)
            + "/"
        )
        return self._records(
            path,
            "transparency.capacities",
            clean_params(fields=fields),
            allow_partial=allow_partial,
        )

    def events_modified(
        self,
        commodity: str,
        modified_from: str | datetime,
        *,
        area: str | None = None,
        facility_type: str | None = None,
        modified_to: str | datetime | None = None,
        limit: int = 60_000,
        fields: list[str] | None = None,
        allow_partial: bool = False,
        **filters: Any,
    ) -> Result[Record]:
        if (area is None) != (facility_type is None):
            from ..exceptions import InvalidRequestError

            raise InvalidRequestError("area and facility_type must be supplied together")
        path = f"/umm/transparency/{segment(commodity, 'commodity')}"
        if area is not None and facility_type is not None:
            path += f"/{segment(area, 'area')}/{segment(facility_type, 'facility_type')}"
        path += f"/{segment(self._time(modified_from), 'modified_from')}"
        params = clean_params(
            modifiedTo=self._time(modified_to),
            limit=limit,
            fields=fields,
            **self._event_filters(filters),
        )
        return self._records(
            path, "transparency.events_modified", params, allow_partial=allow_partial
        )

    def events_valid(
        self,
        commodity: str,
        area: str,
        facility_type: str,
        validity_from: str | datetime,
        *,
        validity_to: str | datetime | None = None,
        limit: int = 60_000,
        fields: list[str] | None = None,
        allow_partial: bool = False,
        **filters: Any,
    ) -> Result[Record]:
        path = "/umm/transparency/{}/{}/{}".format(
            segment(commodity, "commodity"),
            segment(area, "area"),
            segment(facility_type, "facility_type"),
        )
        params = clean_params(
            validityFrom=self._time(validity_from),
            validityTo=self._time(validity_to),
            limit=limit,
            fields=fields,
            **self._event_filters(filters),
        )
        return self._records(path, "transparency.events_valid", params, allow_partial=allow_partial)

    def other_events(
        self,
        *,
        modified_from: str | datetime | None = None,
        validity_from: str | datetime | None = None,
        modified_to: str | datetime | None = None,
        validity_to: str | datetime | None = None,
        limit: int = 60_000,
        fields: list[str] | None = None,
        allow_partial: bool = False,
        **filters: Any,
    ) -> Result[Record]:
        from ..exceptions import InvalidRequestError

        if (modified_from is None) == (validity_from is None):
            raise InvalidRequestError("provide exactly one of modified_from or validity_from")
        path = "/umm/transparency/other"
        if modified_from is not None:
            path += f"/{segment(self._time(modified_from), 'modified_from')}"
        params = clean_params(
            modifiedTo=self._time(modified_to),
            validityFrom=self._time(validity_from),
            validityTo=self._time(validity_to),
            limit=limit,
            fields=fields,
            **filters,
        )
        return self._records(path, "transparency.other_events", params, allow_partial=allow_partial)

    def time_series(
        self,
        commodity: str,
        area: str,
        symbol: str,
        time_from: str | datetime,
        *,
        time_to: str | datetime | None = None,
        euro_wind: bool = False,
        fields: list[str] | None = None,
        **filters: Any,
    ) -> Result[Record]:
        root = "/series/eurowind" if euro_wind else "/series/transparency"
        path = "{}/{}/{}/{}/{}".format(
            root,
            segment(commodity, "commodity"),
            segment(area, "area"),
            segment(symbol, "symbol"),
            segment(self._time(time_from), "time_from"),
        )
        params = clean_params(to=self._time(time_to), fields=fields, **filters)
        return self._records(path, "transparency.time_series", params)

    def _market(self, commodity: str, area: str) -> str:
        return f"{self._rd}/{segment(commodity, 'commodity')}/{segment(area, 'area')}"

    def _dated(self, commodity: str, area: str, value: date | str) -> str:
        return self._market(commodity, area) + f"/{iso_date(value, 'validity_date')}"

    def _entity_path(self, commodity: str, area: str, validity_date: date | str, *ids: str) -> str:
        path = self._dated(commodity, area, validity_date)
        return path + "".join(f"/{segment(value, 'identifier')}" for value in ids)

    @staticmethod
    def _time(value: str | datetime | None) -> str | None:
        return value.isoformat() if isinstance(value, datetime) else value

    @staticmethod
    def _event_filters(filters: dict[str, Any]) -> dict[str, Any]:
        names = {
            "event_start": "eventStart",
            "event_stop": "eventStop",
            "event_status": "eventStatus",
            "company_id": "companyID",
            "facility_id": "facilityID",
            "unit_id": "unitID",
            "control_area": "controlArea",
            "market_area": "marketArea",
            "fuel_type": "fuelType",
            "unavailability_type": "unavailabilityType",
            "message_id": "messageID",
            "unavailability_reason": "unavailabilityReason",
            "min_outage": "minOutage",
        }
        return {names.get(key, key): value for key, value in filters.items()}
