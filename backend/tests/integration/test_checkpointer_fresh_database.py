"""REQ-081 — Checkpointer against a truly fresh PostgreSQL database.

Validates the single shipped connection-kwargs builder
(``build_checkpointer_connection_kwargs``) end-to-end against a
truly fresh PostgreSQL catalog. The test only runs when
``INTERCRAFT_TEST_CHECKPOINTER_FRESH_DB_URL`` is set to a
test-exclusively-owned PostgreSQL URL — without that env var the test
module is skipped. The CI ``checkpointer-fresh-db`` job sees zero skips
when it sets the env.

Contract (REQ-081):
1. Isolated-DB opt-in via ``INTERCRAFT_TEST_CHECKPOINTER_FRESH_DB_URL``
   with a strong guard that the database name contains ``fresh`` or
   ``test`` — a shared or production URL is rejected with test failure
   before any mutation.
2. Assert truly FRESH catalog: the test FAILS if any ``checkpoint_*``
   table exists before we start.  No DROP-before-assert — we never
   mutate until ownership is proven.
3. Invoke shipped ``get_checkpointer()`` (shared singleton) and
   ``get_checkpointer_pool()`` (one shard) so ``pool.open()`` +
   ``saver.setup()`` run with the exact kwargs the production app
   passes through ``build_checkpointer_connection_kwargs``.
4. All saver tables / indexes / latest migration must exist after
   ``setup()``.  ``checkpoint_migrations`` MAX(v) must equal
   ``len(MIGRATIONS) - 1`` (the locked ten-migration contract).
5. Real ``aput`` + ``aget_tuple`` round-trip on BOTH the shared
   singleton saver and a per-shard saver.
6. ``close_all_pools()`` traverses ``saver.conn`` (the real public
   pool attribute, not ``.pool`` or ``._pool``) and is idempotent.
7. Strict cleanup of module caches and saver tables after each test
   (teardown only runs after a successful setup proved ownership).
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from urllib.parse import unquote, urlsplit
from uuid import uuid4

import pytest
from psycopg.rows import dict_row
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = [pytest.mark.integration]

_FRESH_DB_ENV = "INTERCRAFT_TEST_CHECKPOINTER_FRESH_DB_URL"
_FRESH_DB_OWNED_ENV = "INTERCRAFT_TEST_CHECKPOINTER_FRESH_DB_OWNED"
_FRESH_DB_NAME_PREFIX = "checkpointer_fresh"

_EXPECTED_TABLES = frozenset(
    {
        "checkpoint_migrations",
        "checkpoints",
        "checkpoint_blobs",
        "checkpoint_writes",
    }
)
_EXPECTED_INDEXES = (
    "checkpoints_thread_id_idx",
    "checkpoint_blobs_thread_id_idx",
    "checkpoint_writes_thread_id_idx",
)
_EXPECTED_LATEST_MIGRATION_COLUMN = ("checkpoint_writes", "task_path")

# Locked migration version (langgraph-checkpoint-postgres MIGRATIONS):
#   - MIGRATIONS[0] creates the checkpoint_migrations tracking table.
#   - setup() then iterates MIGRATIONS[0:] (not [1:] — when version=-1,
#     ``version + 1 = 0``, so the slice starts at index 0).
#   - The loop runs len(MIGRATIONS) times; the last INSERT v = len-1.
try:
    from langgraph.checkpoint.postgres.base import BasePostgresSaver

    _MIGRATIONS_LEN = len(BasePostgresSaver.MIGRATIONS)
except ImportError:
    _MIGRATIONS_LEN = 10  # locked version fallback

_EXPECTED_LATEST_MIGRATION_VERSION = _MIGRATIONS_LEN - 1


def _require_fresh_db_url() -> str:
    """Return the env var value or skip the test module.

    REQ-081 isolated-DB guard: require the dedicated name
    ``checkpointer_fresh`` (optionally suffixed with ``_...``) and an
    explicit ownership marker. Failure messages expose only a sanitized
    database name, never URL credentials or host details.
    """
    url = os.environ.get(_FRESH_DB_ENV)
    if not url:
        pytest.skip(
            f"{_FRESH_DB_ENV} not set; checkpointer-fresh-db contract "
            "is opt-in to keep shared services untouched"
        )
    db_name = unquote(urlsplit(url).path.lstrip("/"))
    safe_db_name = (
        db_name
        if db_name
        and len(db_name) <= 128
        and all(char.isalnum() or char in "_-" for char in db_name)
        else "<invalid>"
    )
    dedicated_name = db_name == _FRESH_DB_NAME_PREFIX or db_name.startswith(
        f"{_FRESH_DB_NAME_PREFIX}_"
    )
    if not dedicated_name:
        pytest.fail(
            f"database name {safe_db_name!r} is not dedicated to the fresh-DB "
            f"contract; expected {_FRESH_DB_NAME_PREFIX!r} or that prefix plus '_'"
        )
    if os.environ.get(_FRESH_DB_OWNED_ENV) != "1":
        pytest.fail(
            f"database name {safe_db_name!r} requires explicit "
            f"{_FRESH_DB_OWNED_ENV}=1 ownership confirmation"
        )
    return url


@pytest.fixture
def fresh_db_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set up env for the fresh-DB contract, returning nothing (no DSN leak).

    The raw URL is used internally to set ``DATABASE_URL`` but is never
    returned or exposed in pytest test-node output.  Error messages use
    only ``safe_db_name``, never URL credentials or host.
    """
    url = _require_fresh_db_url()
    monkeypatch.setenv("DATABASE_URL", url)
    try:
        from app.core.config import get_settings

        get_settings.cache_clear()  # type: ignore[attr-defined]
    except AttributeError:
        pass


@pytest.fixture
async def fresh_db_session(fresh_db_configured: None) -> AsyncIterator[AsyncSession]:
    from app.core.db import _session_cm

    async with _session_cm() as session:
        try:
            yield session
        finally:
            # Each contract test must remain independent even when the prior
            # assertion fails after setup created the saver tables.
            from app.agents.checkpointer import close_checkpointer
            from app.agents.checkpointer_pool import close_all_pools

            await close_all_pools()
            await close_checkpointer()
            await _teardown_tables(session)


async def _assert_empty_catalog(session: AsyncSession) -> None:
    """Fail unless the catalog has zero checkpoint_* tables.

    No DROP is executed — we only READ.  This proves the database is
    truly fresh before any mutation by the test.
    """
    result = await session.execute(
        text(
            "SELECT tablename FROM pg_tables WHERE tablename LIKE 'checkpoint%' ORDER BY tablename"
        )
    )
    tables = [row[0] for row in result.fetchall()]
    assert tables == [], (
        f"Contract requires a truly fresh catalog (no checkpoint_* tables). "
        f"Found {tables}. The CI job must create the database per invocation."
    )
    # The catalog SELECT implicitly starts a transaction. Release that old
    # snapshot before saver.setup() runs CREATE INDEX CONCURRENTLY, otherwise
    # PostgreSQL correctly waits for this session and the contract deadlocks
    # itself until the outer CI timeout.
    await session.rollback()


async def _teardown_tables(session: AsyncSession) -> None:
    """Drop saver tables after a successful contract test.

    Only called after the test proved ownership and successfully
    exercised the saver.  If teardown fails, the CI runner drops
    the entire database at job exit.
    """
    for table in (
        "checkpoint_writes",
        "checkpoint_blobs",
        "checkpoints",
        "checkpoint_migrations",
    ):
        await session.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE"))
    await session.commit()


def _make_checkpoint(thread_id: str) -> tuple[dict, dict, dict]:
    """A minimal checkpoint triple for round-trip tests."""
    config = {"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}}
    checkpoint = {
        "v": 4,
        "id": f"cp-{thread_id}",
        "ts": "2026-07-14T00:00:00+00:00",
        "channel_versions": {"messages": "1"},
        "channel_values": {"messages": ["hello fresh"]},
        "pending_sends": [],
    }
    metadata = {"source": "input", "step": 0, "writes": {}, "parents": {}}
    return config, checkpoint, metadata


# ---------------------------------------------------------------------------
# Contract — first pytest invocation in the ``checkpointer-fresh-db`` CI job.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_shared_singleton_setup_and_round_trip(
    fresh_db_configured: None,
    fresh_db_session: AsyncSession,
) -> None:
    """REQ-081: shared singleton — empty catalog, setup, tables, shared round-trip, conn close."""
    # Step 1 — assert FRESH catalog (no DROP, no mutation).
    await _assert_empty_catalog(fresh_db_session)

    from app.agents import checkpointer as cp_module
    from app.agents.checkpointer import (
        build_checkpointer_connection_kwargs,
        close_checkpointer,
        get_checkpointer,
        get_checkpointer_readiness,
    )

    cp_module._checkpointer = None
    cp_module._pool = None
    cp_module._readiness = cp_module._READINESS_UNINITIALISED

    # Step 2 — verify the shared kwargs contract.
    kwargs = build_checkpointer_connection_kwargs()
    assert kwargs["autocommit"] is True
    assert kwargs["prepare_threshold"] == 0
    assert kwargs["row_factory"] is dict_row

    # Step 3 — invoke shipped shared singleton init.
    saver = await get_checkpointer()
    assert saver is not None
    shared_pool = saver.conn

    readiness = get_checkpointer_readiness()
    assert readiness.state == "up", readiness.as_dict()

    # Step 4 — verify saver tables + indexes + latest migration.
    result = await fresh_db_session.execute(
        text(
            "SELECT tablename FROM pg_tables WHERE tablename LIKE 'checkpoint%' ORDER BY tablename"
        )
    )
    tables = frozenset(row[0] for row in result.fetchall())
    assert tables == _EXPECTED_TABLES, f"expected {_EXPECTED_TABLES}, got {tables}"

    index_rows = await fresh_db_session.execute(
        text(
            "SELECT indexname FROM pg_indexes "
            "WHERE indexname LIKE 'checkpoint%' AND tablename LIKE 'checkpoint%' "
            "ORDER BY indexname"
        )
    )
    indexes = tuple(row[0] for row in index_rows.fetchall())
    for expected in _EXPECTED_INDEXES:
        assert expected in indexes, f"missing index {expected!r}; got {indexes}"

    table, column = _EXPECTED_LATEST_MIGRATION_COLUMN
    col_row = await fresh_db_session.execute(
        text(
            "SELECT 1 FROM information_schema.columns "
            f"WHERE table_name = '{table}' AND column_name = '{column}'"
        )
    )
    assert col_row.scalar() == 1, f"latest migration column {table}.{column} not present"

    version_row = await fresh_db_session.execute(
        text("SELECT MAX(v) AS v FROM checkpoint_migrations")
    )
    max_v = version_row.scalar()
    assert max_v == _EXPECTED_LATEST_MIGRATION_VERSION, (
        f"expected max migration version {_EXPECTED_LATEST_MIGRATION_VERSION}, got {max_v}"
    )

    # Step 5 — shared saver aput/aget_tuple round trip.
    tid = f"fresh-shared-{uuid4().hex[:12]}"
    config, checkpoint, metadata = _make_checkpoint(tid)
    new_versions: dict[str, str] = {"messages": "1"}

    next_config = await saver.aput(config, checkpoint, metadata, new_versions)
    assert next_config["configurable"]["thread_id"] == tid

    loaded = await saver.aget_tuple({"configurable": {"thread_id": tid}})
    assert loaded is not None, "shared saver aput/aget_tuple round-trip failed"
    assert loaded.checkpoint["channel_values"]["messages"] == ["hello fresh"]
    assert loaded.metadata["source"] == "input"

    # Row exists in the fresh catalog.
    row_count = await fresh_db_session.execute(
        text("SELECT COUNT(*) FROM checkpoints WHERE thread_id = :tid"),
        {"tid": tid},
    )
    assert row_count.scalar() == 1

    # Step 6 — saver.conn is the real pool.
    assert saver.conn is cp_module._pool, "shared saver.conn must match module-level _pool"

    # Step 7 — cleanup.
    await close_checkpointer()
    assert shared_pool.closed is True
    assert cp_module._pool is None
    assert cp_module._checkpointer is None
    assert cp_module._readiness.state == "uninitialised"
    await close_checkpointer()
    assert shared_pool.closed is True
    await _teardown_tables(fresh_db_session)


@pytest.mark.asyncio
async def test_shard_pool_round_trip_and_conn_close(
    fresh_db_configured: None,
    fresh_db_session: AsyncSession,
) -> None:
    """REQ-081: one shard — empty catalog, setup, round trip, close_all_pools via saver.conn."""
    # Step 1 — assert FRESH catalog.
    await _assert_empty_catalog(fresh_db_session)

    from app.agents import checkpointer as cp_module
    from app.agents import checkpointer_pool as pool_module
    from app.agents.checkpointer import close_checkpointer
    from app.agents.checkpointer_pool import close_all_pools, get_checkpointer_pool

    cp_module._checkpointer = None
    cp_module._pool = None
    cp_module._readiness = cp_module._READINESS_UNINITIALISED
    pool_module._pools.clear()
    pool_module._pool_locks.clear()

    # Step 2 — init one shard.
    user_id = f"019ec1be-{uuid4().hex[:12]}"
    saver = await get_checkpointer_pool(user_id)
    assert saver is not None

    # Step 3 — saver.conn is the real pool (locked AsyncPostgresSaver
    # stores the pool as the public ``conn`` attribute).
    inner_pool = getattr(saver, "conn", None)
    assert inner_pool is not None, "shard saver must expose conn (the underlying pool)"
    assert hasattr(inner_pool, "close"), "saver.conn must be the pool (has .close)"

    # Tables exist.
    result = await fresh_db_session.execute(
        text(
            "SELECT tablename FROM pg_tables WHERE tablename LIKE 'checkpoint%' ORDER BY tablename"
        )
    )
    tables = frozenset(row[0] for row in result.fetchall())
    assert tables == _EXPECTED_TABLES, f"expected {_EXPECTED_TABLES}, got {tables}"

    # Step 4 — shard saver aput/aget_tuple round trip.
    tid = f"fresh-shard-{uuid4().hex[:12]}"
    config, checkpoint, metadata = _make_checkpoint(tid)
    new_versions: dict[str, str] = {"messages": "1"}

    next_config = await saver.aput(config, checkpoint, metadata, new_versions)
    assert next_config["configurable"]["thread_id"] == tid

    loaded = await saver.aget_tuple({"configurable": {"thread_id": tid}})
    assert loaded is not None, "shard saver aput/aget_tuple round-trip failed"
    assert loaded.checkpoint["channel_values"]["messages"] == ["hello fresh"]
    assert loaded.metadata["source"] == "input"

    row_count = await fresh_db_session.execute(
        text("SELECT COUNT(*) FROM checkpoints WHERE thread_id = :tid"),
        {"tid": tid},
    )
    assert row_count.scalar() == 1

    # Step 5 — close_all_pools traverses saver.conn, not .pool or ._pool.
    # The function must close the underlying pool and clear the registry.
    await close_all_pools()
    assert inner_pool.closed is True
    assert len(pool_module._pools) == 0

    # Repeat close must be idempotent (empty registry → no-op).
    await close_all_pools()
    assert inner_pool.closed is True

    # Shared singleton was never initialised — close_checkpointer is no-op.
    await close_checkpointer()

    # Cleanup tables.
    await _teardown_tables(fresh_db_session)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(f"Run via pytest with {_FRESH_DB_ENV} set to a test-owned URL.")
