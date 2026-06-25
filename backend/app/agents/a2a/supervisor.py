"""Supervisor — compiles a LangGraph StateGraph from agent list + routing fn.

The Supervisor is the load-bearing builder of the A2A framework. It
takes a :class:`~app.agents.a2a.SupervisorConfig` and produces a
compiled :class:`langgraph.graph.StateGraph` that:

- has one node per :class:`~app.agents.a2a.AgentDefinition`
- inserts a hidden ``__supervisor_router__`` node that owns the
  ``add_conditional_edges`` mapping
- routes agent → router → next agent (or END) on each hop
- tracks delegation depth + visited path in state for cycle detection
- delegates to :class:`~app.agents.a2a.DelegationRunner` for timeout
  + retry + persistence
"""
from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable

from langgraph.graph import END, StateGraph

import structlog

from app.agents.a2a.delegation import DelegationRunner
from app.agents.a2a.repository import A2AMessageRepository
from app.agents.a2a.routing import (
    CycleDetectedError,
    DepthExceededError,
    UnknownAgentError,
    decide,
)
from app.agents.a2a.schemas import (
    AgentDefinition,
    RoutingDecision,
    SupervisorConfig,
)

logger = structlog.get_logger("agents.a2a.supervisor")

_SUPERVISOR_ROUTER_NODE = "__supervisor_router__"


class Supervisor:
    """Compiles and runs a Supervisor-routed LangGraph ``StateGraph``.

    The :class:`Supervisor` does not hold any per-invocation state
    itself — the graph compiled by :meth:`compile_state_graph` is a
    pure function of the config. Lifecycle is therefore:

    1. Construct ``Supervisor(config)`` once at module import (or per
       request when config is dynamic).
    2. Call ``supervisor.compile_state_graph(state_cls)`` to build a
       compiled graph; cache the result if the config is stable.
    3. Invoke the compiled graph via the standard LangGraph API
       (``graph.ainvoke``, ``graph.aupdate_state``, etc.).
    """

    def __init__(
        self,
        config: SupervisorConfig,
        *,
        delegation_runner: DelegationRunner | None = None,
    ) -> None:
        self._config = config
        self._agents_by_name: dict[str, AgentDefinition] = {a.name: a for a in config.agents}
        self._delegation_runner = delegation_runner or DelegationRunner()
        self._handler_registry: dict[
            str, Callable[[dict[str, Any], dict[str, Any]], Awaitable[dict[str, Any]]]
        ] = {}

    @property
    def config(self) -> SupervisorConfig:
        return self._config

    @property
    def agent_names(self) -> list[str]:
        return list(self._agents_by_name.keys())

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compile_state_graph(self, state_cls: Any) -> Any:
        """Build a compiled LangGraph ``StateGraph`` from the config.

        Parameters
        ----------
        state_cls:
            The TypedDict class that defines the graph's state shape.
            Must be a valid LangGraph state class (extends TypedDict).

        Returns
        -------
        langgraph.graph.StateGraph
            A compiled graph ready to be invoked. The compiled graph
            carries no shared state with the Supervisor itself — it
            can be re-compiled on demand.
        """
        builder = StateGraph(state_cls)
        # The Supervisor does not own a database session — the
        # DelegationRunner is constructed stateless. Callers that want
        # to persist A2AMessage rows should construct a Supervisor
        # with ``delegation_runner=DelegationRunner(repository=...)``
        # inside the graph's request-scoped context.
        for agent in self._config.agents:
            builder.add_node(agent.name, _make_agent_node(agent, self))

        builder.add_node(_SUPERVISOR_ROUTER_NODE, _make_router_node(self))

        # Entry point is the first registered agent — callers can
        # override via add_edge before compiling if a different entry
        # is desired.
        entry = self._config.agents[0].name
        builder.set_entry_point(entry)

        # Each agent → router → next agent (or END). The router node
        # returns a RoutingDecision that we read in the conditional
        # edges.
        for agent in self._config.agents:
            builder.add_edge(agent.name, _SUPERVISOR_ROUTER_NODE)

        route_map: dict[str, str] = {a.name: a.name for a in self._config.agents}
        route_map[END] = END
        # Note: the router returns the next agent's name from state;
        # we use a passthrough routing function that just reads the
        # field the router wrote into state.
        builder.add_conditional_edges(
            _SUPERVISOR_ROUTER_NODE,
            _read_next_agent,
            route_map,
        )

        return builder.compile()

    # ------------------------------------------------------------------
    # Internals (used by the compiled graph)
    # ------------------------------------------------------------------

    async def _delegate(
        self,
        *,
        agent: AgentDefinition,
        state: dict[str, Any],
        parent: str,
    ) -> tuple[dict[str, Any] | None, str | None]:
        """Run one agent's function via ``DelegationRunner``.

        Returns ``(result, None)`` on success and ``(None, error_reason)``
        on failure. The Supervisor's caller (the graph node wrapper)
        translates this into state updates.
        """
        thread_id = str(state.get("thread_id", "")) or "unknown"
        trace_id = str(state.get("request_id", "")) or thread_id
        context = _extract_context_for_agent(agent, state)

        async def _agent_fn(ctx: dict[str, Any]) -> dict[str, Any]:
            # The agent's function is constructed per-call from the
            # AgentDefinition. We dispatch by name to a registry of
            # async callables supplied via Supervisor construction.
            # (See ``Supervisor(..., agent_fn_registry=...)`` for the
            # production wiring.)
            handler = self._resolve_handler(agent)
            return await handler(ctx, state)

        timeout = agent.timeout_seconds or self._config.default_timeout_seconds

        record = await self._delegation_runner.run(
            parent=parent,
            child=agent.name,
            task=agent.role,
            context=context,
            agent_fn=_agent_fn,
            timeout_seconds=timeout,
            trace_id=trace_id,
            thread_id=thread_id,
            expected_output={
                "schema": agent.output_schema.__name__ if agent.output_schema else None,
            },
        )

        if record.status == "success" and record.result is not None:
            return record.result, None
        return None, record.error_reason or f"agent returned status={record.status}"

    def _resolve_handler(
        self, agent: AgentDefinition
    ) -> Callable[[dict[str, Any], dict[str, Any]], Awaitable[dict[str, Any]]]:
        """Return the user-supplied async callable for ``agent``.

        Raises :class:`UnknownAgentError` if no handler is registered
        for the agent name (defensive — should not happen because
        :meth:`compile_state_graph` only adds nodes for registered
        agents).
        """
        handler = self._handler_registry.get(agent.name)
        if handler is None:
            raise UnknownAgentError(
                agent_name=agent.name, available=list(self._handler_registry.keys())
            )
        return handler

    def register_handler(
        self,
        agent_name: str,
        handler: Callable[[dict[str, Any], dict[str, Any]], Awaitable[dict[str, Any]]],
    ) -> None:
        """Bind an async callable to an agent name.

        The ``Supervisor`` owns a per-instance handler registry that
        maps agent name → async callable. The graph compiled by
        :meth:`compile_state_graph` dispatches via this registry at
        runtime. If an agent fires without a registered handler, the
        dispatch raises :class:`UnknownAgentError`.
        """
        self._handler_registry[agent_name] = handler


# ---------------------------------------------------------------------------
# Module-level helpers (also re-bound per-Supervisor-instance for clarity)
# ---------------------------------------------------------------------------

def _extract_context_for_agent(agent: AgentDefinition, state: dict[str, Any]) -> dict[str, Any]:
    """Slice the state for the agent's ``input_schema`` (if any).

    For US1 we pass the whole state — schema validation is the
    agent's responsibility (the framework will validate the *output*
    on US4). When ``input_schema`` is provided, we still pass the
    full state so the agent can read everything it needs.
    """
    return dict(state)


def _read_next_agent(state: dict[str, Any]) -> str:
    """Read the router-written ``a2a_next_agent`` from state.

    The router writes the next agent's name (or ``END`` sentinel) to
    this field. LangGraph's ``add_conditional_edges`` then dispatches
    via the route_map.
    """
    return state.get("a2a_next_agent", END)


# ---------------------------------------------------------------------------
# Graph node factories
# ---------------------------------------------------------------------------

def _make_router_node(supervisor: Supervisor) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """Build the hidden router node function.

    The router reads the current ``a2a_visited`` + ``a2a_depth``,
    invokes the user's routing function via
    :func:`app.agents.a2a.routing.decide`, and writes
    ``a2a_next_agent`` + the updated bookkeeping into state.
    """
    config = supervisor.config

    async def _router_node(state: dict[str, Any]) -> dict[str, Any]:
        visited = list(state.get("a2a_visited", []))
        depth = int(state.get("a2a_depth", 0))

        # Find the parent — the last entry in visited, or
        # the supervisor sentinel if visited is empty (entry hop).
        parent = visited[-1] if visited else config.parent_agent

        try:
            decision: RoutingDecision = decide(
                state=state,
                agents=config.agents,
                visited=visited,
                depth=depth,
                routing_fn=config.routing_fn,
                max_depth=config.max_delegation_depth,
                enable_cycle_detection=config.enable_cycle_detection,
            )
        except (CycleDetectedError, DepthExceededError) as exc:
            logger.error(
                "a2a.routing_rejected",
                parent=exc.parent_agent if hasattr(exc, "parent_agent") else parent,
                error=type(exc).__name__,
                reason=str(exc),
                visited=visited,
                depth=depth,
            )
            # End the graph on routing rejection — the agent will
            # still return whatever it produced; the Supervisor
            # cannot continue safely.
            return {
                "a2a_next_agent": END,
                "a2a_error": str(exc),
            }

        next_name = decision.next_agent if decision.next_agent is not None else END

        # The router node also updates bookkeeping for the next hop.
        return {
            "a2a_next_agent": next_name,
            "a2a_visited": visited,  # unchanged — child appended by agent node
            "a2a_depth": decision.depth,
        }

    return _router_node


def _make_agent_node(
    agent: AgentDefinition, supervisor: Supervisor
) -> Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]:
    """Build one agent's node function.

    The node function:

    1. Appends the agent's name to ``a2a_visited`` (so the next
       router hop sees the updated path).
    2. Calls :meth:`Supervisor._delegate` which routes through
       :class:`~app.agents.a2a.DelegationRunner`.
    3. Translates the result into a state update.
    """
    async def _agent_node(state: dict[str, Any]) -> dict[str, Any]:
        visited = list(state.get("a2a_visited", []))
        parent = visited[-1] if visited else supervisor.config.parent_agent

        result, error_reason = await supervisor._delegate(
            agent=agent, state=state, parent=parent
        )

        # Append this agent to the visited path so the router's
        # cycle check sees the current hop.
        visited_with_self = visited + [agent.name]

        update: dict[str, Any] = {
            "a2a_visited": visited_with_self,
            "a2a_error": error_reason,
        }
        if result is not None:
            # The agent's result is shallow-merged into state. This
            # matches the LangGraph convention (return a dict of the
            # fields you want to update).
            update.update(result)
        return update

    return _agent_node


__all__ = ["Supervisor", "_SUPERVISOR_ROUTER_NODE"]