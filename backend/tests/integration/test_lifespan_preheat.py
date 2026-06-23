"""023 US6 — Lifespan checkpointer preheat success path.

Verifies FR-022 / FR-023 / FR-024 / FR-025:

- ``preheat()`` emits a ``checkpointer.preheat ok`` structlog event
  (asserted via ``structlog.testing.capture_logs`` — the previous test
  only checked that ``checkpoints`` table existed, which ``setup()``
  creates regardless of whether preheat itself succeeded).
- The pool is built with the explicit ``_POOL_CONFIG`` (FR-023/024/025)
  and ``pool.get_stats()`` reflects the configured ``min_size`` / ``max_size``.
- ``checkpoints`` table exists in ``pg_tables`` after preheat.

Per spec 023 US6 acceptance scenarios 2 & 3:
  - "可见 checkpointer.preheat ok 日志, 证明 checkpointer 在 lifespan 阶段已初始化"
  - "查询 pg_tables WHERE tablename LIKE 'checkpoint%', checkpointer 表已存在"
"""
from __future__ import annotations

import pytest
from sqlalchemy import text
from structlog.testing import capture_logs

pytestmark = [pytest.mark.integration]


@pytest.mark.asyncio
async def test_preheat_logs_ok_and_creates_checkpoint_tables(db_session):
    """023 US6 — preheat() succeeds, emits ``checkpointer.preheat ok``, creates tables.

    The previous version of this test only asserted ``checkpoints`` table
    existence, which is created by ``setup()`` even if the ``preheat``
    function itself crashed at the ``cp.list()`` probe (TypeError on
    sync generator).  We now assert the structured log event directly so a
    runtime crash in ``preheat`` cannot masquerade as a success.
    """
    from app.agents.checkpointer import _force_rebuild, preheat

    # Reset singleton so preheat() runs the full init path this test asserts.
    await _force_rebuild()

    with capture_logs() as logs:
        await preheat()

    ok_events = [e for e in logs if e.get("event") == "checkpointer.preheat ok"]
    assert ok_events, (
        f"Expected 'checkpointer.preheat ok' event in logs; got events: "
        f"{[e.get('event') for e in logs]}"
    )
    # FR-022: log must include pool_config
    assert "pool_config" in ok_events[0], ok_events[0]
    assert ok_events[0]["pool_config"]["min_size"] == 1
    assert ok_events[0]["pool_config"]["max_size"] == 10

    # Verify checkpoint_* tables exist in pg_tables
    result = await db_session.execute(
        text(
            "SELECT tablename FROM pg_tables "
            "WHERE tablename LIKE 'checkpoint%' ORDER BY tablename"
        )
    )
    tables = [row[0] for row in result.fetchall()]
    assert "checkpoints" in tables, f"Expected 'checkpoints' table, got {tables}"


@pytest.mark.asyncio
async def test_preheat_returns_none_on_success():
    """023 US6 — preheat() never raises on success."""
    from app.agents.checkpointer import preheat

    result = await preheat()
    assert result is None


@pytest.mark.asyncio
async def test_preheat_idempotent_when_called_multiple_times():
    """023 US6 — preheat() can be called repeatedly without error (FR: setup() idempotent)."""
    from app.agents.checkpointer import preheat

    # Multiple invocations must not raise (setup() is idempotent per LangGraph)
    await preheat()
    await preheat()
    await preheat()


@pytest.mark.asyncio
async def test_pool_config_reflects_in_pool_stats():
    """023 FR-023 / FR-024 / FR-025 — pool is built with explicit config.

    The previous test only checked ``_POOL_CONFIG`` module attribute exists,
    which is misleading: the dict can exist while ``from_conn_string`` ignores
    it entirely.  We now inspect the live pool's stats to confirm min_size /
    max_size actually propagated.
    """
    from app.agents.checkpointer import _POOL_CONFIG, _force_rebuild, get_checkpointer

    # Reset singleton so get_checkpointer builds a fresh pool with current config.
    await _force_rebuild()
    await get_checkpointer()

    # Import module state after init.
    from app.agents import checkpointer as cp_module

    pool = cp_module._pool
    assert pool is not None, "Pool singleton must be initialised after get_checkpointer()"

    stats = pool.get_stats()
    assert stats["pool_min"] == _POOL_CONFIG["min_size"], stats
    assert stats["pool_max"] == _POOL_CONFIG["max_size"], stats

    # FR-024 / FR-025 — config dict carries keepalive + check callback markers.
    assert _POOL_CONFIG["keepalives"] == 1
    assert _POOL_CONFIG["keepalives_idle"] == 30
    assert _POOL_CONFIG["keepalives_interval"] == 10
    assert _POOL_CONFIG["keepalives_count"] == 5
    # check callback is wired (FR-025) — pool._check is the function reference
    assert pool._check is not None, "FR-025 check_connection callback must be wired"


@pytest.mark.asyncio
async def test_pool_config_present_in_module():
    """023 FR-023 — pool config dict is exposed for diagnostic logging."""
    from app.agents import checkpointer

    cfg = checkpointer._POOL_CONFIG
    assert cfg["min_size"] == 1
    assert cfg["max_size"] == 10
    assert cfg["max_idle"] == 300.0
    assert cfg["reconnect_timeout"] == 300.0
    assert cfg["timeout"] == 30.0
    # Keepalive params (FR-024)
    assert cfg["keepalives"] == 1
    assert cfg["keepalives_idle"] == 30
    assert cfg["keepalives_interval"] == 10
    assert cfg["keepalives_count"] == 5
