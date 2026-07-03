"""M18 Ability Diagnose StateGraph — LangGraph agent for post-interview ability diagnosis.

Graph structure (US2 FR-005 + AC-5.9):
    aggregate_scores → compare_baseline → generate_insight →
    update_dim_db → update_history → update_activities → ws_push → END

Failure handling (US2 AC-5.7):
- Each ``update_dim_*`` node re-raises on ``OperationalError`` so the
  ``@traced_node`` outer span is marked ERROR (AC-6.5).
- ``add_conditional_edges`` after each ``update_dim_*`` node routes
  through ``update_dim_error_log`` (intermediate node, AC-5.7) using
  ``_route_after_update_dim_db`` to inspect the latest state for
  accumulated ``db_warnings``.
- ``update_dim_error_log`` returns the warnings as a state delta and
  the graph continues to the next node (no re-raise).

Triggered by ARQ task ``diagnose_after_interview``.
"""
from __future__ import annotations

from typing import Any, Literal

from langgraph.graph import END, StateGraph

from app.agents.base import BaseAgent
from app.agents.checkpointer import get_checkpointer, get_graph_config, retry_graph_op
from app.agents.nodes.ability_diagnose.aggregate_scores import aggregate_scores_node
from app.agents.nodes.ability_diagnose.compare_baseline import compare_baseline_node
from app.agents.nodes.ability_diagnose.generate_insight import generate_insight_node
from app.agents.nodes.ability_diagnose.update_dim_db import update_dim_db_node
from app.agents.nodes.ability_diagnose.update_dim_error_log import (
    update_dim_error_log_node,
)
from app.agents.nodes.ability_diagnose.update_history import update_history_node
from app.agents.nodes.ability_diagnose.update_activities import (
    update_activities_node,
)
from app.agents.nodes.ability_diagnose.ws_push import ws_push_node
from app.agents.state.ability_diagnose_state import AbilityDiagnoseState
from app.observability import traced_node


# ---------------------------------------------------------------------------
# Routing function for the 4 split update nodes (US2 AC-5.7).
#
# Each ``update_dim_*`` node may re-raise OperationalError. The graph
# inspects ``state["db_warnings"]`` after the node returns / raises;
# if warnings exist, route to ``update_dim_error_log`` so the warnings
# are logged via OTel + structlog. Otherwise proceed to the next node
# in the pipeline.
#
# Important: in LangGraph, an exception inside a node is propagated to
# the next edge. ``add_conditional_edges`` can either route via the
# conditional function OR let the exception bubble up to the caller.
# To preserve "DB failure does not block downstream", the update
# nodes catch + log + re-raise, then the routing function inspects
# the **state delta** returned and routes to ``update_dim_error_log``
# when ``db_warnings`` is non-empty.
# ---------------------------------------------------------------------------


def _route_after_update_dim_db(
    state: Any,
) -> Literal["update_dim_error_log", "update_history"]:
    """Route from ``update_dim_db`` to either the error-log intermediate or
    the next pipeline node.

    Inspects ``state["db_warnings"]``: if the previous node appended a
    warning, route to ``update_dim_error_log``; otherwise proceed to
    ``update_history``.
    """
    if isinstance(state, dict):
        warnings = state.get("db_warnings", [])
    else:
        warnings = getattr(state, "db_warnings", []) or []
    if warnings:
        return "update_dim_error_log"
    return "update_history"


def _route_after_update_dim_error_log(
    state: Any,
) -> Literal["update_history", "update_activities", "ws_push", END]:
    """After logging the warnings, continue to the next pipeline node.

    The intermediate ``update_dim_error_log`` does not know which
    downstream node was the source of the error, so we always continue
    from ``update_history`` (the next unblocked step). If the error
    happened in a later node, the route resets the cycle.
    """
    return "update_history"


def _route_after_update_history(
    state: Any,
) -> Literal["update_dim_error_log", "update_activities"]:
    """Same pattern as ``_route_after_update_dim_db`` for history."""
    if isinstance(state, dict):
        warnings = state.get("db_warnings", [])
    else:
        warnings = getattr(state, "db_warnings", []) or []
    if warnings:
        return "update_dim_error_log"
    return "update_activities"


def _route_after_update_activities(
    state: Any,
) -> Literal["update_dim_error_log", "ws_push"]:
    """Same pattern as ``_route_after_update_dim_db`` for activities."""
    if isinstance(state, dict):
        warnings = state.get("db_warnings", [])
    else:
        warnings = getattr(state, "db_warnings", []) or []
    if warnings:
        return "update_dim_error_log"
    return "ws_push"


def _route_after_ws_push(
    state: Any,
) -> Literal["update_dim_error_log", "__end__"]:
    """Last node in the pipeline; either log warnings or end the graph."""
    if isinstance(state, dict):
        warnings = state.get("db_warnings", [])
    else:
        warnings = getattr(state, "db_warnings", []) or []
    if warnings:
        return "update_dim_error_log"
    return END


# ---------------------------------------------------------------------------
# Re-decorated node shims (FR-006 / AC-6.1) for graph add_node.
# ---------------------------------------------------------------------------


@traced_node("ability_diagnose.aggregate_scores")
async def aggregate_scores(state: Any) -> Any:
    return await aggregate_scores_node(state)


@traced_node("ability_diagnose.compare_baseline")
async def compare_baseline(state: Any) -> Any:
    return await compare_baseline_node(state)


@traced_node("ability_diagnose.generate_insight")
async def generate_insight(state: Any) -> Any:
    return await generate_insight_node(state)


@traced_node("ability_diagnose.update_dim_db")
async def update_dim_db(state: Any) -> Any:
    return await update_dim_db_node(state)


@traced_node("ability_diagnose.update_history")
async def update_history(state: Any) -> Any:
    return await update_history_node(state)


@traced_node("ability_diagnose.update_activities")
async def update_activities(state: Any) -> Any:
    return await update_activities_node(state)


@traced_node("ability_diagnose.ws_push")
async def ws_push(state: Any) -> Any:
    return await ws_push_node(state)


@traced_node("ability_diagnose.update_dim_error_log")
async def update_dim_error_log(state: Any) -> Any:
    return await update_dim_error_log_node(state)


class AbilityDiagnoseGraph(BaseAgent):
    """LangGraph agent for post-interview ability diagnosis.

    Flow (US2):
        aggregate_scores → compare_baseline → generate_insight →
        update_dim_db → update_history → update_activities → ws_push → END

    With ``update_dim_error_log`` as the conditional intermediate
    (AC-5.7) — routed to when any of the 4 update nodes appends a
    ``db_warnings`` entry.
    """

    async def build_graph(self) -> StateGraph:
        builder = StateGraph(AbilityDiagnoseState)

        # FR-003 / AC-3.4: all node names follow `{agent}.{role}_{action}`.
        builder.add_node("ability_diagnose.aggregate_scores", aggregate_scores)
        builder.add_node("ability_diagnose.compare_baseline", compare_baseline)
        builder.add_node("ability_diagnose.generate_insight", generate_insight)
        builder.add_node("ability_diagnose.update_dim_db", update_dim_db)
        builder.add_node("ability_diagnose.update_history", update_history)
        builder.add_node("ability_diagnose.update_activities", update_activities)
        builder.add_node("ability_diagnose.ws_push", ws_push)
        builder.add_node("ability_diagnose.update_dim_error_log", update_dim_error_log)

        builder.set_entry_point("ability_diagnose.aggregate_scores")
        builder.add_edge("ability_diagnose.aggregate_scores", "ability_diagnose.compare_baseline")
        builder.add_edge("ability_diagnose.compare_baseline", "ability_diagnose.generate_insight")
        builder.add_edge("ability_diagnose.generate_insight", "ability_diagnose.update_dim_db")

        # AC-5.7: each update_dim_* node uses add_conditional_edges so a
        # failure routes through update_dim_error_log before continuing.
        builder.add_conditional_edges(
            "ability_diagnose.update_dim_db",
            _route_after_update_dim_db,
            {
                "update_dim_error_log": "ability_diagnose.update_dim_error_log",
                "update_history": "ability_diagnose.update_history",
            },
        )
        builder.add_conditional_edges(
            "ability_diagnose.update_dim_error_log",
            _route_after_update_dim_error_log,
            {
                "update_history": "ability_diagnose.update_history",
                "update_activities": "ability_diagnose.update_activities",
                "ws_push": "ability_diagnose.ws_push",
                END: END,
            },
        )
        builder.add_conditional_edges(
            "ability_diagnose.update_history",
            _route_after_update_history,
            {
                "update_dim_error_log": "ability_diagnose.update_dim_error_log",
                "update_activities": "ability_diagnose.update_activities",
            },
        )
        builder.add_conditional_edges(
            "ability_diagnose.update_activities",
            _route_after_update_activities,
            {
                "update_dim_error_log": "ability_diagnose.update_dim_error_log",
                "ws_push": "ability_diagnose.ws_push",
            },
        )
        builder.add_conditional_edges(
            "ability_diagnose.ws_push",
            _route_after_ws_push,
            {
                "update_dim_error_log": "ability_diagnose.update_dim_error_log",
                END: END,
            },
        )

        checkpointer = await get_checkpointer()
        # REQ-042 US-1 FR-002 — recursion_limit from per-agent config.
        # ability_diagnose uses PlannerStateConfiguration (researcher-like pattern).
        from app.agents.utils.loop_termination import PlannerStateConfiguration

        return builder.compile(
            checkpointer=checkpointer,
            recursion_limit=PlannerStateConfiguration().recursion_limit,
        )

    async def run(self, user_id: str, session_id: str) -> dict[str, Any]:
        """Execute the full ability diagnosis pipeline.

        023 US4 (FR-011): ``ainvoke`` is wrapped with the shared
        ``retry_graph_op`` helper (``state_first=True`` because
        ``ainvoke(state, config)`` puts config in the second position).
        A transient checkpointer drop (e.g. ARQ worker idle reconnect)
        triggers a force-rebuild + retry instead of failing the job.
        """
        thread_id = f"diag-{session_id}"
        initial_state: dict[str, Any] = {
            "user_id": user_id,
            "session_id": session_id,
            "thread_id": thread_id,
            "db_warnings": [],
        }
        config = await get_graph_config(thread_id)
        return await retry_graph_op(
            self.build_graph,
            config,
            "ainvoke",
            initial_state,
            state_first=True,
        )


_ability_diagnose_graph: AbilityDiagnoseGraph | None = None


def get_ability_diagnose_graph() -> AbilityDiagnoseGraph:
    global _ability_diagnose_graph
    if _ability_diagnose_graph is None:
        _ability_diagnose_graph = AbilityDiagnoseGraph()
    return _ability_diagnose_graph


__all__ = [
    "AbilityDiagnoseGraph",
    "_route_after_update_dim_db",
    "_route_after_update_dim_error_log",
    "_route_after_update_history",
    "_route_after_update_activities",
    "_route_after_ws_push",
    "get_ability_diagnose_graph",
]