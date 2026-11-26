"""Check adapter paths and queries against the actual bundled OpenAPI files."""

from __future__ import annotations

import inspect
import re
from typing import Any

import pytest

from eex_datasource.api.auctions import AuctionsAPI
from eex_datasource.api.derivatives import DerivativesAPI
from eex_datasource.api.gas_spot import GasSpotAPI
from eex_datasource.api.indices import IndicesAPI
from eex_datasource.api.transparency import TransparencyAPI

ADAPTERS = {
    "derivatives": DerivativesAPI,
    "gas_spot": GasSpotAPI,
    "auctions": AuctionsAPI,
    "index": IndicesAPI,
    "transparency": TransparencyAPI,
}
DAY = "2026-01-02"
START = f"{DAY}T00:00:00Z"
END = "2026-01-03T00:00:00Z"


class RecordingTransport:
    """Capture adapter requests instead of making HTTP calls."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def get(self, path: str, params: dict[str, Any] | None = None) -> list[Any]:
        self.calls.append((path, params or {}))
        if path == f"/rd/spot/NATGAS/TTF/{DAY}/":
            return ["TTFDA"]
        return []


def adapter_cases():
    """Exercise discovery, optional path depths, history, and pooled calls."""
    date_range = {"date_from": DAY, "date_to": DAY}
    for name, commodity, area, shortcode in (
        ("derivatives", "POWER", "DE", "DEBM"),
        ("gas_spot", "NATGAS", "TTF", "TTFDA"),
    ):
        day = (commodity, area, DAY)
        for method, args in (
            ("commodities", ()),
            ("areas", (commodity,)),
            ("trade_dates", (commodity, area)),
            ("shortcodes", day),
            ("market_day", day),
        ):
            yield name, method, args, {}
        depths = [(), (shortcode,)]
        if name == "derivatives":
            depths.append((shortcode, 202602))
            yield name, "maturities", (*day, shortcode), {}
        for suffix in depths:
            for method in (
                "reference_data",
                "trades",
                "top_of_book",
                "statistics",
                "settlements",
            ):
                yield name, method, (*day, *suffix), {"fields": ["TrdDate", "Area"]}
            for resource in ("trd", "stat", "spr"):
                yield name, "history", (resource, commodity, area, *suffix), date_range
        book = {"time_from": "08:00:00", "time_to": "09:00:00"}
        if name == "derivatives":
            yield name, "top_of_book_history", day, {**book, "symbol": "DEBM+1"}
            instrument = {**book, "shortcode": shortcode, "maturity": 202602}
            yield name, "top_of_book_history", day, instrument
        else:
            yield name, "top_of_book_history", (*day, shortcode), book

    day = ("ENVIRONMENTALS", "EU", DAY)
    for method, args in (
        ("commodities", ()),
        ("areas", day[:1]),
        ("auction_dates", day[:2]),
        ("auction_ids", day),
        ("auction_day", day),
    ):
        yield "auctions", method, args, {}
    for suffix in ((), (42,)):
        for method in ("reference_data", "results", "revenues"):
            yield "auctions", method, (*day, *suffix), {}
    for resource in ("rslt", "rev"):
        yield "auctions", "history", (resource, *day[:2]), date_range

    index = ("NATGAS", "THE", "EGSI_D")
    for method, args in (
        ("commodities", ()),
        ("areas", index[:1]),
        ("indexes", index[:2]),
        ("trade_dates", index),
        ("day", (*index, DAY)),
    ):
        yield "index", method, args, {}
    yield "index", "series", index, {"date_from": DAY, "date_to": DAY}

    day = ("POWER", "DE", DAY)
    for method, args in (
        ("commodities", ()),
        ("areas", day[:1]),
        ("validity_dates", day[:2]),
        ("companies", day),
        ("facilities", (*day, "company")),
        ("units", (*day, "company", "facility")),
        ("capacities", (*day, "company", "facility", "unit")),
        ("reference_tree", day),
    ):
        yield "transparency", method, args, {}
    scope = {}
    for key, value in (
        (None, None),
        ("company_id", "company"),
        ("facility_id", "facility"),
        ("unit_id", "unit"),
    ):
        if key:
            scope[key] = value
        yield "transparency", "reference_data", day, dict(scope)
    for scope in ({}, {"area": "DE", "facility_type": "Producer"}):
        filters = {**scope, "modified_to": END}
        yield "transparency", "umm_updates", ("POWER", START), filters
    validity = {"validity_from": START, "validity_to": END}
    yield "transparency", "current_umms", ("POWER", "DE", "Producer"), validity
    yield "transparency", "adhoc_updates", (START,), {"modified_to": END}
    yield "transparency", "current_adhoc", (), validity
    for eurowind in (False, True):
        args = ("POWER", "DE", "AvailableCapacity", START)
        filters = {"date_to": END, "eurowind": eurowind}
        yield "transparency", "time_series", args, filters


@pytest.mark.parametrize("name,method,args,kwargs", list(adapter_cases()))
def test_requests_match_openapi(api_specs, name, method, args, kwargs) -> None:
    """Reject undocumented routes, query names, and missing required queries."""
    transport = RecordingTransport()
    getattr(ADAPTERS[name](transport), method)(*args, **kwargs)
    spec = api_specs[name]

    def resolve(value):
        if "$ref" not in value:
            return value
        result = spec
        for key in value["$ref"].removeprefix("#/").split("/"):
            result = result[key]
        return result

    assert transport.calls
    for path, query in transport.calls:
        matches = [
            (template, item)
            for template, item in spec["paths"].items()
            if re.fullmatch(re.sub(r"\{[^}]+\}", "[^/]+", template), path)
        ]
        assert matches, f"undocumented path: {path}"
        # Static paths (e.g. 'other') take precedence over variable paths.
        _, item = min(matches, key=lambda match: match[0].count("{"))
        parameters = [
            resolve(value)
            for value in (
                *item.get("parameters", []),
                *item["get"].get("parameters", []),
            )
        ]
        queries = {p["name"]: p for p in parameters if p["in"] == "query"}
        assert query.keys() <= queries.keys(), (
            f"{path}: {query.keys() - queries.keys()}"
        )
        required = {key for key, value in queries.items() if value.get("required")}
        assert required <= query.keys(), f"{path}: missing {required - query.keys()}"


@pytest.mark.parametrize("adapter", ADAPTERS.values())
def test_public_adapter_methods_have_docstrings(adapter) -> None:
    """Keep API documentation present even for inherited shared operations."""
    for name, method in inspect.getmembers(adapter, inspect.isfunction):
        if not name.startswith("_"):
            assert inspect.getdoc(method), f"{adapter.__name__}.{name}"
