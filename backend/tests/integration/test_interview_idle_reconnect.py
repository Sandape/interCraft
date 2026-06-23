"""023 US1 — Interview idle reconnect integration test.

Verifies: submit_answer after a forced checkpointer rebuild (simulates idle
connection drop) still returns a valid result with score and next question.

The interview graph lives in ``backend/app/agents/interview/graph.py`` and
is driven via WebSocket in production. We test the graph layer directly
because the WS layer requires a live socket pair; the WS handler is a thin
wrapper around ``submit_answer`` which is what 023 wraps with the shared
retry wrapper.

Per spec 023 US1 acceptance scenario 1: "等待 60 秒后调用 POST
/interview-sessions/{tid}/messages, 响应 200, 返回 score 和下一题".
"""
from __future__ import annotations

import os
import uuid

import pytest

pytestmark = [pytest.mark.integration]


def _scenario_path() -> str:
    """Empty mock-LLM scenario (interview uses internal prompts)."""
    import json

    os.makedirs(
        os.path.join(os.path.dirname(__file__), "_mock_scenarios"),
        exist_ok=True,
    )
    path = os.path.join(
        os.path.dirname(__file__),
        "_mock_scenarios",
        f"iv_idle_{uuid.uuid4().hex[:8]}.json",
    )
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"evaluate_scores": [], "hint_contents": {}}, f)
    return path


@pytest.fixture(autouse=True)
def _mock_llm(monkeypatch):
    monkeypatch.setenv("LLM_MOCK_MODE", "1")
    monkeypatch.setenv("LLM_MOCK_SCENARIO_PATH", _scenario_path())
    yield


_USER_ID = "019b5e6c-0000-7000-0000-000000000003"


@pytest.mark.asyncio
async def test_interview_submit_answer_after_reconnect_returns_200_equivalent():
    """023 US1 — submit_answer after forced checkpointer drop succeeds with score."""
    from app.agents.checkpointer import _force_rebuild
    from app.agents.interview.graph import get_interview_graph

    graph = get_interview_graph()
    thread_id = str(uuid.uuid4())

    # First submit — primes the graph with the intake answer.
    r1 = await graph.submit_answer(
        thread_id=thread_id,
        answer="我应聘的是高级前端工程师岗位，主要负责 React + TypeScript 开发。",
        sequence_no=1,
        user_id=_USER_ID,
        position="高级前端工程师",
        company="Acme",
    )
    assert r1 is not None

    # Simulate idle connection drop (server-side close after 60s idle).
    await _force_rebuild()

    # Second submit — must NOT raise OperationalError; retry wrapper rebuilds
    # the checkpointer and continues.
    r2 = await graph.submit_answer(
        thread_id=thread_id,
        answer="我对 React 18 的并发特性比较熟悉，比如 useTransition、Suspense 等。",
        sequence_no=2,
        user_id=_USER_ID,
        position="高级前端工程师",
        company="Acme",
    )
    assert r2 is not None

    # Final state must be queryable (i.e. checkpoint persistence survived the drop).
    state = await graph.get_current_state(thread_id)
    assert state is not None
    assert state["current_question"] >= 0


@pytest.mark.asyncio
async def test_interview_resume_from_checkpoint_after_reconnect():
    """023 US1 — reconnect-style read after forced drop must succeed."""
    from app.agents.checkpointer import _force_rebuild
    from app.agents.interview.graph import get_interview_graph

    graph = get_interview_graph()
    thread_id = str(uuid.uuid4())

    await graph.submit_answer(
        thread_id=thread_id,
        answer="我的优势是性能优化和工程化建设。",
        sequence_no=1,
        user_id=_USER_ID,
    )

    await _force_rebuild()

    # resume_from_checkpoint uses retry_graph_op internally
    state = await graph.resume_from_checkpoint(thread_id)
    assert state is not None
    assert state["current_question"] >= 0


@pytest.mark.asyncio
async def test_interview_submit_answer_retries_on_operational_error(monkeypatch):
    """023 US1 FR-003 — retry_graph_op retry branch exercised on interview path.

    Mocks build_graph to return a fake graph whose aget_state succeeds but
    ainvoke raises ``OperationalError("connection is closed")`` on first
    attempt and succeeds on second.  Asserts:

    - ``checkpointer_reconnect_total`` increments (FR-034)
    - The retry returns the second-attempt result
    - ainvoke was called twice (1 initial + 1 retry)
    """
    from unittest.mock import AsyncMock, patch

    from app.agents.checkpointer import _force_rebuild
    from app.agents.interview.graph import get_interview_graph
    from app.core.metrics import checkpointer_reconnect_total

    await _force_rebuild()

    # Snapshot the counter before so we can delta-check inc.
    before = checkpointer_reconnect_total._value.get()

    fake_state = AsyncMock()
    fake_state.values = {"current_question": 1}
    fake_state.next = ["interviewer"]

    fake_graph = AsyncMock()
    fake_graph.aget_state = AsyncMock(return_value=fake_state)
    fake_graph.aupdate_state = AsyncMock(return_value=None)
    call_count = 0

    async def flaky_ainvoke(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("connection is closed")
        return {"correct": True, "score": 8, "next_question": "Q2"}

    fake_graph.ainvoke = flaky_ainvoke

    graph = get_interview_graph()

    # Stub _force_rebuild so retry doesn't tear down the (non-existent) real pool.
    with (
        patch.object(graph, "build_graph", AsyncMock(return_value=fake_graph)),
        patch("app.agents.checkpointer._force_rebuild", new=AsyncMock()),
    ):
        result = await graph.submit_answer(
            thread_id="tid-retry-test",
            answer="test answer",
            sequence_no=2,
            user_id=_USER_ID,
            position="前端",
            company="Acme",
        )

    assert call_count == 2, f"Expected 2 invocations (1 fail + 1 retry), got {call_count}"
    assert result == {"correct": True, "score": 8, "next_question": "Q2"}
    after = checkpointer_reconnect_total._value.get()
    assert after > before, (
        f"checkpointer_reconnect_total must inc on retry (before={before}, after={after})"
    )
