"""REQ-042 US-1 FR-003 + FR-004 — iteration_guard node + GraphRecursionError handler.

The ``iteration_guard_node`` is a per-agent soft-cap check that runs
*before* the LLM step and raises ``MaxIterationsReached`` when the
graph has cycled more than ``Configuration.max_iterations`` times.

Per L041-004 the node is decorated with ``@node_error_handler`` so a
naive throw of the RuntimeError family (``MaxIterationsReached``
inherits ``RuntimeError`` per L041-005) still routes through the
shared failure envelope to ``state["error"]`` rather than crashing
the graph.

The ``catch_graph_recursion_error`` wrapper at the ``graph.ainvoke``
boundary (FR-004) is a sibling layer that converts LangGraph's
``GraphRecursionError`` (the hard ``recursion_limit``) into the same
``state["error"]`` shape with ``category="graph_recursion"``.
"""
from __future__ import annotations

from typing import Any

from app.agents.utils.node_error_handler import node_error_handler
from app.agents.utils.node_error import NodeError
from app.agents.utils.loop_termination import (
    Configuration,
    MaxIterationsReached,
)


# ---------------------------------------------------------------------------
# iteration_guard_node — per-agent soft cap (Layer 1 of 3-layer defence)
# ---------------------------------------------------------------------------


@node_error_handler(fallback_strategy="hard_fail")
async def iteration_guard_node(state: Any, *, agent_name: str = "interview") -> dict[str, Any]:
    """Raise ``MaxIterationsReached`` when iteration_count >= max_iterations.

    Args:
        state: graph state (dict or Pydantic v2 model).
        agent_name: which agent's configuration to use. The default
            ``"interview"`` matches the dominant call site; other agents
            pass their own name explicitly to pick up the right default.

    Returns:
        ``{"iteration_count": N+1}`` partial state delta when the cap
        has not been reached. Raises ``MaxIterationsReached`` (a
        ``RuntimeError``) when the cap is hit; the surrounding
        ``@node_error_handler(fallback_strategy="hard_fail")`` allows
        the exception to propagate so the graph router / API layer can
        branch on it.
    """
    config_cls = _CONFIG_BY_AGENT.get(agent_name, Configuration)
    config = config_cls()
    max_iter = config.max_iterations

    # Dual-form state read (per 040 + 041 dual-guard pattern).
    if isinstance(state, dict):
        iteration_count = int(state.get("iteration_count", 0) or 0)
    else:
        iteration_count = int(getattr(state, "iteration_count", 0) or 0)

    if iteration_count >= max_iter:
        raise MaxIterationsReached(
            agent_name=agent_name,
            limit=max_iter,
            actual=iteration_count,
        )

    return {"iteration_count": iteration_count + 1}


_CONFIG_BY_AGENT: dict[str, type[Configuration]] = {}


def _register_agent_config(agent_name: str, config_cls: type[Configuration]) -> None:
    """Register a per-agent configuration class (called once at import time)."""
    _CONFIG_BY_AGENT[agent_name] = config_cls


# Auto-register the 5 agent configurations at module import.
def _bootstrap_agent_configs() -> None:
    from app.agents.utils.loop_termination import (
        ErrorCoachStateConfiguration,
        GeneralCoachStateConfiguration,
        InterviewStateConfiguration,
        PlannerStateConfiguration,
        ResearcherStateConfiguration,
    )

    _register_agent_config("interview", InterviewStateConfiguration)
    _register_agent_config("error_coach", ErrorCoachStateConfiguration)
    _register_agent_config("planner", PlannerStateConfiguration)
    _register_agent_config("researcher", ResearcherStateConfiguration)
    _register_agent_config("general_coach", GeneralCoachStateConfiguration)


_bootstrap_agent_configs()


# ---------------------------------------------------------------------------
# catch_graph_recursion_error — sibling wrapper for graph.ainvoke boundary
# ---------------------------------------------------------------------------


async def catch_graph_recursion_error(
    state: Any,
    *,
    agent_name: str,
    coro: Any,
) -> tuple[Any, dict[str, Any] | None]:
    """Run a graph.ainvoke coroutine and convert ``GraphRecursionError`` to state.error.

    Usage::

        state, error = await catch_graph_recursion_error(
            state, agent_name="interview", coro=graph.ainvoke(state, config)
        )
        return state

    Returns:
        ``(state, error_dict)`` where ``error_dict`` is ``None`` on
        success or a serialised ``NodeError``-shaped dict with
        ``category="graph_recursion"`` on ``GraphRecursionError``.
    """
    try:
        result = await coro
        return result, None
    except Exception as exc:  # noqa: BLE001 — boundary catch
        from langgraph.errors import GraphRecursionError

        if isinstance(exc, GraphRecursionError):
            error = NodeError(
                category="graph_recursion",  # type: ignore[arg-type]
                node_name=agent_name,
                cause=str(exc),
            )
            error_dict = error.model_dump()
            # Also write to state.error so the API layer can serialise.
            if isinstance(state, dict):
                state["error"] = error_dict
            else:
                try:
                    setattr(state, "error", error_dict)
                except Exception:
                    pass
            return state, error_dict
        raise


__all__ = [
    "catch_graph_recursion_error",
    "iteration_guard_node",
]
