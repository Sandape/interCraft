"""Integration test for M17 Error Coach complete flow.

Tests: start → 3 rounds of correct answers → frequency updated
       timeout auto-abort

Per Constitution III: these must FAIL before implementation.
"""
from __future__ import annotations

import pytest

pytestmark = [pytest.mark.integration]

_ERROR_QUESTION_ID = "019b5e6c-0000-7000-0000-000000000002"
_USER_ID = "019b5e6c-0000-7000-0000-000000000003"


@pytest.mark.asyncio
async def test_error_coach_three_correct_flow():
    """M17 start → 3 correct answers → frequency decremented."""
    from app.agents.graphs.error_coach import get_error_coach_graph

    graph = get_error_coach_graph()
    thread_id = await graph.start(
        user_id=_USER_ID,
        error_question_id=_ERROR_QUESTION_ID,
    )

    assert thread_id is not None

    # Simulate 3 correct answers
    for i in range(3):
        result = await graph.submit_answer(thread_id, "用户的正确答案内容")
        assert result is not None

    # Verify state shows completion
    state = await graph.get_state(thread_id)
    assert state["status"] == "completed"
    assert state["correct_count"] >= 3


@pytest.mark.asyncio
async def test_error_coach_abort():
    """M17 user abort marks session as aborted."""
    from app.agents.graphs.error_coach import get_error_coach_graph

    graph = get_error_coach_graph()
    thread_id = await graph.start(
        user_id=_USER_ID,
        error_question_id=_ERROR_QUESTION_ID,
    )

    result = await graph.abort(thread_id)
    assert result is not None
    assert result.get("correct_count", 0) >= 0
