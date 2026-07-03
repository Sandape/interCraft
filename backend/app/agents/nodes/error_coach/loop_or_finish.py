"""M17 node — loop_or_finish: check completion condition.

End the session when the LLM has called ``MarkComplete`` (sets
``state['_mark_complete'] = True``), OR ``correct_count >= 3``, OR the
user has aborted the session.
"""
from __future__ import annotations

from app.agents.state.error_coach_state import ErrorCoachState
from app.observability import traced_node


@traced_node("error_coach.loop_or_finish")
async def loop_or_finish_node(state: ErrorCoachState) -> dict:
    """Check if the error coach session should continue or end.

    Priority order (REQ-041 US2 AC-5.5a — ``_mark_complete`` FRONT-branch):

        1. ``state["_mark_complete"]`` (LLM-driven ``MarkComplete`` tool)
           — overrides every other condition. Set to True by the wrapping
           node function after the LLM invokes ``MarkComplete``.
        2. ``correct_count >= 3``  — legacy completion guard.
        3. ``session_aborted``     — user-initiated cancellation.

    If none match, emit the "continue" message and the graph routes to
    ``hint_ladder`` for another attempt.
    """
    # AC-5.5a FRONT-branch — ``_mark_complete`` wins over correct_count.
    if state.get("_mark_complete"):
        return {
            "next_node": "END",
            "_mark_complete": True,
            "messages": [
                {"role": "system", "content": "MarkComplete: LLM signalled end-of-flow."},
            ],
        }

    correct_count = state.get("correct_count", 0)
    attempt_count = state.get("attempt_count", 0)
    session_aborted = state.get("session_aborted", False)

    if session_aborted or correct_count >= 3:
        return {
            "next_node": "END",
            "correct_count": correct_count,
            "messages": [{"role": "system", "content": "Session complete. Updating frequency..."}],
        }

    return {
        "next_node": "hint_ladder",
        "attempt_count": attempt_count,
        "messages": [
            {
                "role": "system",
                "content": f"Continue. Correct: {correct_count}/3, Attempts: {attempt_count}",
            },
        ],
    }


__all__ = ["loop_or_finish_node"]
