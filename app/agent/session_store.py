from __future__ import annotations

import os
from typing import Protocol

from redis import Redis
from redis.exceptions import RedisError

from app.agent.models import SessionState


DEFAULT_SESSION_TTL_SECONDS = 60 * 60 * 24
DEFAULT_SESSION_KEY_PREFIX = "distributor-agent:session:"


class SessionStore(Protocol):
    def get(self, session_id: str) -> SessionState | None:
        ...

    def save(self, state: SessionState) -> None:
        ...

    def delete(self, session_id: str) -> None:
        ...

    def clear(self) -> None:
        ...


class InMemorySessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, SessionState] = {}

    def get(self, session_id: str) -> SessionState | None:
        state = self._sessions.get(session_id)
        if state is None:
            return None
        return state.model_copy(deep=True)

    def save(self, state: SessionState) -> None:
        self._sessions[state.session_id] = state.model_copy(deep=True)

    def delete(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    def clear(self) -> None:
        self._sessions.clear()


class RedisSessionStore:
    def __init__(
        self,
        redis_client: Redis,
        *,
        prefix: str = DEFAULT_SESSION_KEY_PREFIX,
        ttl_seconds: int = DEFAULT_SESSION_TTL_SECONDS,
    ) -> None:
        self.redis_client = redis_client
        self.prefix = prefix
        self.ttl_seconds = ttl_seconds

    def get(self, session_id: str) -> SessionState | None:
        payload = self.redis_client.get(self._key(session_id))
        if payload is None:
            return None
        if isinstance(payload, bytes):
            payload = payload.decode("utf-8")
        return SessionState.model_validate_json(payload)

    def save(self, state: SessionState) -> None:
        self.redis_client.set(
            self._key(state.session_id),
            state.model_dump_json(),
            ex=self.ttl_seconds,
        )

    def delete(self, session_id: str) -> None:
        self.redis_client.delete(self._key(session_id))

    def clear(self) -> None:
        cursor = 0
        pattern = f"{self.prefix}*"
        while True:
            cursor, keys = self.redis_client.scan(cursor=cursor, match=pattern, count=100)
            if keys:
                self.redis_client.delete(*keys)
            if cursor == 0:
                break

    def _key(self, session_id: str) -> str:
        return f"{self.prefix}{session_id}"


def build_session_store_from_env() -> SessionStore:
    backend = os.getenv("SESSION_STORE_BACKEND", "auto").lower()

    if backend == "memory":
        return InMemorySessionStore()

    if backend in {"redis", "auto"} and os.getenv("REDIS_HOST"):
        try:
            return _build_redis_store_from_env()
        except RedisError:
            if backend == "redis":
                raise

    return InMemorySessionStore()


def _build_redis_store_from_env() -> RedisSessionStore:
    host = os.getenv("REDIS_HOST", "localhost")
    port = int(os.getenv("REDIS_PORT", "6379"))
    password = os.getenv("REDIS_PASSWORD") or None
    db = int(os.getenv("REDIS_DB", "0"))
    ttl_seconds = int(
        os.getenv("SESSION_STORE_TTL_SECONDS", str(DEFAULT_SESSION_TTL_SECONDS))
    )
    prefix = os.getenv("SESSION_STORE_PREFIX", DEFAULT_SESSION_KEY_PREFIX)

    client = Redis(
        host=host,
        port=port,
        password=password,
        db=db,
        socket_connect_timeout=1,
        socket_timeout=1,
        decode_responses=False,
    )
    client.ping()
    return RedisSessionStore(
        client,
        prefix=prefix,
        ttl_seconds=ttl_seconds,
    )
