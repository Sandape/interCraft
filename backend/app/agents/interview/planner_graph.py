"""REQ-025 interview planner subgraph.

The mock interview flow is a two-agent supervisor: the parent interview graph
routes into this Planner Agent first, then hands ``interview_plan`` and
``web_research`` to the Interviewer Agent's question generator.
"""
from __future__ import annotations

from typing import Any

from langgraph.graph import END, StateGraph

from app.agents.interview.nodes.planner_context import planner_context_node
from app.agents.interview.nodes.planner_generate import planner_generate_node
from app.agents.interview.nodes.planner_search import planner_search_node
from app.agents.interview.state import InterviewGraphState
from app.observability import traced_node


@traced_node("interview_planner.context")
async def planner_context(state: dict[str, Any]) -> dict[str, Any]:
    return await planner_context_node(state)


@traced_node("interview_planner.search")
async def planner_search(state: dict[str, Any]) -> dict[str, Any]:
    return await planner_search_node(state)


@traced_node("interview_planner.generate")
async def planner_generate(state: dict[str, Any]) -> dict[str, Any]:
    return await planner_generate_node(state)


def get_planner_subgraph() -> Any:
    """Return the compiled Planner Agent subgraph.

    This is intentionally synchronous because the parent interview graph calls
    it while building nodes. Returning a compiled runnable gives tests and
    runtime code a stable ``.ainvoke`` surface.
    """
    builder = StateGraph(InterviewGraphState)
    builder.add_node("interview_planner.context", planner_context)
    builder.add_node("interview_planner.search", planner_search)
    builder.add_node("interview_planner.generate", planner_generate)

    builder.set_entry_point("interview_planner.context")
    builder.add_edge("interview_planner.context", "interview_planner.search")
    builder.add_edge("interview_planner.search", "interview_planner.generate")
    builder.add_edge("interview_planner.generate", END)

    return builder.compile()


async def planner_search_bind_tools(llm: Any) -> Any:
    """Bind search and control-flow tools to an LLM implementation."""
    from app.agents.tools import MarkComplete, tavily_search, think_tool
    from app.agents.tools.approval import bind_tools_with_approval

    return bind_tools_with_approval(llm, [tavily_search, think_tool, MarkComplete])


from app.agents.tools import MarkComplete  # noqa: E402
from app.agents.tools import tavily_search  # noqa: E402
from app.agents.tools import think_tool  # noqa: E402


# ---------------------------------------------------------------------------
# REQ-048 US4 / T085 — Planner subgraph return value when mode='doubao'.
#
# When the parent interview graph routes through ``_route_after_planner``
# with ``state.mode == 'doubao'``, the Planner subgraph is the LAST node
# to execute. The interview_sessions row is written by the API service
# layer (POST /interview-sessions with mode='doubao') BEFORE the graph
# runs, but the InterviewPlan dict returned by planner_generate_node
# needs to flow through to the card-render API endpoint
# (GET /interviews/{session_id}/card) which reads it from the
# interview_sessions.interview_plan column.
#
# This helper is the contract surface used by:
#   - the API service (service.py) — to update interview_plan
#     column after Planner completes
#   - the tests (test_us4_doubao_mode.py) — to verify the dict
#     structure
# ---------------------------------------------------------------------------


def extract_interview_plan(graph_state: dict[str, Any]) -> dict[str, Any] | None:
    """Pull the InterviewPlan out of a planner subgraph final state.

    Returns ``None`` when the plan field is missing or empty (Planner
    failed / was skipped). Callers should fall back to a minimal plan
    or surface a CARD_RENDER_FAILED error per AC-22.
    """
    if not isinstance(graph_state, dict):
        return None
    values = graph_state.get("values")
    if isinstance(values, dict):
        plan = values.get("interview_plan")
    else:
        plan = graph_state.get("interview_plan")
    if not isinstance(plan, dict):
        return None
    if not plan:
        return None
    return plan


__all__ = [
    "extract_interview_plan",
    "get_planner_subgraph",
    "planner_context",
    "planner_generate",
    "planner_search",
    "planner_search_bind_tools",
]
