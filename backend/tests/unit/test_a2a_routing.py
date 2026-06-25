"""Unit tests for A2A routing math (T010)."""
from __future__ import annotations

import pytest

from app.agents.a2a.routing import (
    CycleDetectedError,
    DepthExceededError,
    UnknownAgentError,
    check_cycle,
    decide,
    enforce_depth,
)
from app.agents.a2a.schemas import AgentDefinition, RoutingDecision, SupervisorConfig


def _agents(*names: str) -> list[AgentDefinition]:
    return [AgentDefinition(name=n, role=f"role for {n}") for n in names]


def _stub_routing_fn(target: str | None):
    def _fn(state):
        return RoutingDecision(next_agent=target, reason=f"target={target}")
    return _fn


# ---------------------------------------------------------------------------
# check_cycle
# ---------------------------------------------------------------------------

class TestCheckCycle:
    def test_unique_path_ok(self) -> None:
        check_cycle(["a", "b", "c"], "d")  # no raise

    def test_repeat_raises(self) -> None:
        """Routing to 'a' when 'a' is already at index 0 → cycle."""
        with pytest.raises(CycleDetectedError) as exc_info:
            check_cycle(["a", "b"], "a")
        assert exc_info.value.child_agent == "a"
        # parent is visited[index_of_a - 1] = supervisor sentinel.
        assert exc_info.value.parent_agent == "__supervisor__"

    def test_repeat_midpath_parent_is_predecessor(self) -> None:
        """If 'b' is at index 1, parent of re-visit 'b' is visited[0] = 'a'."""
        with pytest.raises(CycleDetectedError) as exc_info:
            check_cycle(["a", "b", "c"], "b")
        assert exc_info.value.parent_agent == "a"

    def test_empty_visited_allows_first(self) -> None:
        check_cycle([], "a")  # no raise

    def test_first_visit_does_not_raise(self) -> None:
        check_cycle(["hint_ladder"], "recommendation")  # no raise


# ---------------------------------------------------------------------------
# enforce_depth
# ---------------------------------------------------------------------------

class TestEnforceDepth:
    def test_under_max_ok(self) -> None:
        enforce_depth(0, 3, "__supervisor__", "a")
        enforce_depth(2, 3, "a", "b")

    def test_at_max_raises(self) -> None:
        with pytest.raises(DepthExceededError) as exc_info:
            enforce_depth(3, 3, "a", "b")
        assert exc_info.value.depth == 3
        assert exc_info.value.max_depth == 3
        assert exc_info.value.parent_agent == "a"
        assert exc_info.value.child_agent == "b"

    def test_above_max_raises(self) -> None:
        with pytest.raises(DepthExceededError):
            enforce_depth(5, 3, "a", "b")


# ---------------------------------------------------------------------------
# decide
# ---------------------------------------------------------------------------

class TestDecide:
    def test_next_agent_none_returns_end(self) -> None:
        decision = decide(
            state={},
            agents=_agents("a", "b"),
            visited=["a"],
            depth=0,
            routing_fn=_stub_routing_fn(None),
            max_depth=3,
            enable_cycle_detection=True,
        )
        assert decision.next_agent is None
        assert decision.depth == 0  # depth unchanged on END

    def test_routing_fn_invoked(self) -> None:
        decision = decide(
            state={},
            agents=_agents("a", "b"),
            visited=[],
            depth=0,
            routing_fn=_stub_routing_fn("b"),
            max_depth=3,
            enable_cycle_detection=True,
        )
        assert decision.next_agent == "b"
        assert decision.depth == 1

    def test_unknown_agent_raises(self) -> None:
        with pytest.raises(UnknownAgentError) as exc_info:
            decide(
                state={},
                agents=_agents("a", "b"),
                visited=[],
                depth=0,
                routing_fn=_stub_routing_fn("c"),
                max_depth=3,
                enable_cycle_detection=True,
            )
        assert exc_info.value.agent_name == "c"

    def test_cycle_check_before_target_validation(self) -> None:
        """Cycle check fires before UnknownAgentError for repeat entries."""
        with pytest.raises(CycleDetectedError):
            decide(
                state={},
                agents=_agents("a", "b", "c"),
                visited=["a", "b"],  # 'a' is already visited
                depth=0,
                routing_fn=_stub_routing_fn("a"),
                max_depth=3,
                enable_cycle_detection=True,
            )

    def test_depth_check_before_target_validation(self) -> None:
        with pytest.raises(DepthExceededError):
            decide(
                state={},
                agents=_agents("a", "b"),
                visited=[],
                depth=3,  # at max → raise before unknown check
                routing_fn=_stub_routing_fn("a"),
                max_depth=3,
                enable_cycle_detection=True,
            )

    def test_cycle_detection_disabled_skips_check(self) -> None:
        # Routing to "a" again — would normally raise cycle. With
        # detection disabled, the agent must still be known.
        decision = decide(
            state={},
            agents=_agents("a", "b"),
            visited=["a"],
            depth=0,
            routing_fn=_stub_routing_fn("a"),
            max_depth=3,
            enable_cycle_detection=False,
        )
        assert decision.next_agent == "a"

    def test_reason_preserved_from_routing_fn(self) -> None:
        def _fn(state):
            return RoutingDecision(next_agent="b", reason="custom")

        decision = decide(
            state={},
            agents=_agents("a", "b"),
            visited=[],
            depth=0,
            routing_fn=_fn,
            max_depth=3,
            enable_cycle_detection=True,
        )
        assert decision.reason == "custom"


# ---------------------------------------------------------------------------
# Smoke: SupervisorConfig can be built (compile happens at supervisor level)
# ---------------------------------------------------------------------------

class TestSupervisorConfigSmoke:
    def test_builds_with_decide(self) -> None:
        def _fn(state):
            return RoutingDecision(next_agent="b")

        cfg = SupervisorConfig(
            agents=_agents("a", "b"),
            routing_fn=_fn,
        )
        decision = decide(
            state={}, agents=cfg.agents, visited=[],
            depth=0, routing_fn=cfg.routing_fn,
            max_depth=cfg.max_delegation_depth,
            enable_cycle_detection=cfg.enable_cycle_detection,
        )
        assert decision.next_agent == "b"