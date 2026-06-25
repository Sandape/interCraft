"""Unit tests for A2A framework schemas (T009)."""
from __future__ import annotations

from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

from app.agents.a2a.schemas import (
    A2AMessage,
    A2AMessageStatus,
    AgentDefinition,
    DelegationRecord,
    RoutingDecision,
    SupervisorConfig,
)


# ---------------------------------------------------------------------------
# AgentDefinition
# ---------------------------------------------------------------------------

class TestAgentDefinition:
    def test_minimal(self) -> None:
        a = AgentDefinition(name="hint_ladder", role="hint")
        assert a.name == "hint_ladder"
        assert a.timeout_seconds is None

    def test_name_required(self) -> None:
        with pytest.raises(ValidationError):
            AgentDefinition(role="hint")  # type: ignore[call-arg]

    def test_empty_name_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AgentDefinition(name="", role="hint")

    def test_double_underscore_name_rejected(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            AgentDefinition(name="__internal", role="hint")
        assert "reserved" in str(exc_info.value).lower()

    def test_input_output_schema_accepted(self) -> None:
        class In(BaseModel):
            x: int

        class Out(BaseModel):
            y: int

        a = AgentDefinition(name="a", role="r", input_schema=In, output_schema=Out)
        assert a.input_schema is In
        assert a.output_schema is Out

    def test_timeout_zero_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AgentDefinition(name="a", role="r", timeout_seconds=0.0)

    def test_timeout_negative_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AgentDefinition(name="a", role="r", timeout_seconds=-1.0)


# ---------------------------------------------------------------------------
# A2AMessage
# ---------------------------------------------------------------------------

class TestA2AMessage:
    def test_status_enum_validated(self) -> None:
        with pytest.raises(ValidationError):
            A2AMessage(
                trace_id="t",
                thread_id="th",
                parent_agent="p",
                child_agent="c",
                task="task",
                status="bogus",  # type: ignore[arg-type]
            )

    def test_default_status_is_pending(self) -> None:
        msg = A2AMessage(
            trace_id="t", thread_id="th",
            parent_agent="p", child_agent="c", task="task",
        )
        assert msg.status == A2AMessageStatus.PENDING

    def test_all_terminal_statuses_accepted(self) -> None:
        for s in ("pending", "success", "failed", "timeout"):
            msg = A2AMessage(
                trace_id="t", thread_id="th",
                parent_agent="p", child_agent="c", task="task",
                status=s,  # type: ignore[arg-type]
            )
            assert msg.status == s

    def test_retry_count_out_of_range_rejected(self) -> None:
        with pytest.raises(ValidationError):
            A2AMessage(
                trace_id="t", thread_id="th",
                parent_agent="p", child_agent="c", task="task",
                retry_count=10,
            )

    def test_result_optional(self) -> None:
        msg = A2AMessage(
            trace_id="t", thread_id="th",
            parent_agent="p", child_agent="c", task="task",
        )
        assert msg.result is None


# ---------------------------------------------------------------------------
# SupervisorConfig
# ---------------------------------------------------------------------------

class TestSupervisorConfig:
    def test_defaults(self) -> None:
        def _rf(state: dict[str, Any]) -> RoutingDecision:
            return RoutingDecision(next_agent=None)

        cfg = SupervisorConfig(agents=[AgentDefinition(name="a", role="r")], routing_fn=_rf)
        assert cfg.default_timeout_seconds == 30.0
        assert cfg.max_delegation_depth == 3
        assert cfg.enable_cycle_detection is True
        assert cfg.parent_agent == "__supervisor__"

    def test_duplicate_agent_names_rejected(self) -> None:
        def _rf(state: dict[str, Any]) -> RoutingDecision:
            return RoutingDecision(next_agent=None)

        with pytest.raises(ValidationError) as exc_info:
            SupervisorConfig(
                agents=[
                    AgentDefinition(name="a", role="r"),
                    AgentDefinition(name="a", role="r"),
                ],
                routing_fn=_rf,
            )
        assert "duplicate" in str(exc_info.value).lower()

    def test_empty_agents_rejected(self) -> None:
        def _rf(state: dict[str, Any]) -> RoutingDecision:
            return RoutingDecision(next_agent=None)

        with pytest.raises(ValidationError):
            SupervisorConfig(agents=[], routing_fn=_rf)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# RoutingDecision
# ---------------------------------------------------------------------------

class TestRoutingDecision:
    def test_next_agent_optional(self) -> None:
        rd = RoutingDecision(next_agent=None, reason="end")
        assert rd.next_agent is None

    def test_depth_default(self) -> None:
        rd = RoutingDecision(next_agent="hint_ladder")
        assert rd.depth == 0


# ---------------------------------------------------------------------------
# DelegationRecord
# ---------------------------------------------------------------------------

class TestDelegationRecord:
    def test_status_default(self) -> None:
        rec = DelegationRecord(parent="p", child="c", task="t")
        assert rec.status == A2AMessageStatus.PENDING

    def test_duration_default_zero(self) -> None:
        rec = DelegationRecord(parent="p", child="c", task="t")
        assert rec.duration_ms == 0