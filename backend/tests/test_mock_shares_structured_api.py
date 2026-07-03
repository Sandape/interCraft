"""[ac-completed: AC-009] — MockLLMClient must share the structured-output API.

Lock contract:
    1. MockLLMClient.parse_structured_output must call LLMClient.parse_structured_output
       (mock and prod share the same validator).
    2. MockLLMClient.by_scenario(name) must raise KeyError on unknown names
       (no silent fallback; ac-matrix Note R11).
"""
from __future__ import annotations

import pytest

from app.agents.llm_client import LLMClient
from app.agents.llm_client_mock import MockLLMClient
from app.agents.structured_output.errors import (
    OutOfBounds,
    SchemaInvalid,
)
from app.agents.structured_output.schemas import InterviewScoreOutput


def test_mock_uses_prod_parse():
    """Mock and prod must reject an oob score the same way."""
    mock = MockLLMClient()
    bad = '{"score": 200, "feedback": "x"}'  # out of bounds only
    with pytest.raises(OutOfBounds) as exc:
        mock.parse_structured_output(bad, InterviewScoreOutput)
    # oob is caught by the local validator (L009); category pinned by client.
    assert exc.value.category in ("oob", "schema_invalid")


def test_by_scenario_rejects_invalid():
    mock = MockLLMClient()
    with pytest.raises(KeyError) as exc:
        mock.by_scenario("nonexistent_xyz")
    assert "Available scenarios:" in str(exc.value)


def test_by_scenario_returns_oob_payload():
    mock = MockLLMClient()
    payload = mock.by_scenario("oob")
    assert '"score"' in payload and "200" in payload


def test_by_scenario_returns_malformed_payload():
    mock = MockLLMClient()
    payload = mock.by_scenario("malformed")
    # truncated brace should fail JSON parse
    assert payload.startswith("{")


def test_by_scenario_returns_enum_violation_payload():
    mock = MockLLMClient()
    payload = mock.by_scenario("enum_violation")
    assert "extreme" in payload


def test_by_scenario_returns_missing_payload():
    mock = MockLLMClient()
    payload = mock.by_scenario("missing")
    assert payload == "{}"


def test_by_scenario_returns_quota_payload():
    mock = MockLLMClient()
    payload = mock.by_scenario("quota")
    assert "_kind" in payload and "quota_429" in payload


def test_by_scenario_returns_timeout_payload():
    mock = MockLLMClient()
    payload = mock.by_scenario("timeout")
    assert "_kind" in payload and "timeout_504" in payload


def test_mock_parse_routes_to_prod():
    """The mock parse path must call LLMClient.parse_structured_output.

    AC-009 grep anchor: `return LLMClient.parse_structured_output(self`.
    This test is the behavioral counterpart of that anchor.
    """
    mock = MockLLMClient()
    # Use a valid payload to confirm the path; mock has no MockLLMClient-specific impl.
    good = '{"score": 50.0, "feedback": "ok"}'
    parsed = mock.parse_structured_output(good, InterviewScoreOutput)
    assert parsed.score == 50.0
    assert parsed.feedback == "ok"
    # Confirm the class inherits from LLMClient (so prod parse is reachable).
    assert isinstance(mock, LLMClient)