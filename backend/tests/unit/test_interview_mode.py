"""REQ-048 US1 — InterviewMode Literal + Pydantic validation unit tests.

These tests verify the Pydantic schema-level validation, independent of
the database / HTTP layer.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.modules.interviews.schemas import InterviewMode, InterviewSessionCreate


def test_interview_mode_literal_accepts_valid_modes() -> None:
    for m in ("quick_drill", "full", "doubao"):
        c = InterviewSessionCreate(position="X", company="Y", mode=m)  # type: ignore[arg-type]
        assert c.mode == m


def test_interview_mode_literal_rejects_invalid_modes() -> None:
    with pytest.raises(ValidationError):
        InterviewSessionCreate(position="X", company="Y", mode="garbage")  # type: ignore[arg-type]


def test_max_questions_schema_defers_business_rule_to_service() -> None:
    # The schema accepts integers so the service can return
    # INVALID_MAX_QUESTIONS with allowed choices in details.
    InterviewSessionCreate(position="X", company="Y", mode="full", max_questions=5)
    InterviewSessionCreate(position="X", company="Y", mode="full", max_questions=10)
    InterviewSessionCreate(position="X", company="Y", mode="full", max_questions=16)


def test_default_mode_is_full() -> None:
    c = InterviewSessionCreate(position="X", company="Y")
    assert c.mode == "full"


def test_default_use_variants_is_false() -> None:
    """AC-25: use_variants defaults false on the create schema."""
    c = InterviewSessionCreate(position="X", company="Y", mode="quick_drill")
    assert c.use_variants is False


def test_use_variants_accepts_request_body_value() -> None:
    c = InterviewSessionCreate(position="X", company="Y", mode="quick_drill", use_variants=True)
    assert c.use_variants is True


def test_interview_mode_literal_exports() -> None:
    assert hasattr(InterviewMode, "__args__") or InterviewMode == "quick_drill"  # Literal sentinel


def test_doubao_plan_uses_session_position_and_company() -> None:
    """REQ-048 US4: card title/company must follow the selected session target."""
    from app.modules.interviews.service import InterviewSessionService

    plan = {
        "target_position": "人工智能工程师",
        "target_company": "未知",
        "suggested_questions": ["Q1"],
    }

    merged = InterviewSessionService._merge_session_targets_into_plan(
        plan,
        position="AI 产品经理",
        company="豆包",
    )

    assert merged["target_position"] == "AI 产品经理"
    assert merged["target_company"] == "豆包"
    assert plan["target_position"] == "人工智能工程师"


@pytest.mark.asyncio
async def test_graph_submit_answer_seeds_req048_context(monkeypatch) -> None:
    """REQ-048: persisted session mode fields must reach LangGraph state."""
    from app.agents.interview import graph as graph_mod

    class EmptyState:
        values = {}
        next = ()

    calls: list[dict] = []

    async def fake_get_graph_config(thread_id: str, checkpoint_ns: str = "") -> dict:
        return {"configurable": {"thread_id": thread_id, "checkpoint_ns": checkpoint_ns}}

    async def fake_retry_graph_op(build_graph, config, op_name, payload=None, state_first=False):
        calls.append(
            {
                "op_name": op_name,
                "payload": payload,
                "state_first": state_first,
            }
        )
        if op_name == "aget_state":
            return EmptyState()
        if op_name == "ainvoke":
            return {"ok": True}
        raise AssertionError(f"unexpected graph op: {op_name}")

    monkeypatch.setattr(graph_mod, "get_graph_config", fake_get_graph_config)
    monkeypatch.setattr(graph_mod, "retry_graph_op", fake_retry_graph_op)

    await graph_mod.InterviewGraph().submit_answer(
        thread_id="session-1",
        answer="生成豆包面试卡",
        sequence_no=0,
        user_id="user-1",
        position="AI 产品经理",
        company="字节跳动",
        mode="doubao",
        max_questions=15,
        error_question_ids=["eq-1", "eq-2"],
        use_variants=True,
    )

    initial_state = next(c["payload"] for c in calls if c["op_name"] == "ainvoke")
    assert initial_state["mode"] == "doubao"
    assert initial_state["max_questions"] == 15
    assert initial_state["error_question_ids"] == ["eq-1", "eq-2"]
    assert initial_state["use_variants"] is True
    assert initial_state["position"] == "AI 产品经理"
    assert initial_state["company"] == "字节跳动"
