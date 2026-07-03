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

    # REQ-041 US2 FR-005 — ``MarkComplete`` priority over ``correct_count`` guard.
    # When the LLM calls the ``MarkComplete`` @tool (FR-005), the surrounding
    # node function returns ``{"_mark_complete": True}`` and the
    # conditional-edge router (``loop_or_finish_node``) reads this field as a
    # FRONT-branch (before the ``correct_count >= 3`` loop guard per AC-5.5a).
    _mark_complete: bool

    # REQ-042 US-1 FR-001 — soft iteration cap (per-agent default via
    # ``Configuration.max_iterations``). Read by ``iteration_guard_node``;
    # raised to ``state.error.error_category=loop_terminated`` on overflow.
    max_iterations: int
    # REQ-042 US-1 FR-001 — monotonic add reducer counter incremented by
    # ``iteration_guard_node`` on each evaluation cycle.
    iteration_count: int


__all__ = ["ErrorCoachState"]

