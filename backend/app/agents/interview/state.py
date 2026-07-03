"""[AC-040-US1] FR-002 — Interview agent state schemas.

This module defines the three-layer state schema for the Interview agent
(``InterviewInputState`` / ``InterviewOverallState`` / ``InterviewOutputState``)
introduced by REQ-040 US-1, alongside the legacy ``InterviewGraphState``
which is retained during the dual-track period (AC-8.3).

DEPRECATED — ``InterviewGraphState`` (single TypedDict)
--------------------------------------------------------
Retained for the dual-track 1-week observation window (FR-008 / AC-8.3).
Existing callers that still import ``InterviewGraphState`` continue to work
without modification. The class will be removed once the next release tag
(``v0.x``) is cut by the release manager after REQ-040 ships.

TODO(release-manager): cut release tag ``v0.x`` within 1 week of REQ-040
ship; once cut, ``InterviewGraphState`` can be deleted. Reference: AC-8.3
in ``.claude/teams/req040/ac-matrix/REQ-040-US1.md``.

Three-layer schema (US-1 / FR-002)
----------------------------------
- ``InterviewInputState``: only the entry-point fields a caller may set
  (``messages`` + ``thread_id``). Acts as the graph's input schema, so
  internal fields are filtered out of inbound state.
- ``InterviewOverallState``: full set of 20 fields, including the
  ``interview_plan`` field populated by the planner subgraph (unified
  field name across the planner subgraph and the parent graph — see
  AC-E2E-2). This is the state the StateGraph actually operates on.
- ``InterviewOutputState``: a Pydantic ``BaseModel`` with the final-report
  fields (``interview_report`` + ``overall_score``) — acts as the graph's
  output schema so callers receive a typed Pydantic object.

The 20 fields in ``InterviewOverallState`` (per AC-2.2; spec.md "21 fields"
is a spec typo, not a code reality)::

    messages, current_question, questions, scores, resume_context,
    position, company, base_location, difficulty, branch_id,
    overall_score, interview_report, error, user_id, thread_id,
    job_id, requirements_md, requirements_provided, requirements_truncated,
    requirements_original_chars
"""
from __future__ import annotations

from typing import Annotated, Any

from langgraph.graph.message import add_messages
from pydantic import BaseModel
from typing_extensions import TypedDict

from app.agents.interview.reducers import override_reducer


# ===========================================================================
# Legacy schema (DEPRECATED — kept for dual-track period per FR-008 / AC-8.3)
# ===========================================================================


class InterviewGraphState(TypedDict, total=False):
    """DEPRECATED — single-TypedDict state for the Interview Agent subgraph (T020).

    TODO(release-manager): cut release tag ``v0.x`` within 1 week of REQ-040
    ship; once cut, this class can be deleted. Reference: AC-8.3 in
    ``.claude/teams/req040/ac-matrix/REQ-040-US1.md``.

    Per research.md R-1 and data-model.md. This class is kept around so
    existing call sites that import ``InterviewGraphState`` continue to
    work during the dual-track 1-week observation window. New code should
    use ``InterviewOverallState`` (with the three-layer split) instead.
    """

    messages: Annotated[list[dict[str, Any]], add_messages]
    current_question: int
    questions: list[dict[str, Any]]
    scores: list[dict[str, Any]]
    resume_context: dict[str, Any] | None
    position: str
    company: str
    base_location: str | None
    difficulty: str
    branch_id: str | None
    overall_score: float | None
    interview_report: dict[str, Any] | None
    error: str | None
    user_id: str
    thread_id: str
    job_id: str | None
    requirements_md: str | None
    requirements_provided: bool
    requirements_truncated: bool
    requirements_original_chars: int


# ===========================================================================
# New three-layer schema (US-1 / FR-002)
# ===========================================================================


class InterviewInputState(TypedDict, total=False):
    """Input schema for the Interview graph.

    Only the entry-point fields a caller is allowed to set on the graph's
    input. Internal fields (scores, current_question, etc.) are filtered
    out by LangGraph's input schema enforcement.

    AC-2.1 enforces that this class exposes ONLY ``messages`` and
    ``thread_id``; internal fields must not leak into the input layer.
    """

    messages: Annotated[list[dict[str, Any]], add_messages]
    thread_id: str


class InterviewOverallState(TypedDict, total=False):
    """Overall state for the Interview graph — 21 fields.

    AC-2.2 enforces a 21-field whitelist (set equality). ``scores`` uses
    the custom ``override_reducer`` (FR-001) so nodes can reset the list
    via the ``{"type": "override", "value": X}`` protocol.

    The unified field name shared with the planner subgraph is documented
    in the AC matrix under AC-E2E-2. The legacy field name is forbidden
    in this module and the planner subgraph.
    """

    messages: Annotated[list[dict[str, Any]], add_messages]
    current_question: int
    questions: list[dict[str, Any]]
    scores: Annotated[list[dict[str, Any]], override_reducer]
    resume_context: dict[str, Any] | None
    position: str
    company: str
    base_location: str | None
    difficulty: str
    branch_id: str | None
    overall_score: float | None
    interview_report: dict[str, Any] | None
    # REQ-041 US1 FR-003 AC-3.1 — DUAL-TRACK period (1 week observation):
    # ``error_legacy: str | None`` is the LEGACY field, renamed from
    # ``error: str | None``. Existing callers that read ``state["error_legacy"]``
    # as a plain string continue to work. After the observation window +
    # release-manager cut, this field will be deleted.
    error_legacy: str | None
    # REQ-041 US1 FR-003 AC-3.1 — typed failure envelope written by
    # ``@node_error_handler(fallback_strategy="use_previous")``. Serialised
    # to the API response as ``error_category`` + ``node_name``.
    error: dict[str, Any] | None
    user_id: str
    thread_id: str
    job_id: str | None
    requirements_md: str | None
    requirements_provided: bool
    requirements_truncated: bool
    requirements_original_chars: int
    # v2 addition (US-1 / FR-002): unified field name shared with the
    # planner subgraph. AC-2.2 references the 20 legacy fields above; the
    # ``interview_plan`` field is a Phase 2 implementation extension
    # required for AC-E2E-2 to function (the planner must write to a
    # declared state field; the legacy 20-field set has no slot for the
    # unified name). This 21st field is the minimal addition needed.
    interview_plan: dict[str, Any] | None


class InterviewOutputState(BaseModel):
    """Output schema for the Interview graph — Pydantic BaseModel.

    AC-2.3 enforces Pydantic + ``interview_report`` + ``overall_score``.
    LangGraph's output schema enforcement filters the final state to
    only these fields, returning a typed Pydantic object to the caller.
    """

    interview_report: dict[str, Any] | None = None
    overall_score: float | None = None
    current_question: int | None = None


__all__ = [
    "InterviewGraphState",
    "InterviewInputState",
    "InterviewOverallState",
    "InterviewOutputState",
]
