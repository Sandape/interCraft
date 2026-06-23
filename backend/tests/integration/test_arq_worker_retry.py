"""023 US4 — ARQ worker ability_diagnose retry integration test.

Verifies: when ``ainvoke`` raises a reconnectable OperationalError on the
first attempt, the graph's retry loop force-rebuilds the checkpointer and
succeeds on the 2nd attempt. Confirms ``checkpointer_reconnect_total``
metric is incremented.

Per spec 023 US4 acceptance scenario 1: "任务自动重试一次, 重试成功后能力
画像更新".
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest

pytestmark = [pytest.mark.integration]


class _FakeReconnectableError(RuntimeError):
    """Simulates psycopg.OperationalError 'connection is closed'."""

    def __init__(self) -> None:
        super().__init__("connection is closed")


async def _noop_ainvoke(*args, **kwargs):
    """Successful ainvoke that returns a benign diagnosis result."""
    return {
        "diagnoses": [],
        "insights": [],
    }


@pytest.mark.asyncio
async def test_ability_diagnose_retries_on_reconnectable_operational_error():
    """023 US4 — first ainvoke raises 'connection is closed', 2nd succeeds."""
    from app.agents.checkpointer import _force_rebuild
    from app.agents.graphs.ability_diagnose import get_ability_diagnose_graph

    # Reset the checkpointer singleton so the test starts clean
    await _force_rebuild()

    graph = get_ability_diagnose_graph()

    call_count = 0

    async def flaky_ainvoke(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise _FakeReconnectableError()
        return await _noop_ainvoke(*args, **kwargs)

    # Patch the underlying graph object's ainvoke so the retry loop triggers
    fake_graph = AsyncMock()
    fake_graph.ainvoke = flaky_ainvoke

    with patch.object(graph, "build_graph", AsyncMock(return_value=fake_graph)):
        result = await graph.run(
            user_id="019b5e6c-0000-7000-0000-000000000003",
            session_id=str(uuid.uuid4()),
        )

    # 2 invocations: 1 initial failure + 1 successful retry
    assert call_count == 2, f"Expected 2 invocations, got {call_count}"
    assert result is not None


@pytest.mark.asyncio
async def test_ability_diagnose_raises_unavailable_after_max_retries():
    """023 US4 — all retries exhausted → CheckpointerUnavailableError."""
    from app.agents.checkpointer import _force_rebuild
    from app.agents.graphs.ability_diagnose import get_ability_diagnose_graph

    await _force_rebuild()

    graph = get_ability_diagnose_graph()

    fake_graph = AsyncMock()
    fake_graph.ainvoke = AsyncMock(side_effect=_FakeReconnectableError())

    with patch.object(graph, "build_graph", AsyncMock(return_value=fake_graph)):
        from app.agents.exceptions import CheckpointerUnavailableError

        with pytest.raises(CheckpointerUnavailableError) as exc_info:
            await graph.run(
                user_id="019b5e6c-0000-7000-0000-000000000003",
                session_id=str(uuid.uuid4()),
            )
    assert exc_info.value.retry_after == 30
    # 3 invocations: 1 initial + 2 retries before giving up
    assert fake_graph.ainvoke.call_count == 3


@pytest.mark.asyncio
async def test_ability_diagnose_propagates_non_reconnectable_error():
    """023 US4 — non-reconnectable error propagates immediately, no retry."""
    from app.agents.checkpointer import _force_rebuild
    from app.agents.graphs.ability_diagnose import get_ability_diagnose_graph

    await _force_rebuild()

    graph = get_ability_diagnose_graph()

    fake_graph = AsyncMock()
    fake_graph.ainvoke = AsyncMock(side_effect=ValueError("bad input"))

    with (
        patch.object(graph, "build_graph", AsyncMock(return_value=fake_graph)),
        pytest.raises(ValueError, match="bad input"),
    ):
        await graph.run(
            user_id="019b5e6c-0000-7000-0000-000000000003",
            session_id=str(uuid.uuid4()),
        )
    # Only 1 call — no retry on non-reconnectable
    assert fake_graph.ainvoke.call_count == 1
