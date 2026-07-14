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
  ``AsyncConnectionPool`` whose connection-kwargs funnel through the
  shared ``build_checkpointer_connection_kwargs`` (REQ-081) so the
  saver's ``autocommit=True`` / ``prepare_threshold=0`` / ``dict_row``
  semantics match the locked ``AsyncPostgresSaver.from_conn_string``
  contract exactly.
- A failing pool rebuild is scoped to that pool_id — never
  force-rebuild all 8 pools. Pool open and saver setup failures close
  the partial pool, leave the slot uninitialised, and re-raise the
  original exception so the next caller for that slot can retry.
"""

from __future__ import annotations

import asyncio
import contextlib
import sys
from hashlib import md5
from typing import TYPE_CHECKING, Any

import structlog
from pydantic import BaseModel, Field

from app.agents.checkpointer import build_checkpointer_connection_kwargs

if TYPE_CHECKING:
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

# Windows: force SelectorEventLoop (psycopg rejects ProactorEventLoop).
if sys.platform.startswith("win"):
    with contextlib.suppress(AttributeError):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


logger = structlog.get_logger("agents.checkpointer_pool")


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
POOL_CONFIGS: list[CheckpointerPoolConfig] = [CheckpointerPoolConfig(pool_id=i) for i in range(8)]


# ---------------------------------------------------------------------------
# Pool registry (one slot per pool_id)
# ---------------------------------------------------------------------------
_pools: dict[int, AsyncPostgresSaver] = {}
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


async def _create_pool(cfg: CheckpointerPoolConfig) -> AsyncPostgresSaver:
    """Build a per-pool ``AsyncPostgresSaver`` + ``AsyncConnectionPool``.

    Connection-kwargs come from the shared
    ``build_checkpointer_connection_kwargs`` so the saver's
    ``autocommit=True`` / ``prepare_threshold=0`` / ``dict_row``
    semantics match the locked ``AsyncPostgresSaver.from_conn_string``
    contract (REQ-081).

    REQ-081 staged fail-closed:

    - Pre-pool stages (imports, URL, kwargs, pool ctor):  propagate
      the original exception — there is no pool to close; the caller
      sees ``pool_id not in _pools`` and can retry.
    - ``pool.open()`` failure: closes the partial pool, logs
      ``pool_open_failed``, re-raises.
    - ``AsyncPostgresSaver(pool)`` or ``saver.setup()`` failure:
      closes the open pool, logs ``saver_setup_failed``, re-raises.

    Concurrent / repeated first calls for the same pool_id are
    serialised by the per-pool lock (single-flight per slot).
    """
    import os

    os.environ.setdefault("LANGGRAPH_STRICT_MSGPACK", "true")

    # Stage 1 — imports, URL, pool ctor. No pool to close.
    try:
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
            kwargs=build_checkpointer_connection_kwargs(),
            check=_check_connection,
            open=False,
        )
    except Exception:
        raise

    # Stage 2 — pool.open()
    try:
        await pool.open(wait=True)
    except Exception:
        with contextlib.suppress(Exception):
            await pool.close()
        logger.warning(
            "checkpointer_pool.init_failed",
            pool_id=cfg.pool_id,
            state="down",
            reason="pool_open_failed",
        )
        raise

    # Stage 3 — saver construction + setup
    try:
        saver = AsyncPostgresSaver(pool)
        await saver.setup()
    except Exception:
        with contextlib.suppress(Exception):
            await pool.close()
        logger.warning(
            "checkpointer_pool.init_failed",
            pool_id=cfg.pool_id,
            state="down",
            reason="saver_setup_failed",
        )
        raise

    return saver


async def get_checkpointer_pool(user_id: str) -> AsyncPostgresSaver:
    """Return the pool singleton for ``user_id`` (8-pool sharded).

    The first call for a given ``pool_id`` constructs the pool;
    subsequent calls return the cached instance. Per-pool
    ``asyncio.Lock`` ensures only one coroutine builds a given pool,
    even under concurrent first-touch. A failing pool rebuild is
    scoped to that ``pool_id`` — never force-rebuilt across all 8
    pools — so shards remain independent.
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
    """Gracefully shut down all 8 pools. Called from FastAPI lifespan.

    REQ-081: every sharded pool's underlying ``AsyncConnectionPool`` is
    awaited exactly once per registry entry — the ``saver.conn``
    attribute holds the pool per the locked
    ``AsyncPostgresSaver.__init__`` (``self.conn = conn`` — see
    langgraph-checkpoint-postgres ``aio.py``). The legacy
    ``saver.pool`` / ``saver._pool`` lookup is gone because it
    silently fell through when ``conn`` is the source of truth.

    Idempotent: tolerates already-closed pools and a fully-empty
    registry. Always clears the registry so the next
    ``get_checkpointer_pool(user_id)`` rebuilds from a clean slate.
    """
    if not _pools:
        logger.info(
            "checkpointer_pool.closed_all",
            state="noop",
            reason="empty_registry",
        )
        return
    # Claim the registry before the first await. Overlapping/repeated
    # shutdown calls then cannot close the same saver.conn twice.
    claimed_pools = list(_pools.items())
    _pools.clear()
    for pool_id, saver in claimed_pools:
        # Locked langgraph-checkpoint-postgres ``AsyncPostgresSaver``
        # exposes the underlying conn (which is our
        # ``AsyncConnectionPool``) as the public ``saver.conn``
        # attribute. ``pool`` / ``_pool`` are not part of the contract.
        inner = getattr(saver, "conn", None)
        if inner is not None and hasattr(inner, "close"):
            try:
                await inner.close()
            except Exception:
                # Best-effort cleanup — never raise from lifespan shutdown.
                logger.warning(
                    "checkpointer_pool.cleanup_failed",
                    pool_id=pool_id,
                    state="error",
                    reason="pool_close_raised",
                )
    logger.info(
        "checkpointer_pool.closed_all",
        state="ok",
        reason="pools_closed",
    )


# Test-only reset hook. Production code MUST NOT call this.
def _reset_pools_for_test() -> None:
    _pools.clear()
    _pool_locks.clear()


__all__ = [
    "POOL_CONFIGS",
    "CheckpointerPoolConfig",
    "close_all_pools",
    "get_checkpointer_pool",
    "get_pool_id",
]
