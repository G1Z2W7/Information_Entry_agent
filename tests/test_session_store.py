from __future__ import annotations

import os
import time
import uuid

import pytest
from redis import Redis

from app.agent.models import MainInfo, SessionState
from app.agent.session_store import (
    InMemorySessionStore,
    RedisSessionStore,
    build_session_store_from_env,
)


def test_in_memory_session_store_round_trip() -> None:
    store = InMemorySessionStore()
    state = SessionState(
        session_id="memory-session-1",
        main_info=MainInfo(distributorName="智行汽车"),
    )

    store.save(state)
    loaded = store.get("memory-session-1")

    assert loaded is not None
    assert loaded.session_id == "memory-session-1"
    assert loaded.main_info.distributorName == "智行汽车"

    loaded.main_info.distributorName = "修改后名称"
    reloaded = store.get("memory-session-1")
    assert reloaded is not None
    assert reloaded.main_info.distributorName == "智行汽车"


def test_build_session_store_from_env_can_force_memory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SESSION_STORE_BACKEND", "memory")

    store = build_session_store_from_env()

    assert isinstance(store, InMemorySessionStore)


def test_redis_session_store_round_trip_and_clear() -> None:
    client = _build_test_redis_client()
    prefix = f"test:session-store:{uuid.uuid4()}:"
    store = RedisSessionStore(client, prefix=prefix, ttl_seconds=30)

    state = SessionState(
        session_id="redis-session-1",
        main_info=MainInfo(distributorName="智行汽车"),
    )
    store.save(state)

    loaded = store.get("redis-session-1")
    assert loaded is not None
    assert loaded.main_info.distributorName == "智行汽车"

    store.clear()
    assert store.get("redis-session-1") is None


def test_redis_session_store_ttl_expiry() -> None:
    client = _build_test_redis_client()
    prefix = f"test:session-store:{uuid.uuid4()}:"
    store = RedisSessionStore(client, prefix=prefix, ttl_seconds=1)

    state = SessionState(
        session_id="redis-session-ttl",
        main_info=MainInfo(distributorName="智行汽车"),
    )
    store.save(state)
    assert store.get("redis-session-ttl") is not None

    time.sleep(1.2)
    assert store.get("redis-session-ttl") is None


def _build_test_redis_client() -> Redis:
    host = os.getenv("REDIS_HOST")
    if not host:
        pytest.skip("REDIS_HOST is not configured")

    client = Redis(
        host=host,
        port=int(os.getenv("REDIS_PORT", "6379")),
        password=os.getenv("REDIS_PASSWORD") or None,
        db=int(os.getenv("REDIS_DB", "0")),
        socket_connect_timeout=1,
        socket_timeout=1,
        decode_responses=False,
    )
    client.ping()
    return client
