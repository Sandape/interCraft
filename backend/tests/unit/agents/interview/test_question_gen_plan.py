"""question_gen plan consumption tests (REQ-058 T014)."""
from __future__ import annotations

import pytest

from app.agents.interview.nodes.question_gen import question_gen_node
from app.agents.interview.plan_questions import select_next_question_spec


SAMPLE_PLAN = {
    "focus_areas": [
        {"area": "分布式", "weight": 0.5, "reason": "核心"},
        {"area": "数据库", "weight": 0.5, "reason": "存储"},
    ],
    "suggested_questions": [
        "请描述一次高并发改造",
        "如何做分库分表？",
    ],
    "interview_difficulty": "medium",
    "tips": ["追问落地"],
    "tech_stack": ["Java"],
}


@pytest.mark.asyncio
async def test_question_gen_uses_suggested_first() -> None:
    state = {
        "current_question": 0,
        "questions": [],
        "mode": "full",
        "max_questions": 10,
        "interview_plan": SAMPLE_PLAN,
        "plan_status": "ready",
        "degraded": False,
        "position": "后端",
        "company": "美团",
        "difficulty": "medium",
        "user_id": "u",
        "thread_id": "t",
        "messages": [],
    }
    out = await question_gen_node(state)
    assert out["questions"][-1]["source"] == "suggested"
    assert out["questions"][-1]["question"] == "请描述一次高并发改造"
    assert "tech_depth" not in out["questions"][-1]["question"]


def test_no_template_when_ready_via_selector() -> None:
    spec = select_next_question_spec(
        interview_plan=SAMPLE_PLAN,
        plan_status="ready",
        degraded=False,
        questions=[],
        max_questions=10,
    )
    assert spec.source == "suggested"
    assert spec.question and "请分享你在" not in spec.question
@pytest.mark.asyncio
async def test_degraded_question_gen_uses_template_without_llm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_if_called() -> object:
        raise AssertionError("degraded template path must not call the LLM client")

    monkeypatch.setattr(
        "app.agents.interview.nodes.question_gen.get_llm_client",
        fail_if_called,
    )
    state = {
        "current_question": 0,
        "questions": [],
        "mode": "full",
        "max_questions": 10,
        "plan_status": "degraded",
        "degraded": True,
        "position": "AI application engineer",
        "company": "ByteDance",
        "difficulty": "medium",
        "user_id": "u",
        "thread_id": "t",
        "messages": [],
    }

    out = await question_gen_node(state)

    assert out["questions"][-1]["source"] == "template_degraded"
    assert out["questions"][-1]["question"]
