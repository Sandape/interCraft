"""Routing math for the A2A framework (REQ-031 US1, T008).

Pure functions (no DB, no LangGraph, no async) — unit-testable in
isolation. The cycle-detection and depth-cap semantics follow spec
FR-007:

> The framework MUST enforce a delegation depth cap (e.g., 3 levels)
> with cycle detection.

Errors are typed and carry context for log attrs:

- :class:`CycleDetectedError` includes ``parent_agent`` and ``child_agent``.
- :class:`DepthExceededError` includes ``depth`` and ``max_depth``.
"""
from __future__ import annotations

from typing import Any

import structlog

from app.agents.a2a.schemas import AgentDefinition, RoutingDecision

logger = structlog.get_logger("agents.a2a.routing")


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class A2ARoutingError(Exception):
    """Base class for routing-time errors. Carries context attrs for logs."""


class CycleDetectedError(A2ARoutingError):
    """Raised when an agent would delegate to itself / an ancestor.

    Spec FR-007: "What happens with circular delegation (A → B → A)?
    → Cycle detection blocks it; an error is logged; the delegation is rejected."
    """

    def __init__(self, parent_agent: str, child_agent: str, visited: list[str]) -> None:
        self.parent_agent = parent_agent
        self.child_agent = child_agent
        self.visited = list(visited)
        super().__init__(
            f"Cycle detected: would route from {parent_agent!r} to "
            f"{child_agent!r} but {child_agent!r} is already in visited "
            f"path {visited!r}"
        )


class DepthExceededError(A2ARoutingError):
    """Raised when delegation depth would exceed the configured cap."""

    def __init__(self, depth: int, max_depth: int, parent_agent: str, child_agent: str) -> None:
        self.depth = depth
        self.max_depth = max_depth
        self.parent_agent = parent_agent
        self.child_agent = child_agent
        super().__init__(
            f"Delegation depth exceeded: {parent_agent!r} → {child_agent!r} "
            f"at depth {depth} (max_depth={max_depth})"
        )


class UnknownAgentError(A2ARoutingError):
    """Raised when the routing decision points to an agent not in the registry."""

    def __init__(self, agent_name: str, available: list[str]) -> None:
        self.agent_name = agent_name
        self.available = list(available)
        super().__init__(
            f"Unknown agent {agent_name!r}; available: {sorted(available)}"
        )


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

def check_cycle(visited: list[str], next_agent: str) -> None:
    """Block re-entry into any agent on the current visited path.

    Raises :class:`CycleDetectedError` when ``next_agent`` appears in
    ``visited``. Pure function — caller is responsible for mutating
    ``visited`` to add the new agent after the check passes.
    """
    if next_agent in visited:
        # The parent is the agent immediately preceding the cycle in
        # the visited path. If next_agent appears at index i, then
        # visited[i-1] is its parent (or the supervisor sentinel if
        # i == 0). This makes log attrs point to the edge that closed
        # the cycle, not to the duplicate entry itself.
        cycle_idx = visited.index(next_agent)
        parent = visited[cycle_idx - 1] if cycle_idx > 0 else "__supervisor__"
        raise CycleDetectedError(parent_agent=parent, child_agent=next_agent, visited=visited)


def enforce_depth(depth: int, max_depth: int, parent_agent: str, child_agent: str) -> None:
    """Block delegation beyond ``max_depth``.

    ``depth`` is the *current* delegation depth (entry node = 0). We
    raise when ``depth >= max_depth`` because the next hop would land
    at ``depth + 1`` which is past the cap.
    """
    if depth >= max_depth:
        raise DepthExceededError(
            depth=depth, max_depth=max_depth, parent_agent=parent_agent, child_agent=child_agent
        )


def _resolve_agent_names(agents: list[AgentDefinition]) -> set[str]:
    return {a.name for a in agents}


# ---------------------------------------------------------------------------
# Decide
# ---------------------------------------------------------------------------

def decide(
    state: dict[str, Any],
    agents: list[AgentDefinition],
    visited: list[str],
    depth: int,
    routing_fn: Any,
    max_depth: int,
    enable_cycle_detection: bool,
) -> RoutingDecision:
    """Apply cycle + depth checks to the routing function's decision.

    Parameters
    ----------
    state:
        LangGraph state dict (read-only).
    agents:
        Registered :class:`AgentDefinition` list — used to validate
        the routing decision's ``next_agent``.
    visited:
        Path of agent names visited so far (will include the current
        parent). The router appends the current agent before calling
        so ``visited[-1]`` is the parent.
    depth:
        Current delegation depth (entry = 0).
    routing_fn:
        Callable ``(state) -> RoutingDecision``. We invoke it once.
    max_depth:
        From :class:`~app.agents.a2a.schemas.SupervisorConfig`.
    enable_cycle_detection:
        When ``False``, cycle check is skipped (useful for tiny
        single-agent graphs that loop indefinitely).

    Returns
    -------
    RoutingDecision
        The routing function's decision, with ``depth`` updated to
        reflect the *next* hop (``depth + 1``).

    Raises
    ------
    CycleDetectedError, DepthExceededError, UnknownAgentError
    """
    available = _resolve_agent_names(agents)

    decision = routing_fn(state)

    # Validate the decision shape — neither name nor None is allowed to be empty.
    if decision.next_agent is not None and decision.next_agent == "":
        raise UnknownAgentError(agent_name="", available=sorted(available))

    parent = visited[-1] if visited else "__supervisor__"

    if decision.next_agent is None:
        # End of graph — emit decision with current depth for observability.
        logger.info(
            "a2a.routing_decision",
            parent=parent,
            next_agent="END",
            reason=decision.reason,
            depth=depth,
        )
        return RoutingDecision(next_agent=None, reason=decision.reason, depth=depth)

    # Depth + cycle checks before the agent is invoked.
    if enable_cycle_detection:
        check_cycle(visited, decision.next_agent)

    # Depth cap is enforced on the *current* depth; the next hop is depth+1.
    enforce_depth(depth, max_depth, parent, decision.next_agent)

    if decision.next_agent not in available:
        raise UnknownAgentError(agent_name=decision.next_agent, available=sorted(available))

    logger.info(
        "a2a.routing_decision",
        parent=parent,
        next_agent=decision.next_agent,
        reason=decision.reason,
        depth=depth + 1,
    )
    return RoutingDecision(
        next_agent=decision.next_agent,
        reason=decision.reason,
        depth=depth + 1,
    )


__all__ = [
    "A2ARoutingError",
    "CycleDetectedError",
    "DepthExceededError",
    "UnknownAgentError",
    "check_cycle",
    "decide",
    "enforce_depth",
]