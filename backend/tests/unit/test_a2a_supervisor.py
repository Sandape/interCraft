"""Unit tests for A2A Supervisor (compile_state_graph).

These tests verify the Supervisor builds a valid LangGraph StateGraph
without actually invoking any agents (no LLM calls, no DB).
"""
from __future__ import annotations

import pytest
from typing_extensions import TypedDict

from app.agents.a2a import (
    AgentDefinition,
    RoutingDecision,
    Supervisor,
    SupervisorConfig,
)


class _TestState(TypedDict, total=False):
    """Minimal state for Supervisor compile tests."""

    messages: list[dict]
    attempt_count: int
    correct_count: int
    a2a_visited: list[str]
    a2a_depth: int
    a2a_next_agent: str


def _two_agent_config() -> SupervisorConfig:
    """Build a 2-agent config: hint_ladder → (recommendation | END)."""

    def _route(state):
        if int(state.get("attempt_count", 0)) >= 3 and int(state.get("correct_count", 0)) == 0:
            return RoutingDecision(next_agent="recommendation", reason="stuck")
        return RoutingDecision(next_agent=None, reason="continue")

    return SupervisorConfig(
        agents=[
            AgentDefinition(name="hint_ladder", role="hint"),
            AgentDefinition(name="recommendation", role="recommend"),
        ],
        routing_fn=_route,
    )


class TestSupervisorCompile:
    def test_compiles_without_error(self) -> None:
        supervisor = Supervisor(_two_agent_config())
        graph = supervisor.compile_state_graph(_TestState)
        assert graph is not None

    def test_agent_names_property(self) -> None:
        supervisor = Supervisor(_two_agent_config())
        assert sorted(supervisor.agent_names) == ["hint_ladder", "recommendation"]

    def test_register_handler_then_compile(self) -> None:
        supervisor = Supervisor(_two_agent_config())

        async def _hint_handler(ctx: dict, state: dict) -> dict:
            return {"hint": "small"}

        async def _rec_handler(ctx: dict, state: dict) -> dict:
            return {"recommendations": []}

        supervisor.register_handler("hint_ladder", _hint_handler)
        supervisor.register_handler("recommendation", _rec_handler)
        # Compile and don't crash — handlers are wired at runtime.
        graph = supervisor.compile_state_graph(_TestState)
        assert graph is not None

    def test_handler_registry_defaults_empty(self) -> None:
        supervisor = Supervisor(_two_agent_config())
        assert supervisor._handler_registry == {}  # noqa: SLF001 — internal

    def test_compile_with_single_agent(self) -> None:
        def _route(state):
            return RoutingDecision(next_agent=None)

        cfg = SupervisorConfig(
            agents=[AgentDefinition(name="only", role="solo")],
            routing_fn=_route,
        )
        supervisor = Supervisor(cfg)
        graph = supervisor.compile_state_graph(_TestState)
        assert graph is not None


class TestSupervisorConfig:
    def test_default_timeout_seconds_inherited(self) -> None:
        cfg = _two_agent_config()
        # Default is 30s per spec FR-006.
        assert cfg.default_timeout_seconds == 30.0

    def test_max_delegation_depth_default(self) -> None:
        cfg = _two_agent_config()
        assert cfg.max_delegation_depth == 3

    def test_parent_agent_default(self) -> None:
        cfg = _two_agent_config()
        assert cfg.parent_agent == "__supervisor__"

    def test_cycle_detection_default_on(self) -> None:
        cfg = _two_agent_config()
        assert cfg.enable_cycle_detection is True