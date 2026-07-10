"""Regression coverage for degraded full-interview routing."""
from __future__ import annotations

from app.agents.interview.graph import _route_after_intake


def test_degraded_full_session_skips_planner_after_intake() -> None:
    state = {
        "mode": "full",
        "plan_status": "degraded",
        "degraded": True,
        "interview_plan": None,
    }

    assert _route_after_intake(state) == "interview.mode_guard"


def test_ready_full_session_reuses_plan_without_replanning() -> None:
    state = {
        "mode": "full",
        "plan_status": "ready",
        "degraded": False,
        "interview_plan": {"suggested_questions": ["Explain a RAG evaluation loop."]},
    }

    assert _route_after_intake(state) == "interview.mode_guard"


def test_full_session_without_plan_still_runs_planner() -> None:
    state = {
        "mode": "full",
        "plan_status": "pending",
        "degraded": False,
        "interview_plan": None,
    }

    assert _route_after_intake(state) == "interview_planner"


def test_doubao_card_session_still_runs_planner() -> None:
    state = {
        "mode": "doubao",
        "plan_status": "degraded",
        "degraded": True,
    }

    assert _route_after_intake(state) == "interview_planner"


def test_quick_drill_session_skips_planner_after_intake() -> None:
    state = {
        "mode": "quick_drill",
        "plan_status": None,
        "degraded": False,
        "error_question_ids": ["q1", "q2", "q3", "q4", "q5"],
    }

    assert _route_after_intake(state) == "interview.drill_selector"
