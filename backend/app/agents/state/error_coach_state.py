"""ErrorCoachState — TypedDict for M17 Error Coach subgraph.

Per data-model.md.
"""
from __future__ import annotations

from typing import Annotated, Any, Literal

from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class ErrorCoachState(TypedDict, total=False):
    """State for the Error Coach agent (M17).

    messages: conversation history with add_messages reducer.
    user_id: authenticated user UUID.
    error_question_id: target error question UUID.
    question: full error question record.
    correct_count: accumulated correct answers (threshold ≥ 3).
    attempt_count: total attempts in this session.
    current_hint_level: current hint gradient level.
    session_aborted: set to True on user abort.
    """

    # REQ-041 US1 FR-003 (AC-3.1) - failure envelope written by
    # @node_error_handler(fallback_strategy="use_previous") on node failure.
    # TypedDict-compatible (total=False) so absent == None.
    # Serialised to API response as error_category + node_name.
    error: dict[str, Any] | None
    messages: Annotated[list[dict[str, Any]], add_messages]
    user_id: str
    error_question_id: str
    question: dict[str, Any]
    correct_count: int
    attempt_count: int
    current_hint_level: Literal["small", "medium", "detailed"]
    session_aborted: bool


__all__ = ["ErrorCoachState"]

