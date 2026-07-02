"""REQ-038 US2 — A2A boundary output_schema enforcement tests."""
from __future__ import annotations

from unittest import mock

import pytest

from app.agents.a2a import AgentDefinition, RoutingDecision, Supervisor, SupervisorConfig
from app.agents.structured_output.errors import SchemaInvalid
from app.agents.structured_output.schemas import InterviewIntakeOutput


def _route_end(state: dict) -> RoutingDecision:
    return RoutingDecision(next_agent=None, reason="done")


def _supervisor(agent: AgentDefinition) -> Supervisor:
    return Supervisor(SupervisorConfig(agents=[agent], routing_fn=_route_end))


@pytest.fixture
def initial_state() -> dict:
    return {
        "thread_id": "thread-1",
        "request_id": "trace-1",
        "next_question": "original question",
        "topic": "original topic",
        "difficulty": "hard",
    }


@pytest.mark.asyncio
async def test_delegated_output_schema_violation_blocks_state_write_return_invalid(
    initial_state: dict,
) -> None:
    child = AgentDefinition(
        name="child_agent",
        role="structured child",
        output_schema=InterviewIntakeOutput,
    )
    supervisor = _supervisor(child)

    async def _handler(ctx: dict, state: dict) -> dict:
        return {"next_question": "", "topic": "intro", "difficulty": "medium"}

    supervisor.register_handler("child_agent", _handler)

    result, error_reason = await supervisor._delegate(  # noqa: SLF001
        agent=child,
        state=initial_state,
        parent="parent",
    )

    assert result is None
    assert error_reason is not None
    assert "schema_validation_failed" in error_reason
    assert initial_state["next_question"] == "original question"
    assert initial_state["topic"] == "original topic"
    assert initial_state["difficulty"] == "hard"


@pytest.mark.asyncio
async def test_delegated_output_schema_violation_blocks_state_write_handler_raises(
    initial_state: dict,
) -> None:
    child = AgentDefinition(
        name="child_agent",
        role="structured child",
        output_schema=InterviewIntakeOutput,
    )
    supervisor = _supervisor(child)

    async def _handler(ctx: dict, state: dict) -> dict:
        raise SchemaInvalid("schema_validation_failed: child refused malformed output")

    supervisor.register_handler("child_agent", _handler)

    result, error_reason = await supervisor._delegate(  # noqa: SLF001
        agent=child,
        state=initial_state,
        parent="parent",
    )

    assert result is None
    assert error_reason is not None
    assert "SchemaInvalid" in error_reason
    assert "schema_validation_failed" in error_reason
    assert initial_state["next_question"] == "original question"
    assert initial_state["topic"] == "original topic"
    assert initial_state["difficulty"] == "hard"


@pytest.mark.asyncio
async def test_delegated_output_schema_compliant_passes(initial_state: dict) -> None:
    child = AgentDefinition(
        name="child_agent",
        role="structured child",
        output_schema=InterviewIntakeOutput,
    )
    supervisor = _supervisor(child)

    expected = {
        "next_question": "What is your experience?",
        "topic": "intro",
        "difficulty": "medium",
    }

    async def _handler(ctx: dict, state: dict) -> dict:
        return dict(expected)

    supervisor.register_handler("child_agent", _handler)

    result, error_reason = await supervisor._delegate(  # noqa: SLF001
        agent=child,
        state=initial_state,
        parent="parent",
    )

    assert error_reason is None
    assert result == expected
    merged = {**initial_state, **(result or {})}
    assert merged["next_question"] == "What is your experience?"
    assert merged["topic"] == "intro"
    assert merged["difficulty"] == "medium"


@pytest.mark.asyncio
async def test_free_form_agent_bypasses_schema_enforcement(initial_state: dict) -> None:
    child = AgentDefinition(
        name="free_form_agent",
        role="free form child",
        output_schema=None,
    )
    supervisor = _supervisor(child)
    arbitrary = {"next_question": "", "unexpected": {"nested": True}}

    async def _handler(ctx: dict, state: dict) -> dict:
        return dict(arbitrary)

    supervisor.register_handler("free_form_agent", _handler)

    with mock.patch.object(InterviewIntakeOutput, "model_validate", wraps=InterviewIntakeOutput.model_validate) as validate_spy:
        result, error_reason = await supervisor._delegate(  # noqa: SLF001
            agent=child,
            state=initial_state,
            parent="parent",
        )

    assert validate_spy.call_count == 0
    assert error_reason is None
    assert result == arbitrary
    merged = {**initial_state, **(result or {})}
    assert merged["unexpected"] == {"nested": True}
