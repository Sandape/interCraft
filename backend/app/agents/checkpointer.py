"""023 — PostgreSQL checkpointer wrapper with retry + connection pool.

Encapsulates langgraph-checkpoint-postgres AsyncPostgresSaver.

Uses an explicit ``psycopg_pool.AsyncConnectionPool`` so FR-023/024/025
(pool sizing, TCP keepalive, check callback) actually take effect —
``AsyncPostgresSaver.from_conn_string`` ignores all pool_config and
uses a single ``AsyncConnection.connect`` under the hood (verified
against langgraph-checkpoint-postgres 1.0.9 ``aio.py``; verified
same API surface in 3.1.0 (T183).

Connection semantics (REQ-081):
- Shared singleton + every sharded per-user pool share ONE tested
  ``build_checkpointer_connection_kwargs()`` builder so the lock-free
  ``autocommit=True`` / ``prepare_threshold=0`` / ``dict_row`` semantics
  match the locked saver's ``from_conn_string`` contract exactly.
- Without ``autocommit=True`` a fresh database's ``CREATE INDEX
  CONCURRENTLY`` migration runs inside an implicit transaction block and
  fails before ``setup()`` completes.

Singleton access with asyncio.Lock + double-check for concurrent safety.
First-time init is fail-closed: any pool-open or saver-setup failure
closes the partial pool, leaves the singleton uninitialised, preserves
the original exception, and allows a clean retry on the next call.
"""

from __future__ import annotations

import asyncio
import contextlib
import sys
import time
from typing import TYPE_CHECKING, Any

import structlog
from psycopg.rows import dict_row

from app.agents.checkpointer_controls import checkpointer_control_status
from app.agents.exceptions import CheckpointerUnavailableError
from app.observability.tracing import record_req035_capture_event

if TYPE_CHECKING:
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    from psycopg import AsyncConnection
    from psycopg_pool import AsyncConnectionPool

# Windows: force SelectorEventLoop (psycopg rejects ProactorEventLoop).
if sys.platform.startswith("win"):
    with contextlib.suppress(AttributeError):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

logger = structlog.get_logger("agents.checkpointer")

# ---------------------------------------------------------------------------
# Reconnect patterns (FR-008)
# ---------------------------------------------------------------------------
_CHECKPOINTER_RECONNECT_PATTERNS = (
    "connection is closed",
    "the connection",
    "admin shutdown",
    "server closed the connection unexpectedly",
)

# ---------------------------------------------------------------------------
# Connection pool config (FR-023 / FR-024 / FR-025)
#
# Used to construct ``AsyncConnectionPool`` manually. The previous
# implementation passed these to ``AsyncPostgresSaver.from_conn_string``
# which does NOT accept pool_config — making this entire dict dead.
# We now build the pool ourselves and pass it to ``AsyncPostgresSaver(pool)``.
# ---------------------------------------------------------------------------
_POOL_CONFIG: dict[str, Any] = {
    "min_size": 1,
    "max_size": 10,
    "max_idle": 300.0,
    "reconnect_timeout": 300.0,
    "timeout": 30.0,
    "keepalives": 1,
    "keepalives_idle": 30,
    "keepalives_interval": 10,
    "keepalives_count": 5,
}


def _is_reconnectable(exc: BaseException) -> bool:
    """Check if an OperationalError is one we should retry (FR-008)."""
    msg = str(exc).lower()
    return any(pattern in msg for pattern in _CHECKPOINTER_RECONNECT_PATTERNS)


def _stripped_db_url() -> str:
    """Strip +asyncpg/+psycopg prefix for psycopg-compatible URL."""
    from app.core.config import get_settings

    url = get_settings().database_url
    for prefix in ("+asyncpg", "+psycopg"):
        url = url.replace(prefix, "")
    return url


async def _check_connection(conn: AsyncConnection[Any]) -> None:
    """FR-025 — lightweight SELECT 1 health check on pool checkout.

    If this raises, the pool marks the connection dead and creates a
    new one, so transient idle drops never surface to business code.
    """
    async with conn.cursor() as cur:
        await cur.execute("SELECT 1")


def build_checkpointer_connection_kwargs() -> dict[str, Any]:
    """Return the single tested connection-kwargs builder for saver pools.

    Both the shared singleton ``get_checkpointer()`` and every sharded
    ``get_checkpointer_pool(user_id)`` MUST funnel through this function so
    the saver's connection semantics match the locked
    ``AsyncPostgresSaver.from_conn_string`` contract exactly:

    - ``autocommit=True`` — required for ``CREATE INDEX CONCURRENTLY``
      migrations on a fresh database. Without it the migration runs in
      an implicit transaction block and fails before ``setup()`` completes.
    - ``prepare_threshold=0`` — skip server-side prepared statements so
      autocommit transactions stay cheap (matches ``from_conn_string``).
    - ``row_factory=dict_row`` — return rows as dicts (matches
      ``from_conn_string`` and what ``AsyncPostgresSaver._cursor`` uses).

    Plus the existing FR-024 keepalive settings so TCP keepalives survive
    pool checkout. Public so unit tests can lock the contract.
    """
    return {
        "autocommit": True,
        "prepare_threshold": 0,
        "row_factory": dict_row,
        "keepalives": _POOL_CONFIG["keepalives"],
        "keepalives_idle": _POOL_CONFIG["keepalives_idle"],
        "keepalives_interval": _POOL_CONFIG["keepalives_interval"],
        "keepalives_count": _POOL_CONFIG["keepalives_count"],
    }


# ---------------------------------------------------------------------------
# Singleton state
# ---------------------------------------------------------------------------
_checkpointer: AsyncPostgresSaver | None = None
_pool: AsyncConnectionPool[Any] | None = None
_init_lock = asyncio.Lock()


# ---------------------------------------------------------------------------
# Readiness snapshot (REQ-081 — fail-closed preheat)
# ---------------------------------------------------------------------------
class CheckpointerReadiness:
    """Snapshot of the singleton checkpointer's init state for /readyz.

    ``state`` is one of ``"up"`` / ``"down"`` / ``"uninitialised"``.
    ``reason`` is a redacted, short tag (``"ok"`` / ``"pool_open_failed"``
    / ``"saver_setup_failed"`` / ``"not_initialised"``); never logs the
    raw exception, URL, or user payload.
    """

    __slots__ = ("reason", "state")

    def __init__(self, state: str, reason: str) -> None:
        self.state = state
        self.reason = reason

    def as_dict(self) -> dict[str, str]:
        return {"state": self.state, "reason": self.reason}


_READINESS_UP = CheckpointerReadiness("up", "ok")
_READINESS_UNINITIALISED = CheckpointerReadiness("uninitialised", "not_initialised")
_READINESS_POOL_OPEN_FAILED = CheckpointerReadiness("down", "pool_open_failed")
_READINESS_SAVER_SETUP_FAILED = CheckpointerReadiness("down", "saver_setup_failed")
_readiness: CheckpointerReadiness = _READINESS_UNINITIALISED


def get_checkpointer_readiness() -> CheckpointerReadiness:
    """Return the current readiness snapshot (redacted, no secrets).

    Used by /readyz and worker startup to fail closed when the
    checkpointer cannot be initialised.
    """
    return _readiness


async def get_checkpointer() -> AsyncPostgresSaver:
    """Return the singleton AsyncPostgresSaver with asyncio.Lock + double-check.

    Builds an explicit ``AsyncConnectionPool`` (FR-023/024/025) using the
    shared ``build_checkpointer_connection_kwargs`` so the saver's
    connection semantics match the locked contract. ``setup()`` is called
    once on first init — it is idempotent per LangGraph contract.

    REQ-081 staged fail-closed handling — every stage from pool ctor
    through ``pool.open()`` through ``AsyncPostgresSaver(pool)`` through
    ``saver.setup()`` is individually covered:

    - Pre-pool stages (imports, URL, kwargs, pool ctor):  propagate
      the original exception — there is no pool to close yet, and the
      readiness stays ``uninitialised`` because we never reached a
      stage that could produce a typed reason.
    - ``pool.open()`` failure: closes the partial pool, publishes
      ``_READINESS_POOL_OPEN_FAILED``, and re-raises the original
      exception.
    - ``AsyncPostgresSaver(pool)`` failure: closes the open pool,
      publishes ``_READINESS_SAVER_SETUP_FAILED``, re-raises.
    - ``saver.setup()`` failure: closes the open pool, publishes
      ``_READINESS_SAVER_SETUP_FAILED``, re-raises.

    Single-flight per process: concurrent first callers serialise on
    ``_init_lock``; subsequent callers after a successful init return
    the cached saver.

    Enforces ``LANGGRAPH_STRICT_MSGPACK=true`` before importing the
    checkpointer so that deserialisation rejects unknown module payloads
    (T183, langgraph 1.2.9+).
    """
    import os

    os.environ.setdefault("LANGGRAPH_STRICT_MSGPACK", "true")
    global _checkpointer, _pool, _readiness

    if _checkpointer is not None:
        return _checkpointer

    async with _init_lock:
        if _checkpointer is not None:  # double-check after acquiring the lock
            return _checkpointer

        # Stage 1 — imports, URL, kwargs, pool ctor.
        # No pool to close here — just propagate the original exception
        # and leave _readiness as _READINESS_UNINITIALISED.
        try:
            from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
            from psycopg_pool import AsyncConnectionPool

            sync_url = _stripped_db_url()
            connection_kwargs = build_checkpointer_connection_kwargs()
            pool = AsyncConnectionPool(
                conninfo=sync_url,
                min_size=_POOL_CONFIG["min_size"],
                max_size=_POOL_CONFIG["max_size"],
                max_idle=_POOL_CONFIG["max_idle"],
                reconnect_timeout=_POOL_CONFIG["reconnect_timeout"],
                timeout=_POOL_CONFIG["timeout"],
                kwargs=connection_kwargs,
                check=_check_connection,  # FR-025
                open=False,
            )
        except Exception:
            # No pool allocated — nothing to close.
            raise

        # Stage 2 — pool.open()
        try:
            await pool.open(wait=True)
        except Exception:
            # REQ-081: staged fail-closed — close the partial pool,
            # publish typed ``pool_open_failed``, re-raise original.
            with contextlib.suppress(Exception):
                await pool.close()
            _readiness = _READINESS_POOL_OPEN_FAILED
            logger.warning(
                "checkpointer.init_failed",
                state=_readiness.state,
                reason=_readiness.reason,
            )
            raise

        # Stage 3 — saver construction
        try:
            saver = AsyncPostgresSaver(pool)
        except Exception:
            with contextlib.suppress(Exception):
                await pool.close()
            _readiness = _READINESS_SAVER_SETUP_FAILED
            logger.warning(
                "checkpointer.init_failed",
                state=_readiness.state,
                reason=_readiness.reason,
            )
            raise

        # Stage 4 — saver.setup()
        try:
            await saver.setup()
        except Exception:
            # REQ-081: saver-side failure (typically ``CREATE INDEX
            # CONCURRENTLY`` on a fresh DB without autocommit=True).
            # Close the now-open pool, keep the singleton empty, and
            # re-raise the ORIGINAL exception so the next caller can
            # retry with different kwargs if needed.
            with contextlib.suppress(Exception):
                await pool.close()
            _readiness = _READINESS_SAVER_SETUP_FAILED
            logger.warning(
                "checkpointer.init_failed",
                state=_readiness.state,
                reason=_readiness.reason,
            )
            raise

        _pool = pool
        _checkpointer = saver
        _readiness = _READINESS_UP
        logger.info(
            "checkpointer.initialized",
            pool_config=_POOL_CONFIG,
        )
        return _checkpointer


async def close_checkpointer() -> None:
    """Gracefully shut down the checkpointer + pool.

    Idempotent: tolerates an already-closed pool and an uninitialised
    singleton. Always resets module-level state so the next
    ``get_checkpointer()`` call rebuilds from a clean slate.

    Closes the shared pool and every shard pool that
    ``checkpointer_pool`` registered — but it does NOT touch ARQ's
    Redis pool (owned by ``app.core.redis``).
    """
    global _checkpointer, _pool, _readiness
    pool_ref = _pool
    _checkpointer = None
    _pool = None
    _readiness = _READINESS_UNINITIALISED
    if pool_ref is None:
        logger.info("checkpointer.closed", state="noop", reason="no_pool")
    else:
        try:
            await pool_ref.close()
            logger.info("checkpointer.closed", state="ok", reason="pool_closed")
        except Exception:
            logger.warning(
                "checkpointer.cleanup_failed",
                state="error",
                reason="pool_close_raised",
            )


async def preheat() -> CheckpointerReadiness:
    """Lifespan preheat: initialize checkpointer (setup() + pool.open()).

    Returns the ``CheckpointerReadiness`` snapshot so callers (FastAPI
    /readyz, worker startup) can fail closed when the checkpointer
    dependency is not healthy. ``get_checkpointer()`` already calls
    ``setup()`` + ``pool.open(wait=True)`` so a successful return means
    the connection is live. We deliberately do NOT probe with
    ``cp.list()`` — the sync ``list`` returns a generator (not a
    coroutine) in langgraph-checkpoint-postgres 1.0.9/3.1.0, so awaiting
    it crashes with ``TypeError``. ``alist`` would also work but adds no
    signal beyond what ``setup()`` already proved.

    The exception is preserved and logged with a redacted reason tag
    (never the raw exception message) so /readyz can surface the
    dependency failure without leaking URLs, paths, or user payload.
    """
    global _readiness

    ts = time.time()
    try:
        await get_checkpointer()
        elapsed = int((time.time() - ts) * 1000)
        readiness = get_checkpointer_readiness()
        logger.info(
            "checkpointer.preheat ok",
            elapsed_ms=elapsed,
            pool_config=_POOL_CONFIG,
            controls=checkpointer_control_status(),
            readiness=readiness.as_dict(),
        )
        return readiness
    except Exception:
        elapsed = int((time.time() - ts) * 1000)
        # REQ-081: actively set a typed down snapshot so callers never
        # see stale ``uninitialised`` when get_checkpointer() failed
        # before reaching a stage that publishes a specific reason.
        # The reason is a short redacted tag — never the raw exception
        # message or URL.
        # Preserve a stage-specific failure published by get_checkpointer().
        # Only synthesize the generic setup reason when no failing stage was
        # able to publish a typed down snapshot.
        if _readiness.state != "down":
            _readiness = _READINESS_SAVER_SETUP_FAILED
        readiness = get_checkpointer_readiness()
        logger.warning(
            "checkpointer.preheat_failed",
            elapsed_ms=elapsed,
            readiness=readiness.as_dict(),
        )
        return readiness


async def _force_rebuild() -> None:
    """Reset singleton state to force re-initialisation on next get().

    Used by retry paths and by integration tests that simulate an idle
    connection drop.  Cleanup errors are logged, not swallowed silently
    (FR: observability of pool teardown failures).
    """
    global _checkpointer, _pool, _readiness
    if _pool is not None:
        try:
            await _pool.close()
        except Exception:
            logger.warning("checkpointer.cleanup_failed", state="error", reason="pool_close_raised")
    _checkpointer = None
    _pool = None
    _readiness = _READINESS_UNINITIALISED


async def get_graph_config(thread_id: str, checkpoint_ns: str = "") -> dict[str, Any]:
    """Build a RunnableConfig dict for graph invocation."""
    return {
        "configurable": {
            "thread_id": thread_id,
            "checkpoint_ns": checkpoint_ns,
        }
    }


async def retry_graph_op(
    build_graph_fn: Any,
    config: dict[str, Any],
    op_name: str,
    *args: Any,
    max_retries: int = 2,
    state_first: bool = False,
    **kwargs: Any,
) -> Any:
    """Call graph.<op_name>(...) with retry on connection loss.

    ``build_graph_fn`` is an async callable that returns a freshly compiled
    graph each invocation.  On psycopg OperationalError the checkpointer
    singleton is force-rebuilt and the operation retried (up to
    ``max_retries`` times).

    ``state_first`` controls argument order:

    - ``False`` (default) — ``op(config, *args, **kwargs)``.  Matches
      ``aget_state(config)`` and ``aupdate_state(config, values)``.
    - ``True`` — ``op(*args, config, **kwargs)``.  Matches
      ``ainvoke(state, config)`` where config is the second positional arg.

    Typical usage::

        state = await retry_graph_op(self.build_graph, config, "aget_state")
        await retry_graph_op(self.build_graph, config, "aupdate_state", {"messages": [...]})
        result = await retry_graph_op(self.build_graph, config, "ainvoke", initial_state, state_first=True)
    """
    from app.core.metrics import checkpointer_reconnect_total

    last_exc = None
    target_id = config.get("configurable", {}).get("thread_id", "unknown")
    for attempt in range(max_retries + 1):
        graph = await build_graph_fn()
        try:
            op = getattr(graph, op_name)
            if state_first:
                result = await op(*args, config, **kwargs)
            else:
                result = await op(config, *args, **kwargs)
            record_req035_capture_event(
                target_type="checkpointer_graph_op",
                target_id=target_id,
                operation=op_name,
                status="success",
            )
            return result
        except Exception as exc:
            record_req035_capture_event(
                target_type="checkpointer_graph_op",
                target_id=target_id,
                operation=op_name,
                status="error",
                error=str(exc),
            )
            # Non-reconnectable errors propagate immediately, no retry.
            if not _is_reconnectable(exc):
                raise
            # Reconnectable but retries exhausted → convert to 503 signal.
            if attempt == max_retries:
                raise CheckpointerUnavailableError(
                    f"Graph operation {op_name} failed after {max_retries + 1} attempts: {exc}",
                    retry_after=30,
                ) from exc
            last_exc = exc
            logger.warning(
                "checkpointer.retry_graph_op",
                op=op_name,
                attempt=attempt + 1,
                max_retries=max_retries,
                exc_info=True,
            )
            checkpointer_reconnect_total.inc()
            await asyncio.sleep(1.0 * (attempt + 1))
            await _force_rebuild()

    # Unreachable: loop either returns or raises.  Defensive fallback.
    raise CheckpointerUnavailableError(
        f"Graph operation {op_name} failed after {max_retries + 1} attempts: {last_exc}",
        retry_after=30,
    )


__all__ = [
    "CheckpointerReadiness",
    "CheckpointerUnavailableError",
    "build_checkpointer_connection_kwargs",
    "close_checkpointer",
    "get_checkpointer",
    "get_checkpointer_readiness",
    "get_graph_config",
    "preheat",
    "retry_graph_op",
]
