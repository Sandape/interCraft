"""Contract fixture tests for question-selection (REQ-058 T015)."""
from __future__ import annotations

from app.agents.interview.plan_questions import (
    build_focus_schedule,
    select_next_question_spec,
)

PLAN = {
    "focus_areas": [
        {"area": "A", "weight": 0.5, "reason": ""},
        {"area": "B", "weight": 0.5, "reason": ""},
    ],
    "suggested_questions": [f"建议题{i}" for i in range(1, 8)],
}


def test_contract_first_seven_suggested_last_three_generated() -> None:
    asked: list[dict] = []
    for i in range(10):
        spec = select_next_question_spec(
            interview_plan=PLAN,
            plan_status="ready",
            degraded=False,
            questions=asked,
            max_questions=10,
        )
        assert spec.use_plan_block is True
        if i < 7:
            assert spec.source == "suggested"
            assert spec.question == f"建议题{i + 1}"
        else:
            assert spec.source == "generated"
        asked.append(
            {
                "question": spec.question or f"g{i}",
                "source": spec.source,
            }
        )


def test_contract_schedule_length_matches_n() -> None:
    assert len(build_focus_schedule(PLAN["focus_areas"], 10)) == 10
