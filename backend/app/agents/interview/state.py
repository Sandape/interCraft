"""InterviewGraphState — TypedDict for the Interview Agent subgraph (T020).

Per research.md R-1 and data-model.md.
"""
from __future__ import annotations

from typing import Annotated, Any

from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class InterviewGraphState(TypedDict, total=False):
    """State shared across all interview graph nodes.

    messages: conversation history with add_messages reducer (dedup by message ID).
    current_question: 0-based index of current question (0-4).
    questions: accumulated list of generated questions with metadata.
    scores: accumulated list of score results.
    resume_context: optional resume content for contextual questions.
    position: target job position.
    company: target job company.
    base_location: target job base location (019).
    difficulty: interview difficulty level (default "medium").
    branch_id: optional resume branch for context.
    overall_score: final aggregated score (set by report node).
    report: final report data (set by report node).
    error: error message if a node failed.
    user_id: authenticated user UUID (required for LLM quota tracking).
    thread_id: conversation thread ID.
    job_id: optional job UUID (019 — drives requirements_md prefill).
    # 019 — requirements injection (consumed by question_gen + report)
    requirements_md: str | None
    requirements_provided: bool
    requirements_truncated: bool
    requirements_original_chars: int
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


__all__ = ["InterviewGraphState"]
