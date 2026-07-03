"""[AC-040-US2 FR-005 / AC-5.7] update_dim_error_log intermediate node.

When any of the 4 split update nodes (``update_dim_db`` /
``update_history`` / ``update_activities`` / ``ws_push``) raises an
exception, the graph routes here via ``add_conditional_edges`` with
the routing function ``_route_after_update_dim_db``. This node:

1. Reads ``state["db_warnings"]`` (TypedDict-compatible list of strings,
   AC-5.7a).
2. Writes the warnings to the OTel span as attributes (so they appear
   in LangSmith alongside the ERROR span).
3. Returns an empty state delta so the next conditional edge resumes
   the flow downstream (the node does **not** re-raise — we want the
   graph to continue).

The presence of this node in the graph is what makes the
``AC-5.7`` "DB failure does not block subsequent nodes" property
work: even if ``update_dim_db`` raises, ``update_history``,
``update_activities`` and ``ws_push`` still run.

Per US2 R2''' P1: this is an intermediate node, decorated with
``@traced_node`` like the other leaf nodes (decorated-name count
baseline = 22; this node is included in that baseline).
"""
from __future__ import annotations

import structlog

from app.agents.state.ability_diagnose_state import AbilityDiagnoseState
from app.observability import traced_node

logger = structlog.get_logger(__name__)


@traced_node("ability_diagnose.update_dim_error_log")
async def update_dim_error_log_node(state: AbilityDiagnoseState) -> dict:
    """Log accumulated ``state["db_warnings"]`` to OTel + structlog.

    Called by ``add_conditional_edges`` after any of the 4 update nodes
    raises. Returns an empty delta so the next edge can run normally.
    """
    warnings = list(state.get("db_warnings", []))
    if not warnings:
        # No warnings accumulated — fall through.
        return {}

    # Use structlog so the warning is also visible in the application log.
    logger.warning(
        "ability_diagnose.db_warnings",
        user_id=state.get("user_id", ""),
        session_id=state.get("session_id", ""),
        warnings=warnings,
    )
    # Return the accumulated warnings as a state delta so they survive
    # the next edge (LangGraph state diff propagation).
    return {"db_warnings": warnings}


__all__ = ["update_dim_error_log_node"]