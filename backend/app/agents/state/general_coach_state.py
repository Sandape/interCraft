"""GeneralCoachState — TypedDict for M19 General Coach subgraph.

Per data-model.md.
"""
from __future__ import annotations

from typing import Annotated, Any

from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class GeneralCoachState(TypedDict, total=False):
    """State for the General Coach agent (M19).

    messages: conversation history with add_messages reducer.
    user_id: authenticated user UUID.
    conversation_id: conversation UUID (= thread_id).
    detected_intent: intent classification result.
    confidence: LLM self-reported confidence (0-1).
    suggested_redirect: target subgraph name for redirect.
    session_active: whether the conversation is active.
    """

    # REQ-041 US1 FR-003 (AC-3.1) - failure envelope written by
    # @node_error_handler(fallback_strategy="use_previous") on node failure.
    # TypedDict-compatible (total=False) so absent == None.
    # Serialised to API response as error_category + node_name.
    error: dict[str, Any] | None
    messages: Annotated[list[dict[str, Any]], add_messages]
    user_id: str
    conversation_id: str
    detected_intent: str | None
    confidence: float | None
    suggested_redirect: str | None
    session_active: bool


__all__ = ["GeneralCoachState"]

