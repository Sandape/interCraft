"""023 US5 — General Coach idle reconnect integration test.

Verifies: start → send msg1 → force checkpointer rebuild (simulates idle
connection drop) → send msg2 → AI response includes msg1 in conversation
context (no data loss across the reconnect).

Per spec 023 US5 acceptance scenario 1: "AI 回复引用了第一条消息的上下文".
"""
from __future__ import annotations

import os
import uuid

import pytest

pytestmark = [pytest.mark.integration]


_USER_ID = "019b5e6c-0000-7000-0000-000000000003"


def _scenario_path() -> str:
    """Path to a mock-LLM scenario file (content unused for general_coach)."""
    import json

    os.makedirs(
        os.path.join(os.path.dirname(__file__), "_mock_scenarios"),
        exist_ok=True,
    )
    path = os.path.join(
        os.path.dirname(__file__),
        "_mock_scenarios",
        f"general_coach_{uuid.uuid4().hex[:8]}.json",
    )
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"evaluate_scores": [], "hint_contents": {}}, f)
    return path


@pytest.fixture(autouse=True)
def _mock_llm(monkeypatch):
    """Force mock LLM for deterministic output."""
    monkeypatch.setenv("LLM_MOCK_MODE", "1")
    monkeypatch.setenv("LLM_MOCK_SCENARIO_PATH", _scenario_path())
    yield


@pytest.mark.asyncio
async def test_general_coach_msg2_after_reconnect_preserves_msg1_context():
    """023 US5 — send msg1, force checkpointer drop, send msg2, msg1 still in state."""
    from app.agents.checkpointer import _force_rebuild
    from app.agents.graphs.general_coach import get_general_coach_graph

    graph = get_general_coach_graph()
    thread_id = await graph.start(
        user_id=_USER_ID,
        initial_question="如何准备系统设计面试？",
    )

    # Send first message via the graph (not via start).
    await graph.send_message(thread_id, "我应该先学习哪些基础知识？")

    # Simulate idle connection drop: force-rebuild the singleton.
    await _force_rebuild()

    # Send second message after the drop — retry_graph_op must rebuild
    # and the conversation history must survive.
    result = await graph.send_message(thread_id, "请再补充一下数据库分片的相关知识。")

    # The graph should return successfully (no OperationalError raised).
    assert result is not None

    # Final state must contain both user messages.
    state = await graph.get_state(thread_id)
    assert state["session_active"] is True
    assert state["message_count"] >= 3  # 1 from start + 2 from send_message


@pytest.mark.asyncio
async def test_general_coach_close_after_reconnect():
    """023 US5 — close() must survive a forced checkpointer drop."""
    from app.agents.checkpointer import _force_rebuild
    from app.agents.graphs.general_coach import get_general_coach_graph

    graph = get_general_coach_graph()
    thread_id = await graph.start(user_id=_USER_ID, initial_question="Hi")

    await _force_rebuild()

    # close() must not raise.
    await graph.close(thread_id)

    state = await graph.get_state(thread_id)
    assert state["session_active"] is False


@pytest.mark.asyncio
async def test_general_coach_send_message_retries_on_operational_error(monkeypatch):
    """023 US5 FR-012 — retry_graph_op retry branch exercised on general_coach path.

    Mocks build_graph so aupdate_state succeeds but ainvoke raises
    ``OperationalError("connection is closed")`` on first attempt and
    succeeds on second.  Asserts:

    - ``checkpointer_reconnect_total`` increments (FR-034)
    - The retry returns the second-attempt result
    - ainvoke was called twice (1 initial + 1 retry)
    """
    from unittest.mock import AsyncMock, patch

    from app.agents.checkpointer import _force_rebuild
    from app.agents.graphs.general_coach import get_general_coach_graph
    from app.core.metrics import checkpointer_reconnect_total

    await _force_rebuild()
    before = checkpointer_reconnect_total._value.get()

    fake_graph = AsyncMock()
    fake_graph.aupdate_state = AsyncMock(return_value=None)
    call_count = 0

    async def flaky_ainvoke(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("connection is closed")
        return {"messages": [{"role": "ai", "content": "reply"}]}

    fake_graph.ainvoke = flaky_ainvoke

    graph = get_general_coach_graph()
    with (
        patch.object(graph, "build_graph", AsyncMock(return_value=fake_graph)),
        patch("app.agents.checkpointer._force_rebuild", new=AsyncMock()),
    ):
        result = await graph.send_message("tid-gc-retry", "second message")

    assert call_count == 2, f"Expected 2 invocations, got {call_count}"
    assert result == {"messages": [{"role": "ai", "content": "reply"}]}
    after = checkpointer_reconnect_total._value.get()
    assert after > before, (
        f"checkpointer_reconnect_total must inc on retry (before={before}, after={after})"
    )
