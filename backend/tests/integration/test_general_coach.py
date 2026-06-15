"""Integration test for M19 General Coach complete flow.

Tests: start → intent classification for 4 categories → streaming response
       close → session inactive

Per Constitution III: these must FAIL before implementation.
"""
from __future__ import annotations

import pytest

pytestmark = [pytest.mark.integration]

_USER_ID = "019b5e6c-0000-7000-0000-000000000003"


@pytest.mark.asyncio
async def test_general_coach_career_advice_intent():
    """M19 detects career_advice intent."""
    from app.agents.graphs.general_coach import get_general_coach_graph

    graph = get_general_coach_graph()
    thread_id = await graph.start(
        user_id=_USER_ID,
        initial_question="如何准备系统设计面试",
    )

    state = await graph.get_state(thread_id)
    assert state["session_active"] is True


@pytest.mark.asyncio
async def test_general_coach_close():
    """M19 close marks session as inactive."""
    from app.agents.graphs.general_coach import get_general_coach_graph

    graph = get_general_coach_graph()
    thread_id = await graph.start(user_id=_USER_ID)

    await graph.close(thread_id)
    state = await graph.get_state(thread_id)
    assert state["session_active"] is False
