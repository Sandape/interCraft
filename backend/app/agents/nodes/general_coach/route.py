"""M19 node — route: decide action based on confidence threshold."""
from __future__ import annotations

from app.agents.state.general_coach_state import GeneralCoachState

_REDIRECT_MAP = {
    "resume_optimize": "简历优化",
    "interview_practice": "面试练习",
    "career_advice": None,  # respond directly
    "chitchat": None,  # respond directly
}

_CONFIDENCE_THRESHOLD = 0.7


async def route_node(state: GeneralCoachState) -> dict:
    """Route based on intent confidence — redirect or respond."""
    intent = state.get("detected_intent", "chitchat")
    confidence = state.get("confidence", 0.0)

    redirect = None
    if confidence >= _CONFIDENCE_THRESHOLD:
        suggested = _REDIRECT_MAP.get(intent)
        if suggested:
            redirect = suggested

    return {
        "suggested_redirect": redirect,
    }


__all__ = ["route_node"]
