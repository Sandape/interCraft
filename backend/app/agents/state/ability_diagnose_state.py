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
    """

    messages: Annotated[list[dict[str, Any]], add_messages]
    user_id: str
    session_id: str
    interview_scores: list[dict[str, Any]]
    historical_dims: list[dict[str, Any]]
    current_dims: list[dict[str, Any]]
    diagnoses: list[dict[str, Any]]
    insights: list[dict[str, Any]]


__all__ = ["AbilityDiagnoseState"]
