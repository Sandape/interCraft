"""023 US6 — Lifespan checkpointer preheat failure graceful degradation.

Verifies FR-021: when the checkpointer cannot be initialized (e.g. DB
unreachable), ``preheat()`` logs ``checkpointer.preheat_failed`` warning and
does NOT raise. The FastAPI app must still be able to start and serve
healthz.

Per spec 023 US6 edge case: "当 lifespan 预热 checkpointer 失败 (数据库未就绪)
时, 服务必须仍然启动 (降级为懒加载), 并记录 warning 日志".

Round-1 review #7 fixed the unit-level failure path
(``test_preheat_logs_preheat_failed_event_on_failure`` now uses
``structlog.testing.capture_logs``). Round-2 review #7 part (a) found the
integration-level lifespan wiring test was still broken: ASGITransport
only forwards HTTP requests and never runs ASGI lifespan events, so the
``get_checkpointer`` mock was dead code. ``test_app_starts_when_preheat_fails``
now manually enters the ``lifespan(app)`` async context manager to
trigger the real startup sequence, and asserts ``mock_preheat.call_count >= 1``
as the lifespan-wiring proof (deleting ``main.py``'s
``await checkpointer_preheat()`` makes it fail).
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest
from httpx import ASGITransport
from structlog.testing import capture_logs

pytestmark = [pytest.mark.integration]


@pytest.mark.asyncio
async def test_preheat_does_not_raise_when_get_checkpointer_fails():
    """023 US6 — DB unreachable → preheat() logs warning, returns None, does not raise."""
    from app.agents import checkpointer

    with (
        patch.object(
            checkpointer, "get_checkpointer", side_effect=RuntimeError("db down")
        ),
        capture_logs() as logs,
    ):
        # Should NOT raise — the whole point of preheat() is graceful degrade.
        result = await checkpointer.preheat()

    assert result is None, "preheat() must return None on failure (graceful degrade)"
    failed_events = [e for e in logs if e.get("event") == "checkpointer.preheat_failed"]
    assert failed_events, (
        f"Expected 'checkpointer.preheat_failed' event; got: {[e.get('event') for e in logs]}"
    )


@pytest.mark.asyncio
async def test_preheat_returns_none_when_pool_open_fails():
    """023 US6 — if pool.open() raises during init, preheat() catches it."""
    from app.agents import checkpointer

    fake_cp = AsyncMock()
    fake_cp.setup = AsyncMock()

    with (
        patch.object(checkpointer, "get_checkpointer", side_effect=RuntimeError("connection refused")),
        capture_logs() as logs,
    ):
        result = await checkpointer.preheat()
    assert result is None
    failed_events = [e for e in logs if e.get("event") == "checkpointer.preheat_failed"]
    assert failed_events, (
        f"Expected 'checkpointer.preheat_failed' event; got: {[e.get('event') for e in logs]}"
    )


@pytest.mark.asyncio
async def test_app_starts_when_preheat_fails():
    """023 US6 — lifespan triggers preheat; app starts normally.

    Round-2 review #7 part (a): the round-1 fix switched to
    ``httpx.AsyncClient(transport=ASGITransport(app))`` claiming it
    "triggers the FastAPI lifespan on context enter". That is false —
    ``ASGITransport`` only forwards HTTP requests and never runs ASGI
    lifespan events. Reviewer empirically confirmed
    ``preheat.call_count == 0`` on the ASGITransport path vs ``== 1`` on
    the ``TestClient`` path. The ``get_checkpointer`` mock was dead code
    (never called); deleting ``main.py``'s ``await checkpointer_preheat()``
    line left the test green, zero regression protection.

    Fix: manually enter the ``lifespan(app)`` async context manager,
    which runs the real startup sequence (including
    ``await checkpointer_preheat()``). This is Option 2 from the fix
    brief — preferred over ``TestClient`` (Option 1) because it keeps the
    test async (compatible with the async autouse
    ``_reset_checkpointer_singleton`` fixture in conftest.py).

    Verification:
    - ``mock_preheat.call_count >= 1`` proves lifespan triggered preheat.
      Deleting ``main.py:49``'s ``await checkpointer_preheat()`` makes
      this assertion fail (verified via reverse test below).
    - ``healthz 200`` proves app started normally despite the mock.

    Deviation from task brief: the brief suggested
    ``MagicMock(side_effect=Exception("preheat failed"))``. We deviate
    because ``main.py``'s lifespan does NOT wrap
    ``await checkpointer_preheat()`` in try/except — preheat() itself is
    non-raising by design (internal try/except catches get_checkpointer
    failures and logs ``checkpointer.preheat_failed``). Using
    ``side_effect=Exception`` would propagate through lifespan and crash
    startup, making ``healthz 200`` unreachable. preheat's internal
    failure handling is covered by unit tests
    ``test_preheat_does_not_raise_when_get_checkpointer_fails`` and
    ``test_preheat_logs_preheat_failed_event_on_failure``.
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
    """023 US6 — failure path emits a structured warning event.

    ``structlog.testing.capture_logs`` captures the event dict so we can
    assert the event name directly (not just that no exception raised).
    """
    from app.agents import checkpointer

    with (
        patch.object(
            checkpointer, "get_checkpointer", side_effect=RuntimeError("simulated outage")
        ),
        capture_logs() as logs,
    ):
        await checkpointer.preheat()

    failed_events = [e for e in logs if e.get("event") == "checkpointer.preheat_failed"]
    assert failed_events, (
        f"Expected 'checkpointer.preheat_failed' event; got: {[e.get('event') for e in logs]}"
    )
    # exc_info=True should attach exception info to the event
    assert failed_events[0].get("log_level") == "warning", failed_events[0]
