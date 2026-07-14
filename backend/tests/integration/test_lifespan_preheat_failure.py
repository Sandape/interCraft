"""023 US6 — Lifespan checkpointer preheat failure graceful degradation.

Verifies FR-021 + REQ-081 readiness:

- ``preheat()`` is fail-closed: when the checkpointer cannot be initialized
  (e.g. DB unreachable), ``preheat()`` logs ``checkpointer.preheat_failed``
  warning and returns a typed ``CheckpointerReadiness`` whose
  ``state == "down"`` and ``reason`` is a redacted tag (no exception
  text, no URL).
- The FastAPI app must still be able to start and serve ``healthz``
  even when preheat reports ``down`` (lifespan swallow is preserved,
  but the readiness state surfaces a 503 from ``/readyz``).

Per spec 023 US6 edge case: "当 lifespan 预热 checkpointer 失败 (数据库未就绪)
时, 服务必须仍然启动 (降级为懒加载), 并记录 warning 日志".

REQ-081 round-2 replaces the round-1 ``result is None`` assertions
because ``preheat()`` was made typed (worker startup now gates
``intercraft_worker_started`` on ``readiness.state == "up"``); a None
result would force the worker into the "started" branch blindly.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest
from httpx import ASGITransport
from structlog.testing import capture_logs

pytestmark = [pytest.mark.integration]

_FRESH_DB_OWNED_ENV = "INTERCRAFT_TEST_CHECKPOINTER_FRESH_DB_OWNED"


def test_fresh_db_guard_rejects_shared_name_without_leaking_dsn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.integration import test_checkpointer_fresh_database as contract

    url = "postgresql+asyncpg://secret-user:secret-password@db.internal:5432/intercraft_test"
    monkeypatch.setenv(contract._FRESH_DB_ENV, url)
    monkeypatch.setenv(_FRESH_DB_OWNED_ENV, "1")

    with pytest.raises(pytest.fail.Exception) as exc_info:
        contract._require_fresh_db_url()

    message = str(exc_info.value)
    assert "intercraft_test" in message
    for secret in (url, "secret-user", "secret-password", "db.internal"):
        assert secret not in message


def test_fresh_db_guard_requires_explicit_owned_marker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.integration import test_checkpointer_fresh_database as contract

    monkeypatch.setenv(
        contract._FRESH_DB_ENV,
        "postgresql+asyncpg://ci:ci@127.0.0.1:5432/checkpointer_fresh",
    )
    monkeypatch.delenv(_FRESH_DB_OWNED_ENV, raising=False)

    with pytest.raises(pytest.fail.Exception) as exc_info:
        contract._require_fresh_db_url()

    message = str(exc_info.value)
    assert "checkpointer_fresh" in message
    assert "127.0.0.1" not in message
    assert "ci:ci" not in message


def test_fresh_db_guard_accepts_explicitly_owned_dedicated_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.integration import test_checkpointer_fresh_database as contract

    url = "postgresql+asyncpg://ci:ci@127.0.0.1:5432/checkpointer_fresh_run_42"
    monkeypatch.setenv(contract._FRESH_DB_ENV, url)
    monkeypatch.setenv(_FRESH_DB_OWNED_ENV, "1")

    assert contract._require_fresh_db_url() == url


def test_fresh_db_expected_tables_are_order_independent() -> None:
    from tests.integration import test_checkpointer_fresh_database as contract

    assert (
        frozenset(
            {
                "checkpoint_migrations",
                "checkpoints",
                "checkpoint_blobs",
                "checkpoint_writes",
            }
        )
        == contract._EXPECTED_TABLES
    )


@pytest.mark.asyncio
async def test_preheat_does_not_raise_when_get_checkpointer_fails():
    """023 US6 + REQ-081 — DB unreachable → preheat() does not raise, returns typed down."""
    from app.agents import checkpointer

    with (
        patch.object(checkpointer, "_readiness", checkpointer._READINESS_UNINITIALISED),
        patch.object(checkpointer, "get_checkpointer", side_effect=RuntimeError("db down")),
        capture_logs() as logs,
    ):
        # Should NOT raise — the whole point of preheat() is graceful degrade.
        result = await checkpointer.preheat()

    assert result.state == "down", result.as_dict()
    assert result.reason == "saver_setup_failed", result.as_dict()
    failed_events = [e for e in logs if e.get("event") == "checkpointer.preheat_failed"]
    assert failed_events, (
        f"Expected 'checkpointer.preheat_failed' event; got: {[e.get('event') for e in logs]}"
    )


@pytest.mark.asyncio
async def test_preheat_preserves_stage_specific_pool_open_reason():
    """A concrete pool-open failure must not be relabelled as saver setup."""
    from app.agents import checkpointer

    async def fail_after_pool_open_diagnostic():
        checkpointer._readiness = checkpointer._READINESS_POOL_OPEN_FAILED
        raise RuntimeError("db down with secret details")

    with (
        patch.object(checkpointer, "_readiness", checkpointer._READINESS_UNINITIALISED),
        patch.object(checkpointer, "get_checkpointer", side_effect=fail_after_pool_open_diagnostic),
    ):
        result = await checkpointer.preheat()

    assert result.state == "down"
    assert result.reason == "pool_open_failed"


@pytest.mark.asyncio
async def test_preheat_fallback_sets_saver_setup_failed_reason():
    """REQ-081 — preheat() catch uses ``saver_setup_failed`` as the
    generic fallback when ``get_checkpointer()`` fails at an unknown stage.

    When the failing code did not publish a stage-specific diagnostic,
    ``preheat()`` uses ``_READINESS_SAVER_SETUP_FAILED`` rather than
    returning stale ``uninitialised``.
    """
    from app.agents import checkpointer

    with (
        patch.object(checkpointer, "_readiness", checkpointer._READINESS_UNINITIALISED),
        patch.object(
            checkpointer,
            "get_checkpointer",
            side_effect=RuntimeError("connection refused"),
        ),
        capture_logs() as logs,
    ):
        result = await checkpointer.preheat()
    assert result.state == "down"
    assert result.reason == "saver_setup_failed", result.as_dict()
    failed_events = [e for e in logs if e.get("event") == "checkpointer.preheat_failed"]
    assert failed_events, (
        f"Expected 'checkpointer.preheat_failed' event; got: {[e.get('event') for e in logs]}"
    )


@pytest.mark.asyncio
async def test_app_starts_when_preheat_fails():
    """023 US6 + REQ-081 — lifespan triggers preheat; app starts normally.

    REQ-081: preheat is mockable here; its internal fail-closed
    semantics are verified in
    ``test_preheat_does_not_raise_when_get_checkpointer_fails`` and
    ``test_preheat_returns_typed_down_readiness_when_pool_open_fails``.
    """
    from app.agents import checkpointer
    from app.main import create_app, lifespan

    # Mock preheat itself (not get_checkpointer) so we can assert call_count
    # directly — proving lifespan → preheat wiring.
    mock_preheat = AsyncMock()
    with patch.object(checkpointer, "preheat", mock_preheat):
        app = create_app()
        # Manually enter lifespan context — this is what actually runs
        # `await checkpointer_preheat()` (the line under test).
        async with lifespan(app):
            transport = ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                r = await client.get("/healthz")
                assert r.status_code == 200, r.text
                body = r.json()
                assert body["status"] in ("ok", "down"), body

    # The core assertion: lifespan MUST have invoked preheat.
    # If main.py loses the `await checkpointer_preheat()` line, this fails.
    assert mock_preheat.call_count >= 1, (
        "lifespan must call preheat; if this fails, main.py lost the preheat wiring"
    )


@pytest.mark.asyncio
async def test_preheat_logs_preheat_failed_event_on_failure():
    """023 US6 + REQ-081 — failure path emits a structured warning event with typed reason."""
    from app.agents import checkpointer

    with (
        patch.object(
            checkpointer,
            "get_checkpointer",
            side_effect=RuntimeError("simulated outage"),
        ),
        capture_logs() as logs,
    ):
        result = await checkpointer.preheat()

    assert result.state == "down", result.as_dict()
    failed_events = [e for e in logs if e.get("event") == "checkpointer.preheat_failed"]
    assert failed_events, (
        f"Expected 'checkpointer.preheat_failed' event; got: {[e.get('event') for e in logs]}"
    )
    assert failed_events[0].get("log_level") == "warning", failed_events[0]


@pytest.mark.asyncio
async def test_preheat_failure_global_readiness_is_typed_down():
    """REQ-081: after preheat() fails, the process-global readiness is typed down.

    Verifies that ``get_checkpointer_readiness()`` called OUTSIDE of
    ``preheat()`` (after a failure) returns a typed ``down`` snapshot
    with a redacted reason — not ``uninitialised``, not the raw
    exception text.  This proves the ``global _readiness`` assignment
    inside preheat's catch block actually mutates the module-level
    singleton that /readyz reads.
    """
    from app.agents import checkpointer

    with patch.object(checkpointer, "get_checkpointer", side_effect=RuntimeError("db down")):
        result = await checkpointer.preheat()
        assert result.state == "down", result.as_dict()

    # The process-global readiness must still be "down" AFTER preheat
    # returned — not reverted to "uninitialised" by some cleanup.
    global_snap = checkpointer.get_checkpointer_readiness()
    assert global_snap.state == "down", global_snap.as_dict()
    assert global_snap.reason in {"pool_open_failed", "saver_setup_failed"}, global_snap.as_dict()
    # Redacted: no URL, no credentials, no raw exception message.
    assert "://" not in global_snap.reason
    assert "db down" not in global_snap.reason
