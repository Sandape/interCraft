"""REQ-041 US-2 — Tools package entrypoint.

Re-exports the 4 ``@tool``-decorated query tools (FR-004) + 2 control-flow
tools (FR-005): ``tavily_search``, ``query_error_question_by_id``,
``query_resume_blocks``, ``query_interview_report`` (alias
``query_interview_score``), ``think_tool``, ``MarkComplete``.

``TOOL_REGISTRY`` is populated by ``_register_tools()``, called once on
import. The registration is idempotent (AC-6.6): calling
``_register_tools()`` twice does NOT grow ``TOOL_REGISTRY``.
"""
from __future__ import annotations

# AC-6.6a: 6 explicit imports — NO wildcard.
from app.agents.tools.control.mark_complete import MarkComplete
from app.agents.tools.control.think_tool import think_tool
from app.agents.tools.query_error_question import query_error_question_by_id
from app.agents.tools.query_interview_score import query_interview_report
from app.agents.tools.query_resume_blocks import query_resume_blocks
from app.agents.tools.spec import ToolSpec, extract_tool_spec
from app.agents.tools.tavily_search import tavily_search

TOOL_REGISTRY: dict[str, ToolSpec] = {}


def _register_tools() -> None:
    """Idempotently register the 6 known tools into ``TOOL_REGISTRY``.

    Order of precedence: a tool already in the registry is left untouched.
    New tools are inserted in the order they appear in ``_ALL_TOOL_FUNCS``.
    """
    _ALL_TOOL_FUNCS = (
        tavily_search,
        query_error_question_by_id,
        query_resume_blocks,
        query_interview_report,
        think_tool,
        MarkComplete,
    )
    for tool_func in _ALL_TOOL_FUNCS:
        if tool_func.name not in TOOL_REGISTRY:
            TOOL_REGISTRY[tool_func.name] = extract_tool_spec(tool_func)


# Trigger the one-shot, idempotent registration at module import time so
# callers can rely on ``TOOL_REGISTRY`` being populated immediately after
# ``from app.agents.tools import TOOL_REGISTRY``.
_register_tools()


__all__ = [
    "TOOL_REGISTRY",
    "_register_tools",
    "ToolSpec",
    "extract_tool_spec",
    "tavily_search",
    "query_error_question_by_id",
    "query_resume_blocks",
    "query_interview_report",
    "query_interview_score",
    "think_tool",
    "MarkComplete",
]
