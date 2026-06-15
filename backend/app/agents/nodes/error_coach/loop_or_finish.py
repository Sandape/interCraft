"""M17 node — loop_or_finish: check completion condition.

End the session when correct_count >= 3 or session_aborted.
"""
from __future__ import annotations

from app.agents.state.error_coach_state import ErrorCoachState


async def loop_or_finish_node(state: ErrorCoachState) -> dict:
    """Check if the error coach session should continue or end."""
    correct_count = state.get("correct_count", 0)
    attempt_count = state.get("attempt_count", 0)
    session_aborted = state.get("session_aborted", False)

    if session_aborted or correct_count >= 3:
        return {
            "correct_count": correct_count,
            "messages": [{"role": "system", "content": "Session complete. Updating frequency..."}],
        }

    return {
        "attempt_count": attempt_count,
        "messages": [{"role": "system", "content": f"Continue. Correct: {correct_count}/3, Attempts: {attempt_count}"}],
    }


__all__ = ["loop_or_finish_node"]
