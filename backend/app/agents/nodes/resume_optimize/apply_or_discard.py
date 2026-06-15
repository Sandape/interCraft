"""M16 node — apply_or_discard: interrupt point for user decision.

This is the human-in-the-loop interrupt node.
The graph is compiled with interrupt_after this node, so execution
pauses here and waits for the confirm endpoint to supply the decision.
"""
from __future__ import annotations

from app.agents.state.resume_optimize_state import ResumeOptimizeState


async def apply_or_discard_node(state: ResumeOptimizeState) -> dict:
    """Interrupt point — evaluate user decision and route.

    This node reads the `decision` field set by the confirm endpoint.
    Returns routing info used by the conditional edge.
    """
    decision = state.get("decision")
    thread_aborted = state.get("thread_aborted", False)

    if thread_aborted or decision == "discard":
        return {
            "messages": [{"role": "system", "content": "Changes discarded by user."}],
        }

    if decision == "apply":
        return {
            "messages": [{"role": "system", "content": "Changes approved. Applying patches..."}],
        }

    # No decision yet — still waiting for user input
    return {
        "messages": [{"role": "system", "content": "Awaiting user decision."}],
    }


__all__ = ["apply_or_discard_node"]
