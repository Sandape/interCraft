"""M18 node — aggregate_scores: pure aggregation, no LLM.

Aggregates interview report scores into per-dimension weighted scores.
"""
from __future__ import annotations

from app.agents.state.ability_diagnose_state import AbilityDiagnoseState
from app.agents.tools.query_interview_score import (
    query_ai_messages_for_session,
    query_interview_report,
    query_interview_questions,
)


async def aggregate_scores_node(state: AbilityDiagnoseState) -> dict:
    """Aggregate interview scores from the report and questions."""
    session_id = state.get("session_id", "")

    report = await query_interview_report(session_id)
    questions = await query_interview_questions(session_id)
    ai_msgs = await query_ai_messages_for_session(session_id)

    dimension_scores_raw = {}
    if report and report.get("dimension_scores"):
        dimension_scores_raw = report["dimension_scores"]

    # Convert to standard format
    scores = []
    for dim, score_data in dimension_scores_raw.items():
        if isinstance(score_data, dict):
            scores.append({
                "dimension": dim,
                "score": float(score_data.get("score", 0)),
                "max_score": float(score_data.get("max_score", 10)),
                "weight": float(score_data.get("weight", 1.0)),
                "question_count": score_data.get("question_count", 0),
            })
        else:
            scores.append({
                "dimension": dim,
                "score": float(score_data),
                "max_score": 10,
                "weight": 1.0,
                "question_count": 1,
            })

    # Also derive from per_question_score if available
    per_q = report.get("per_question_score", []) if report else []
    for q in per_q:
        dim = q.get("dimension", "unknown")
        existing = next((s for s in scores if s["dimension"] == dim), None)
        if existing is None:
            scores.append({
                "dimension": dim,
                "score": float(q.get("score", 0)),
                "max_score": 10,
                "weight": 1.0,
                "question_count": 1,
            })

    return {
        "interview_scores": scores,
    }


__all__ = ["aggregate_scores_node"]
