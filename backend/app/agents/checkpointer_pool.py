"""REQ-043 US-2 FR-005 — Checkpointer 8-pool sharding.

Spec contract:
- ``get_checkpointer_pool(user_id)`` returns an
  ``AsyncPostgresSaver`` instance backed by a per-pool
  ``AsyncConnectionPool``.
- ``pool_id = hash(user_id) % 8`` (per Clarifications 2026-07-03:
  ship with 8 pools, not 4, to avoid a future 4→8 migration).
- Each pool is a singleton: same ``pool_id`` → same instance.
- One pool being exhausted / erroring must NOT affect other pools.

Design (per L041-001 + L041-005):
- Module owns its own ``_pools`` registry. Singleton per pool_id
  with double-checked locking via ``asyncio.Lock`` (mirrors the
  pattern from ``checkpointer.py`` — proven safe under concurrent
  callers).
- The pool factory ``_create_pool`` builds a per-pool
  ``AsyncConnectionPool`` with the same keepalive / check params
  as the existing 023 single-pool implementation.
- A failing pool rebuild is scoped to that pool_id — never
  force-rebuild all 8 pools.
"""
from __future__ import annotations

import asyncio
import contextlib
import sys
from hashlib import md5
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    from psycopg_pool import AsyncConnectionPool

# Windows: force SelectorEventLoop (psycopg rejects ProactorEventLoop).
if sys.platform.startswith("win"):
    with contextlib.suppress(AttributeError):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


# ---------------------------------------------------------------------------
# Pool configuration
# ---------------------------------------------------------------------------
class CheckpointerPoolConfig(BaseModel):
    """Per-pool sizing + health check config (per spec Key Entities).

    Attributes:
        pool_id: 0..7 (8 pools total).
        min_size: minimum connections kept warm.
        max_size: maximum concurrent connections.
        health_check_interval: seconds between health probes (informational
            — actual probe runs on every checkout via ``check`` callback).
    """

    pool_id: int = Field(ge=0, le=7)
    min_size: int = Field(default=5, ge=1)
    max_size: int = Field(default=20, ge=1)
    health_check_interval: int = Field(default=60, ge=1)

    model_config = {"frozen": False}


# Pre-built config for all 8 pools (sizes can diverge in future via env).
POOL_CONFIGS: list[CheckpointerPoolConfig] = [
    CheckpointerPoolConfig(pool_id=i) for i in range(8)
]


# ---------------------------------------------------------------------------
# Pool registry (one slot per pool_id)
# ---------------------------------------------------------------------------
_pools: dict[int, "AsyncPostgresSaver"] = {}
_pool_locks: dict[int, asyncio.Lock] = {}
_registry_lock = asyncio.Lock()


def get_pool_id(user_id: str) -> int:
    """Hash a user_id to one of 8 pool slots.

    Algorithm: ``int(md5(user_id.encode()).hexdigest(), 16) % 8``.
    md5 is chosen over Python's built-in ``hash()`` because the latter
    is process-randomized (PYTHONHASHSEED), which would scatter a
    user's checkpoints across pools every restart.
    """
    return int(md5(user_id.encode()).hexdigest(), 16) % 8


async def _check_connection(conn: Any) -> None:
    """Health check on every pool checkout (FR-025 mirror)."""
    async with conn.cursor() as cur:
        await cur.execute("SELECT 1")


async def _create_pool(cfg: CheckpointerPoolConfig) -> "AsyncPostgresSaver":
    """Build a per-pool ``AsyncPostgresSaver`` + ``AsyncConnectionPool``."""
    import os

    os.environ.setdefault("LANGGRAPH_STRICT_MSGPACK", "true")
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    from psycopg_pool import AsyncConnectionPool

    from app.agents.checkpointer import _stripped_db_url

    sync_url = _stripped_db_url()
    pool = AsyncConnectionPool(
        conninfo=sync_url,
        min_size=cfg.min_size,
        max_size=cfg.max_size,
        max_idle=300.0,
        reconnect_timeout=300.0,
        timeout=30.0,
        kwargs={
            "keepalives": 1,
            "keepalives_idle": 30,
            "keepalives_interval": 10,
            "keepalives_count": 5,
        },
        check=_check_connection,
        open=False,
    )
    await pool.open(wait=True)
    saver = AsyncPostgresSaver(pool)
    await saver.setup()
    return saver


async def get_checkpointer_pool(user_id: str) -> "AsyncPostgresSaver":
    """Return the pool singleton for ``user_id`` (8-pool sharded).

    The first call for a given ``pool_id`` constructs the pool;
    subsequent calls return the cached instance. Per-pool
    ``asyncio.Lock`` ensures only one coroutine builds a given pool,
    even under concurrent first-touch.
    """
    pool_id = get_pool_id(user_id)
    if pool_id in _pools:
        return _pools[pool_id]

    # Acquire per-pool lock (lazy create)
    async with _registry_lock:
        lock = _pool_locks.get(pool_id)
        if lock is None:
            lock = asyncio.Lock()
            _pool_locks[pool_id] = lock

    async with lock:
        # Double-check after acquiring the per-pool lock
        if pool_id in _pools:
            return _pools[pool_id]
        cfg = POOL_CONFIGS[pool_id]
        saver = await _create_pool(cfg)
        _pools[pool_id] = saver
        return saver


async def close_all_pools() -> None:
    """Gracefully shut down all 8 pools. Called from FastAPI lifespan."""
    for pool_id, saver in list(_pools.items()):
        try:
            # AsyncPostgresSaver doesn't expose close(); close the underlying pool.
            inner = getattr(saver, "pool", None) or getattr(saver, "_pool", None)
            if inner is not None and hasattr(inner, "close"):
                await inner.close()
        except Exception:
            # Best-effort cleanup — never raise from lifespan shutdown.
            pass
    _pools.clear()


# Test-only reset hook. Production code MUST NOT call this.
def _reset_pools_for_test() -> None:
    _pools.clear()
    _pool_locks.clear()


__all__ = [
    "CheckpointerPoolConfig",
    "POOL_CONFIGS",
    "close_all_pools",
    "get_checkpointer_pool",
    "get_pool_id",
]