"""M032 / REQ-032 v2 MVP — Stub planner_graph.

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
        # the graph to compile + run without raising.
        return {}

    return _passthrough_node