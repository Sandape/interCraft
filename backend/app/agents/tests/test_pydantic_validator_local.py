"""[ac-completed: AC-010] — local Pydantic validator must catch oob inputs.

Per L009 (DeepSeek JSON mode ≠ schema adherence), the production path
must validate *locally* — never trust the model to emit well-formed data.

The fixture we exercise here is `mock_llm_oob.json::{"score": 200}`.
Both endpoints (`{"score": 200.0}` and `{"score": -1.0}`) must trigger
StructuredOutputError with category in {`oob`, `schema_invalid`}.
"""
from __future__ import annotations

import json

import pytest

from app.agents.llm_client import LLMClient
from app.agents.structured_output.errors import StructuredOutputError
from app.agents.structured_output.schemas import (
    InterviewIntakeOutput,
    InterviewScoreOutput,
)


@pytest.mark.parametrize(
    "schema_name, raw_json",
    [
        ("InterviewScoreOutput", {"score": 200.0, "feedback": "x"}),  # oob high
        ("InterviewScoreOutput", {"score": -1.0, "feedback": "x"}),   # oob low
        ("InterviewScoreOutput", {"score": 99999, "feedback": "x"}),
        ("InterviewScoreOutput", {"score": -100, "feedback": "x"}),
    ],
)
def test_oob_caught(schema_name: str, raw_json: dict):
    """Real LLMClient path on oob input must raise StructuredOutputError.

    oob caught by local validator; got category=oob (preferred) or schema_invalid.
    """
    client = LLMClient()
    schema = InterviewScoreOutput if schema_name == "InterviewScoreOutput" else InterviewIntakeOutput
    try:
        client.parse_structured_output(json.dumps(raw_json), schema)
    except StructuredOutputError as exc:
        # oob caught by local validator; got category=oob (preferred) or schema_invalid.
        assert exc.category in ("oob", "schema_invalid"), (
            f"oob caught by local validator; got category={exc.category}"
        )
    else:
        pytest.fail("Should have raised StructuredOutputError for oob input")


def test_valid_score_accepted():
    """Sanity: a valid score passes the local validator."""
    client = LLMClient()
    out = client.parse_structured_output(
        '{"score": 50.0, "feedback": "ok"}',
        InterviewScoreOutput,
    )
    assert out.score == 50.0
    assert out.feedback == "ok"


def test_missing_field_caught():
    """missing field on InterviewScoreOutput raises schema_invalid."""
    client = LLMClient()
    with pytest.raises(StructuredOutputError) as exc:
        client.parse_structured_output('{"score": 50.0}', InterviewScoreOutput)
    assert exc.value.category in ("schema_invalid", "oob")


def test_enum_violation_caught():
    """Literal-field violation raises schema_invalid."""
    client = LLMClient()
    payload = (
        '{"next_question": "Tell me about yourself", '
        '"topic": "intro", "difficulty": "impossible"}'
    )
    with pytest.raises(StructuredOutputError) as exc:
        client.parse_structured_output(payload, InterviewIntakeOutput)
    assert exc.value.category == "schema_invalid"


def test_malformed_caught():
    """Non-JSON content raises parse_fail."""
    client = LLMClient()
    with pytest.raises(StructuredOutputError) as exc:
        client.parse_structured_output("{ not json", InterviewScoreOutput)
    assert exc.value.category == "parse_fail"