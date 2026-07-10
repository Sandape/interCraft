"""Plan failure policy (REQ-058 T037)."""
from __future__ import annotations

from app.agents.interview.plan_questions import select_next_question_spec
from app.agents.interview.nodes.planner_generate import _empty_plan


def test_failed_blocks_question_gen_selector() -> None:
    spec = select_next_question_spec(
        interview_plan=None,
        plan_status="failed",
        degraded=False,
        questions=[],
        max_questions=10,
    )
    assert spec.source == "blocked"


def test_empty_plan_helper_has_no_content() -> None:
    plan = _empty_plan({"company": "x", "position": "y"})
    assert plan["focus_areas"] == []
    assert plan["suggested_questions"] == []
