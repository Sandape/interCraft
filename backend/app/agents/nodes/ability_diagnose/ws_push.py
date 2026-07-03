"""[AC-040-US2 FR-005] ws_push node — best-effort WS push for agent.final event.

Pushes a single ``agent.final`` event to the user via the WebSocket
``connection_manager``. Best-effort: failures do **not** affect DB
writes (US2 AC-5.6).

Per US2 AC-5.6, this node is the only one that touches ``send_to_user``
and the only one that should appear in OTel with the
``ws.*`` attributes. It does NOT write to any DB table.
"""
from __future__ import annotations

from app.agents.state.ability_diagnose_state import AbilityDiagnoseState
from app.observability import traced_node


@traced_node("ability_diagnose.ws_push")
async def ws_push_node(state: AbilityDiagnoseState) -> dict:
    """Push an ``agent.final`` event to the user (best-effort)."""
    user_id = state.get("user_id", "")
    diagnoses = state.get("diagnoses", [])
    session_id = state.get("session_id", "")

    if not user_id:
        return {}

    try:
        from app.core.ws import connection_manager
        from app.core.ws_events import make_agent_final

        dims_summary = ", ".join(
            f"{d['dimension']}: {d.get('current_score', 0):.1f}" for d in diagnoses
        )
        event = make_agent_final(
            thread_id=session_id or "",
            graph="ability_diagnose",
            summary=f"能力画像已更新:{dims_summary}",
            dimensions_updated=True,
        )
        await connection_manager.send_to_user(user_id, event)
    except Exception:
        # AC-5.6: WS push is best-effort. DB writes must not be blocked.
        # The failure is recorded in the OTel span by @traced_node but
        # the graph continues to END.
        return {}

    return {}


__all__ = ["ws_push_node"]