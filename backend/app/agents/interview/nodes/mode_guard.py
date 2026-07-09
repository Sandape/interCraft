"""[REQ-048 US1/US4] mode_guard node — early-stop for ``mode='doubao'``.

After the planner subgraph writes ``interview_plan`` to state, the
``mode_guard`` node inspects ``state.mode`` and signals the parent
graph to terminate (END) when ``mode == 'doubao'`` — US4 expects only
Planner to run, never question_gen / score_llm / report (FR-050, R9,
AC-23). For ``mode in {'quick_drill', 'full'}`` the node is a no-op
pass-through that lets the existing flow proceed.

Phase 1+2 skeleton; the actual early-stop is wired in graph.py via the
conditional edge after the planner subgraph (T025 + T029).
"""
from __future__ import annotations

from typing import Any

from app.agents.interview.state import InterviewGraphState
from app.observability import traced_node


@traced_node("interview.mode_guard")
async def mode_guard_node(state: InterviewGraphState) -> dict:
    """No-op pass-through; the early-stop decision is taken by graph.py
    via the conditional edge that reads ``state.mode``."""
    return {}


__all__ = ["mode_guard_node"]