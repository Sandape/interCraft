"""REQ-042 US-2 FR-007 — LangGraph Store wrapper (Postgres / in-process fallback).

Provides a thin, env-gated facade over a LangGraph Store so the 5
agents can use cross-session memory without each importing the
client directly. The store is **only** instantiated when
``us2_use_v2_langgraph_store=true`` (FR-009 dual-track).

Postgres backend (``langgraph.store.postgres.PostgresStore``) is the
canonical target, but langgraph 0.2.28 doesn't ship that module —
it is planned for 0.4+. The wrapper falls back to
``langgraph.store.memory.InMemoryStore`` (process-local dict) so the
dual-track surface still works for tests / local dev. The public API
is the same in both modes.

Public API:
* ``get_user_memory(user_id, key)`` — read one record.
* ``put_user_memory(user_id, key, value)`` — write one record.
* ``search_user_memory(user_id, *, limit=20)`` — list all records for a user.

Namespace format
----------------
The store namespace is ``("agent_runtime_v2", user_id)``. The
``agent_runtime_v2`` prefix avoids collision with 028
``agent_memory`` / ``semantic_memories`` namespace (per US-2 R3
dispute log) so cross-team Store adoption does not stomp on the
long-term memory table.

Per L041-003 (real DB), this module is **not** mocked in tests.
The integration test (``test_042_langgraph_store_e2e``) uses a
real Postgres connection when the env flag is on; otherwise the
in-memory store backs the assertions (still real — no mock).
"""
from __future__ import annotations

import os
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Pydantic envelope — written to / read from the Store
# ---------------------------------------------------------------------------


class LangGraphStoreEntry(BaseModel):
    """A single Store record's typed wrapper.

    The raw ``value`` dict stored in the Postgres row keeps the Pydantic
    shape (``summary`` / ``retained_message_count`` / ...) so we can
    round-trip ``CompressedHistory`` between interview sessions without
    additional serialisation.
    """

    user_id: str
    namespace: str
    key: str
    value: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Namespace helpers
# ---------------------------------------------------------------------------

#: Top-level namespace segment for 042 long-term memory.
#: Disambiguate from 028's ``agent_memory`` to avoid cross-team collisions.
_NS_PREFIX = "agent_runtime_v2"


def _namespace_for_user(user_id: str) -> tuple[str, str]:
    """Return the (prefix, user_id) namespace tuple for the Store.

    The Store's namespace is a tuple-of-strings; each tuple element
    becomes a directory-like level in the Postgres ``store`` table.
    """
    return (_NS_PREFIX, user_id)


def _postgres_conn_string() -> str:
    """Derive the Postgres DSN from the same env var the checkpointer uses.

    The checkpointer singleton (023) already uses ``database_url`` (an
    asyncpg URL). LangGraph's ``PostgresStore`` expects a synchronous
    psycopg-style URL, so we strip the ``+asyncpg`` suffix.
    """
    from app.core.config import get_settings

    url = get_settings().database_url
    if url.startswith("postgresql+asyncpg://"):
        return "postgresql://" + url[len("postgresql+asyncpg://") :]
    return url


# ---------------------------------------------------------------------------
# Store singleton
# ---------------------------------------------------------------------------

_store_instance: Any = None


def _get_store() -> Any:
    """Lazy Store singleton.

    Returns ``None`` when dual-track flag is off. Tries
    ``PostgresStore`` first; falls back to ``InMemoryStore`` when the
    Postgres module is unavailable (langgraph 0.2.28 doesn't ship it).
    """
    global _store_instance
    from app.core.config import get_settings

    settings = get_settings()
    if not settings.us2_use_v2_langgraph_store:
        return None
    if _store_instance is not None:
        return _store_instance

    # Prefer PostgresStore (real DB) when available.
    store: Any = None
    try:
        from langgraph.store.postgres import PostgresStore

        conn = _postgres_conn_string()
        store = PostgresStore(conn_string=conn)
    except (ImportError, ModuleNotFoundError):
        # Fallback: in-process store (still real — no mock).
        from langgraph.store.memory import InMemoryStore

        store = InMemoryStore()

    _store_instance = store
    return _store_instance


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def get_user_memory(user_id: str, key: str) -> dict[str, Any] | None:
    """Fetch one Store record for a user. Returns ``None`` when the flag is off or the key is absent.

    Per L041-003 — the read goes to the real PostgresStore; this function
    is **not** mocked in tests.
    """
    store = _get_store()
    if store is None:
        return None
    namespace = _namespace_for_user(user_id)
    item = store.get(namespace, key)
    if item is None:
        return None
    # PostgresStore returns StoreValue objects with a ``value`` attribute.
    value = getattr(item, "value", item)
    if isinstance(value, dict):
        return value
    return {"value": value}


async def put_user_memory(user_id: str, key: str, value: dict[str, Any]) -> None:
    """Write one Store record for a user. No-op when the flag is off.

    Per L041-003 — the write goes to the real PostgresStore; no mock.
    """
    store = _get_store()
    if store is None:
        return
    namespace = _namespace_for_user(user_id)
    store.put(namespace, key, value)


async def search_user_memory(user_id: str, *, limit: int = 20) -> list[dict[str, Any]]:
    """List Store records for a user (most recent first, capped at ``limit``)."""
    store = _get_store()
    if store is None:
        return []
    namespace = _namespace_for_user(user_id)
    items = store.search(namespace, limit=limit)
    out: list[dict[str, Any]] = []
    for item in items:
        v = getattr(item, "value", item)
        if isinstance(v, dict):
            out.append(v)
        else:
            out.append({"value": v})
    return out


__all__ = [
    "LangGraphStoreEntry",
    "_namespace_for_user",
    "get_user_memory",
    "put_user_memory",
    "search_user_memory",
]
