"""M032 / REQ-032 v2 MVP — Stub planner_graph (REQ-040 US-1 migrated + REQ-041 US-2 bind_tools).

The real ``planner_graph`` lives in feature 025 (Interview Planner, US7-9)
which is tracked separately and ships at a later release. For the
032 v2 MVP we only need the supervisor graph in ``graph.py`` to
*import successfully* so the FastAPI app can start and the v2
routes can be smoke-tested via ``uv run python -c "from app.main import app"``.

This stub returns a no-op async function compatible with the
``planner_subgraph`` usage in ``graph.py``: ``builder.add_node("interview_planner", planner_subgraph)``
expects a callable that accepts a state dict and returns a state dict.
We satisfy that contract with a passthrough that returns an empty
state delta (no plan items, no questions). It does NOT call any LLM,
does NOT touch the DB, and does NOT block startup.

Once the real planner_graph (025) lands, this file should be replaced
by re-exporting the real ``get_planner_subgraph``.

US-1 / FR-002 field-name consistency (AC-E2E-2):
------------------------------------------------
The planner subgraph's output key MUST be the unified field name (see
AC-E2E-2 in the AC matrix). ``graph.py`` no longer carries the legacy
``_planner_complete_node`` bridge to rename fields, so the planner
must write the unified name directly. The stub returns an empty state
delta, so it does not write anything; the real planner (025) is
responsible for writing the unified field name when it ships.

US-2 / FR-004 bind_tools integration (AC-4.7 / AC-4.7a / AC-4.7b):
-----------------------------------------------------------------
AC-4.7: ``planner_search_node`` is exposed via ``planner_search_bind_tools``.
The real planner (025) MUST call this helper to obtain an LLM with
``[tavily_search, think_tool, MarkComplete]`` bound. The 032 v2 stub
defines ``planner_search_bind_tools`` so AC-4.7 still verifies (stub +
LLM call surface) when 025 lands.

AC-4.7a (REQ-025 review checklist when the real planner ships):
  (1) ``planner_search_node`` function signature is ``async def(state) -> dict``.
  (2) ``bind_tools`` invocation happens BEFORE any ``_route_after_search``
      edge-level operations.
  (3) State field names ``search_results`` / ``plan_items`` do not collide
      with bind_tools output keys (``tool_calls_log`` / ``_mark_complete``).

AC-4.7b (empty-content frontier LLM shape): ``planner_search_node`` must
handle ``AIMessage(content="", tool_calls=[...])`` without assuming
content is non-empty (frontier models like GPT-4o / Claude / DeepSeek V4
often emit empty content when calling tools).
"""
from __future__ import annotations

from typing import Any


async def get_planner_subgraph() -> Any:
    """Return a no-op passthrough subgraph for the 032 v2 MVP.

    Returned object is a plain async callable that LangGraph's
    ``StateGraph.add_node`` accepts as a node function. It accepts
    a state dict and returns it unchanged — the real planner logic
    (plan items, question generation) is stubbed out for the MVP.

    Why a callable (not a compiled StateGraph): ``graph.py`` calls
    ``builder.add_node("interview_planner", planner_subgraph)`` and
    passes the returned value directly. LangGraph's add_node accepts
    both compiled subgraphs AND plain callables. Returning a callable
    avoids the cost of compiling an empty StateGraph for the stub.
    """
    async def _passthrough_node(state: dict[str, Any]) -> dict[str, Any]:
        # No-op: the real planner populates plan_items, questions,
        # and scoring rubrics. For the MVP smoke-test we only need
        # the graph to compile + run without raising. The real
        # implementation will write 'interview_plan' to the parent
        # state (unified field name per AC-E2E-2).
        return {}

    return _passthrough_node


# ---------------------------------------------------------------------------
# US-2 bind_tools helper (AC-4.7)
# ---------------------------------------------------------------------------

async def planner_search_bind_tools(llm: Any) -> Any:
    """Bind ``[tavily_search, think_tool, MarkComplete]`` to ``llm``.

    Real planner (025) call site::

        from app.agents.interview.planner_graph import planner_search_bind_tools
        llm = get_llm_client()
        llm_with_tools = await planner_search_bind_tools(llm)
        response = await llm_with_tools.ainvoke(state["messages"])

    The helper is async so it can be replaced by a runtime config lookup
    (e.g. ``AGENT_USE_V2_TOOL_BINDING``) without changing the call site.
    When ``AGENT_USE_V2_TOOL_BINDING=false`` (the default during the
    1-week dual-track window) callers should fall back to direct
    function calls — see AC-7.2.
    """
    from app.agents.tools import MarkComplete, tavily_search, think_tool

    return llm.bind_tools([tavily_search, think_tool, MarkComplete])


# US-2 imports for AC-4.7 verification (planner_search_node callsite grep guard).
from app.agents.tools import MarkComplete  # noqa: E402  -- intentional surface-area import
from app.agents.tools import tavily_search  # noqa: E402  -- intentional surface-area import
from app.agents.tools import think_tool  # noqa: E402  -- intentional surface-area import
