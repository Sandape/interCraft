"""REQ-042 US-1 FR-001 + FR-002 + FR-004 — Loop termination utilities.

This module centralises per-agent ``Configuration`` (max_iterations +
recursion_limit) and the ``MaxIterationsReached`` exception that the
interview / error_coach / planner / researcher / general_coach agents
share.

Design notes
------------
* ``Configuration`` is a Pydantic ``BaseModel`` (REQ-040 US-1 pattern) so
  it composes with the rest of the agent's ``RunnableConfig`` cleanly
  while keeping plain-dict access (``config["max_iterations"]``) for
  LangGraph's ``add_node`` kwargs.
* ``MaxIterationsReached`` **inherits ``RuntimeError``** (L041-005) so
  REQ-040 AC-4.6's ``pytest.raises(RuntimeError)`` guard in
  ``retry_graph_op`` continues to observe it as a runtime failure
  rather than a structured error.
* ``iteration_count_reducer`` is a plain add reducer (not
  ``override_reducer``): iteration_count is monotonic per graph
  invocation; resetting to 0 is the responsibility of the graph caller
  on a fresh ``ainvoke`` call.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# FR-001 — Configuration.max_iterations (5 per-agent subclasses)
# ---------------------------------------------------------------------------


class Configuration(BaseModel):
    """Generic agent loop configuration.

    ``max_iterations`` is the soft cap; ``recursion_limit`` is the
    hard LangGraph cap passed to ``builder.compile(..., recursion_limit=...)``.
    The soft cap is checked at the iteration_guard node; the hard cap
    surfaces as ``langgraph.errors.GraphRecursionError`` which is
    caught at the graph.ainvoke level and written to ``state.error``.
    """

    max_iterations: int = Field(
        default=10,
        description="Soft per-invocation iteration cap. iteration_guard raises MaxIterationsReached when reached.",
    )
    recursion_limit: int = Field(
        default=25,
        description="Hard LangGraph recursion_limit passed to builder.compile().",
    )


class InterviewStateConfiguration(Configuration):
    """Interview agent (M12). max_iterations=5 to bound one session."""

    max_iterations: int = 5
    recursion_limit: int = 30


class ErrorCoachStateConfiguration(Configuration):
    """Error coach agent (M17). max_iterations=10 (3 rounds × 3 retries)."""

    max_iterations: int = 10
    recursion_limit: int = 20


class PlannerStateConfiguration(Configuration):
    """Planner agent. max_iterations=6 — plan refinement + 1 replan."""

    max_iterations: int = 6
    recursion_limit: int = 25


class ResearcherStateConfiguration(Configuration):
    """Researcher agent (M013). 10 search calls + compress cycles."""

    max_iterations: int = 10
    recursion_limit: int = 25


class GeneralCoachStateConfiguration(Configuration):
    """General coach agent (M19). Generic conversation, 10 turns."""

    max_iterations: int = 10
    recursion_limit: int = 25


# ---------------------------------------------------------------------------
# FR-001 — iteration_count reducer (add semantics)
# ---------------------------------------------------------------------------


def iteration_count_reducer(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    """Monotonic add reducer for ``iteration_count``.

    The reducer receives two partial state updates from LangGraph and
    returns a single delta. ``a`` is the existing value (defaults to 0
    on the first call) and ``b`` is the new contribution. Sum semantics
    keep the counter monotonically increasing within a single graph
    invocation.
    """
    return {"iteration_count": a.get("iteration_count", 0) + b.get("iteration_count", 0)}


# ---------------------------------------------------------------------------
# FR-004 — MaxIterationsReached exception (RuntimeError subclass per L041-005)
# ---------------------------------------------------------------------------


class MaxIterationsReached(RuntimeError):
    """Raised when ``iteration_count >= Configuration.max_iterations``.

    Per L041-005 this inherits ``RuntimeError`` (NOT ``Exception``) so
    REQ-040 AC-4.6's ``except RuntimeError`` in ``retry_graph_op``
    continues to observe it as a runtime failure. Inheriting ``Exception``
    would bypass the ``pytest.raises(RuntimeError)`` guards and break the
    dual-track contract.
    """

    def __init__(self, agent_name: str, limit: int, actual: int) -> None:
        self.agent_name = agent_name
        self.limit = limit
        self.actual = actual
        super().__init__(
            f"Max iterations reached in {agent_name}: {actual}/{limit}"
        )


__all__ = [
    "Configuration",
    "ErrorCoachStateConfiguration",
    "GeneralCoachStateConfiguration",
    "InterviewStateConfiguration",
    "MaxIterationsReached",
    "PlannerStateConfiguration",
    "ResearcherStateConfiguration",
    "iteration_count_reducer",
]
