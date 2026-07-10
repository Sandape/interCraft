"""Intake skip when targets seeded (REQ-058 T022)."""
from __future__ import annotations

import pytest

from app.agents.interview.nodes.intake import intake_node


@pytest.mark.asyncio
async def test_intake_skips_llm_when_seeded(monkeypatch: pytest.MonkeyPatch) -> None:
    called = {"n": 0}

    class Boom:
        async def invoke(self, *args, **kwargs):
            called["n"] += 1
            raise AssertionError("LLM should not be called")

    monkeypatch.setattr(
        "app.agents.interview.nodes.intake.get_llm_client",
        lambda: Boom(),
    )

    out = await intake_node(
        {
            "position": "后端工程师",
            "company": "美团",
            "job_id": None,
            "messages": [{"role": "user", "content": "自我介绍"}],
            "user_id": "u",
            "thread_id": "t",
        }
    )
    assert called["n"] == 0
    assert out["position"] == "后端工程师"
    assert out["company"] == "美团"
