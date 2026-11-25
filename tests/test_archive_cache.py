from __future__ import annotations

from datetime import timedelta

import httpx

from eex_datasource import EEXClient
from eex_datasource.storage.archive import Archive
from eex_datasource.storage.cache import CachedTransport, canonical_request_hash
from eex_datasource.storage.database import (
    create_database_engine,
    session_factory,
)
from eex_datasource.storage.models import Base


def test_archive_is_content_addressed_and_deterministic(tmp_path) -> None:
    archive = Archive(tmp_path)
    body = b'[{"x":1}]'
    first = archive.store(body)
    second = archive.store(body)
    assert first == second
    assert archive.load_bytes(first.relative_path) == body
    assert archive.load_json(first.relative_path) == [{"x": 1}]


def test_canonical_request_hash_ignores_query_order() -> None:
    assert canonical_request_hash("/x", {"b": 2, "a": 1}) == (
        canonical_request_hash("/x", {"a": 1, "b": 2})
    )


def test_cached_transport_avoids_duplicate_http_request(tmp_path) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json=[{"value": 1}], request=request)

    engine = create_database_engine("sqlite://")
    Base.metadata.create_all(engine)
    sessions = session_factory(engine)
    with (
        EEXClient(
            "token",
            request_interval=0,
            transport=httpx.MockTransport(handler),
        ) as client,
        sessions() as session,
    ):
        cached = CachedTransport(
            client,
            session,
            Archive(tmp_path),
            ttl=timedelta(days=1),
        )
        assert cached.get("/test", {"a": 1}) == [{"value": 1}]
        assert cached.get("/test", {"a": 1}) == [{"value": 1}]
        assert cached.last_cache_hit is True
    assert calls == 1
