"""REQ-038 US2 — mock registration compliance tests."""
from __future__ import annotations

from unittest import mock

import pytest
from pydantic import BaseModel

from app.agents.llm_client_mock import MockLLMClient
from app.agents.structured_output.client import with_structured_output
from app.agents.structured_output.errors import StructuredOutputError
from app.agents.structured_output.schemas import (
    ErrorCoachEvalOutput,
    InterviewIntakeOutput,
    InterviewScoreOutput,
)


def test_mock_returns_valid_payload_for_compliant_node() -> None:
    mock_client = MockLLMClient()
    content = '{"next_question": "Tell me about your last project", "topic": "intro", "difficulty": "medium"}'

    with mock.patch(
        "app.agents.structured_output.client.parse_structured_output",
        wraps=mock_client.parse_structured_output,
    ) as parse_spy:
        result = with_structured_output(node_id="interview.intake", content=content)

    assert parse_spy.call_count >= 1
    assert isinstance(result, BaseModel)
    assert isinstance(result, InterviewIntakeOutput)
    assert result.next_question == "Tell me about your last project"


@pytest.mark.parametrize(
    ("scenario", "schema", "expected_category"),
    [
        ("malformed", InterviewIntakeOutput, "parse_fail"),
        ("missing", InterviewIntakeOutput, "schema_invalid"),
        ("enum_violation", ErrorCoachEvalOutput, "schema_invalid"),
        ("oob", InterviewScoreOutput, "oob"),
        ("quota", InterviewIntakeOutput, "quota"),
        ("timeout", InterviewIntakeOutput, "timeout"),
    ],
)
def test_mock_triggers_failure_for_non_compliant_node(
    scenario: str,
    schema: type[BaseModel],
    expected_category: str,
) -> None:
    mock_client = MockLLMClient()
    content = mock_client.by_scenario(scenario)

    with pytest.raises(StructuredOutputError) as exc:
        mock_client.parse_structured_output(content, schema)

    assert exc.value.category == expected_category


def test_unregistered_node_raises_keyerror() -> None:
    with pytest.raises(KeyError) as exc:
        with_structured_output(
            node_id="test.unsigned_node",
            content='{"next_question": "x", "topic": "intro", "difficulty": "medium"}',
        )

    message = str(exc.value)
    assert "Unknown structured node" in message
    assert "test.unsigned_node" in message
    assert "Available:" in message
