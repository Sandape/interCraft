"""REQ-041 US-2 FR-005 — ``MarkComplete`` end-of-flow tool.

Calling ``MarkComplete`` from a LangGraph node signals that the agent
considers its current task done. The actual state transition is the
caller's responsibility: the wrapping node function should set
``state["_mark_complete"] = True`` in its return delta, and the
conditional-edge router (e.g.
:func:`app.agents.nodes.error_coach.loop_or_finish.loop_or_finish_node`)
checks that field before deciding between ``hint_ladder`` and END.

This separation keeps the tool itself pure / side-effect free
(``side_effects=["ws_push"], requires_approval=True`` per AC-6.5) and
lets different agents react differently to the same MarkComplete
invocation.
"""
from __future__ import annotations

from langchain_core.tools import tool


@tool
async def MarkComplete(reason: str = "") -> str:
    """Signal that the agent believes the current task is complete.

    Call this when:
    - you have enough information to answer the user's question;
    - the user has explicitly signaled satisfaction; or
    - you have determined the conversation should end now.

    Args:
        reason: optional free-form explanation the LLM wants to record.

    Returns:
        A short confirmation string. The surrounding node function is expected
        to translate this into ``state["_mark_complete"] = True`` so the
        conditional edge router can route to END.
    """
    if reason:
        return f"complete: {reason}"
    return "complete"


__all__ = ["MarkComplete"]
