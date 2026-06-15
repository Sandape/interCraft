"""PostgreSQL checkpointer wrapper (T013).

Encapsulates langgraph-checkpoint-postgres initialization.
from_conn_string is an async context manager — we enter it once
and keep the connection alive for the app lifetime.
"""
from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

# psycopg (used by langgraph-checkpoint-postgres) rejects the
# ProactorEventLoop that uvicorn creates on Windows. Force a
# SelectorEventLoop here so the checkpointer initialises under a
# compatible loop, even if the host policy wasn't set before uvicorn
# imported its loop factory.
if sys.platform.startswith("win"):
    import asyncio

    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except AttributeError:
        pass

_checkpointer: AsyncPostgresSaver | None = None
_cleanup_ctx = None


async def get_checkpointer() -> AsyncPostgresSaver:
    """Create/return a singleton AsyncPostgresSaver.

    The underlying from_conn_string context manager is entered once
    and stays alive for the process lifetime.
    """
    global _checkpointer, _cleanup_ctx
    if _checkpointer is not None:
        return _checkpointer

    from app.core.config import get_settings
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver as PgSaver

    database_url = get_settings().database_url
    # Strip +asyncpg or +psycopg driver prefix since psycopg expects plain postgresql://
    sync_url = database_url
    for prefix in ("+asyncpg", "+psycopg"):
        sync_url = sync_url.replace(prefix, "")

    _cleanup_ctx = PgSaver.from_conn_string(sync_url)
    _checkpointer = await _cleanup_ctx.__aenter__()
    await _checkpointer.setup()
    return _checkpointer


async def close_checkpointer() -> None:
    """Gracefully shut down the checkpointer connection."""
    global _checkpointer, _cleanup_ctx
    if _cleanup_ctx is not None:
        await _cleanup_ctx.__aexit__(None, None, None)
        _checkpointer = None
        _cleanup_ctx = None


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


__all__ = ["get_checkpointer", "close_checkpointer", "get_graph_config"]
