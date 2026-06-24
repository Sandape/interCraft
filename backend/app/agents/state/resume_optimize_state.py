"""ResumeOptimizeState — TypedDict for M16 Resume Optimize subgraph.

Per data-model.md.
"""
from __future__ import annotations

from typing import Annotated, Any, Literal

from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class ResumeOptimizeState(TypedDict, total=False):
    """State for the Resume Optimize agent (M16).

    messages: conversation history with add_messages reducer.
    user_id: authenticated user UUID.
    branch_id: target resume branch UUID.
    target_jd: target JD text.
    current_blocks: snapshot of branch blocks at start.
    proposed_patches: JSON Patch array from diff_jd node.
    summary: optimization summary text.
    decision: user decision after interrupt (apply/discard).
    thread_aborted: set to True on timeout or user abort.
    """

    messages: Annotated[list[dict[str, Any]], add_messages]
    user_id: str
    branch_id: str
    target_jd: str
    current_blocks: list[dict[str, Any]]
    proposed_patches: list[dict[str, Any]]
    summary: str | None
    decision: Literal["apply", "discard"] | None
    thread_aborted: bool
    # US5: per-patch accept/reject. None = apply all; otherwise apply only these indices.
    accepted_patch_indices: list[int] | None


__all__ = ["ResumeOptimizeState"]
