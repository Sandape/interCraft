"""M17 node — fetch_question: load error question data."""
from __future__ import annotations

from app.agents.state.error_coach_state import ErrorCoachState
from app.agents.tools.query_error_question import query_error_question_by_id
from app.observability import traced_node


@traced_node("error_coach.fetch_question")
async def fetch_question_node(state: ErrorCoachState) -> dict:
    """Fetch the error question record and initialize state."""
    error_question_id = state.get("error_question_id", "")
    user_id = state.get("user_id", "")

    question = await query_error_question_by_id(error_question_id, user_id=user_id)

    if question is None:
        return {
            "question": {},
            "messages": [{"role": "system", "content": "Error question not found."}],
        }

    return {
        "question": question,
        "correct_count": 0,
        "attempt_count": 0,
        "current_hint_level": "small",
        "messages": [{"role": "system", "content": f"Loaded error question: {question.get('question_text', '')[:50]}..."}],
    }


__all__ = ["fetch_question_node"]