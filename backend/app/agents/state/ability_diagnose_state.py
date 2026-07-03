"""AbilityDiagnoseState — TypedDict for M18 Ability Diagnose subgraph.

Per data-model.md.
"""
from __future__ import annotations

from typing import Annotated, Any

from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class AbilityDiagnoseState(TypedDict, total=False):
    """State for the Ability Diagnose agent (M18).

    messages: conversation history with add_messages reducer.
    user_id: authenticated user UUID.
    session_id: interview session UUID (trigger source).
    interview_scores: aggregate_scores node output — per-dimension weighted scores.
    historical_dims: compare_baseline output — last 90 days history.
    current_dims: query_dimensions current ability values.
    diagnoses: per-dimension delta + trend markers.
    insights: LLM-generated improvement suggestions.
    db_warnings: list of human-readable DB warning strings accumulated by
        the split update_dim_* nodes (US2 AC-5.7 / AC-5.7a). Each
        update_dim_* node appends a one-line summary when its underlying
        DB operation fails (e.g. ``"update_dim_db: connection is closed"``).
        Downstream ``update_dim_error_log`` reads this list to log a
        structured warning via the OTel span. TypedDict-compatible: no
        ``Field(default_factory=list)`` — defaults are handled at the node
        level (``state.get("db_warnings", [])``).
    """

    messages: Annotated[list[dict[str, Any]], add_messages]
    user_id: str
    session_id: str
    interview_scores: list[dict[str, Any]]
    historical_dims: list[dict[str, Any]]
    current_dims: list[dict[str, Any]]
    diagnoses: list[dict[str, Any]]
    insights: list[dict[str, Any]]
    db_warnings: list[str]
    # REQ-041 US1 FR-003 (AC-3.1) — failure envelope written by
    # ``@node_error_handler(fallback_strategy="use_previous")`` on node failure.
    # TypedDict-compatible (total=False) so absent == None.
    # Serialised to API response as ``error_category`` + ``node_name`` by
    # ``app.agents.utils.node_error.serialize_state_error``.
    error: dict[str, Any] | None
    # REQ-042 US-1 FR-001 — soft iteration cap + monotonic counter.
    max_iterations: int
    iteration_count: int


__all__ = ["AbilityDiagnoseState"]
