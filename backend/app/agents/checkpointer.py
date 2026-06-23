"""023 — PostgreSQL checkpointer wrapper with retry + connection pool.

Encapsulates langgraph-checkpoint-postgres AsyncPostgresSaver.

Uses an explicit ``psycopg_pool.AsyncConnectionPool`` so FR-023/024/025
(pool sizing, TCP keepalive, check callback) actually take effect —
``AsyncPostgresSaver.from_conn_string`` ignores all pool_config and
uses a single ``AsyncConnection.connect`` under the hood (verified
against langgraph-checkpoint-postgres 1.0.9 ``aio.py``).

Singleton access with asyncio.Lock + double-check for concurrent safety.
"""
from __future__ import annotations

import asyncio
import contextlib
import sys
import time
from typing import TYPE_CHECKING, Any

import structlog

from app.agents.exceptions import CheckpointerUnavailableError

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


# ---------------------------------------------------------------------------
# Singleton state
# ---------------------------------------------------------------------------
_checkpointer: AsyncPostgresSaver | None = None
_pool: AsyncConnectionPool[Any] | None = None
_init_lock = asyncio.Lock()


async def get_checkpointer() -> AsyncPostgresSaver:
    """Return the singleton AsyncPostgresSaver with asyncio.Lock + double-check.

    Builds an explicit ``AsyncConnectionPool`` (FR-023/024/025) and wraps
    it in ``AsyncPostgresSaver(pool)``.  ``setup()`` is called once on
    first init — it is idempotent per LangGraph contract.
    """
    global _checkpointer, _pool

    if _checkpointer is not None:
        return _checkpointer

    async with _init_lock:
        if _checkpointer is not None:  # double-check
            return _checkpointer

        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        from psycopg_pool import AsyncConnectionPool

        sync_url = _stripped_db_url()
        # Build the pool ourselves so FR-023 (sizing), FR-024 (keepalive)
        # and FR-025 (check callback) actually take effect.  open=False
        # then await pool.open() so we can surface init errors here
        # instead of in the first graph op.
        pool = AsyncConnectionPool(
            conninfo=sync_url,
            min_size=_POOL_CONFIG["min_size"],
            max_size=_POOL_CONFIG["max_size"],
            max_idle=_POOL_CONFIG["max_idle"],
            reconnect_timeout=_POOL_CONFIG["reconnect_timeout"],
            timeout=_POOL_CONFIG["timeout"],
            kwargs={
                "keepalives": _POOL_CONFIG["keepalives"],
                "keepalives_idle": _POOL_CONFIG["keepalives_idle"],
                "keepalives_interval": _POOL_CONFIG["keepalives_interval"],
                "keepalives_count": _POOL_CONFIG["keepalives_count"],
            },
            check=_check_connection,  # FR-025
            open=False,
        )
        await pool.open(wait=True)
        saver = AsyncPostgresSaver(pool)
        await saver.setup()
        _pool = pool
        _checkpointer = saver
        logger.info(
            "checkpointer.initialized",
            pool_config=_POOL_CONFIG,
        )
        return _checkpointer


async def close_checkpointer() -> None:
    """Gracefully shut down the checkpointer + pool."""
    global _checkpointer, _pool
    if _pool is not None:
        try:
            await _pool.close()
        except Exception:
            logger.warning("checkpointer.cleanup_failed", exc_info=True)
    _checkpointer = None
    _pool = None
    logger.info("checkpointer.closed")


async def preheat() -> None:
    """Lifespan preheat: initialize checkpointer (setup() + pool.open()).

    ``get_checkpointer()`` already calls ``setup()`` + ``pool.open(wait=True)``
    so a successful return means the connection is live.  We deliberately
    do NOT probe with ``cp.list()`` — the sync ``list`` returns a generator
    (not a coroutine) in langgraph-checkpoint-postgres 1.0.9, so awaiting
    it crashes with ``TypeError``.  ``alist`` would also work but adds no
    signal beyond what ``setup()`` already proved.

    Logs success or warning — never raises (use in try/except).
    """
    ts = time.time()
    try:
        await get_checkpointer()
        elapsed = int((time.time() - ts) * 1000)
        logger.info(
            "checkpointer.preheat ok",
            elapsed_ms=elapsed,
            pool_config=_POOL_CONFIG,
        )
    except Exception:
        elapsed = int((time.time() - ts) * 1000)
        logger.warning(
            "checkpointer.preheat_failed",
            elapsed_ms=elapsed,
            exc_info=True,
        )


async def _force_rebuild() -> None:
    """Reset singleton state to force re-initialisation on next get().

    Used by retry paths and by integration tests that simulate an idle
    connection drop.  Cleanup errors are logged, not swallowed silently
    (FR: observability of pool teardown failures).
    """
    global _checkpointer, _pool
    if _pool is not None:
        try:
            await _pool.close()
        except Exception:
            logger.warning("checkpointer.cleanup_failed", exc_info=True)
    _checkpointer = None
    _pool = None


async def get_graph_config(
    thread_id: str, checkpoint_ns: str = ""
) -> dict[str, Any]:
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

    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        graph = await build_graph_fn()
        try:
            op = getattr(graph, op_name)
            if state_first:
                return await op(*args, config, **kwargs)
            return await op(config, *args, **kwargs)
        except Exception as exc:
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
    "CheckpointerUnavailableError",
    "close_checkpointer",
    "get_checkpointer",
    "get_graph_config",
    "preheat",
    "retry_graph_op",
]
