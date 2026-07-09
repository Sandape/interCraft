"""REQ-051 — agent capture hook tests (simplified).

Tests that the BaseAgent infrastructure still functions after auth refactor.
"""
from __future__ import annotations

import pytest

from app.agents.base import BaseAgent


class FakeGraph:
    async def ainvoke(self, state, config=None):
        return {"ok": True, "thread_id": state["thread_id"]}


class FakeAgent(BaseAgent):
    def build_graph(self):
        return FakeGraph()


@pytest.mark.asyncio
async def test_base_agent_ainvoke_works() -> None:
    """BaseAgent.ainvoke still works after REQ-051 refactor."""
    result = await FakeAgent().ainvoke({"thread_id": "thread_1", "user_id": "user_1"})

    assert result == {"ok": True, "thread_id": "thread_1"}
