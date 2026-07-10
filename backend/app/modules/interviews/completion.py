"""Shared helpers for interview session completion detection.

Historically Service / WS / WeChat adapter each used ``len(scores) >= 5``,
which prematurely completed full-mode sessions (10/15 questions) and
conflicted with REQ-048 ``effective_max`` routing in the LangGraph.

Canonical signal: the report node has run and produced ``interview_report``
(and usually ``overall_score``). Graph routing already decides *when* to
enter report; persistence layers only need to detect that signal.
"""
from __future__ import annotations

from typing import Any


def is_interview_graph_complete(result: dict[str, Any] | None) -> bool:
    """Return True when a graph turn has produced a final report payload.

    Accepts either the raw ``ainvoke`` result dict or a state ``values``
    dict. Prefers ``interview_report`` (report node output) over score
    length so full / quick_drill / adaptive termination all share one rule.
    """
    if not isinstance(result, dict):
        return False
    if result.get("status") == "completed":
        return True
    report = result.get("interview_report")
    if isinstance(report, dict) and report:
        return True
    # Doubao mode ends after planner with no report — callers handle that
    # separately. Do not treat empty report + scores as complete.
    return False
