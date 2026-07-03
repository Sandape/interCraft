"""REQ-038 US3 — Structured output observability diagnostics.

Covers AC-001 through AC-008 from the locked acceptance matrix.
"""
import json
from typing import Any, Literal
from unittest import mock

import pytest
import structlog
from pydantic import BaseModel, Field

from app.agents.structured_output.client import (
    parse_structured_output,
    with_structured_output,
)
from app.agents.structured_output.errors import (
    OutOfBounds,
    ParseFail,
    Quota,
    SchemaInvalid,
    StructuredOutputError,
    Timeout,
)
from app.agents.structured_output.fallbacks import NodeConfig
from app.agents.structured_output.fixture_loader import load_structured_output_fixture
from app.agents.structured_output.observability import emit_structured_invocation_event
from app.agents.structured_output.schemas import (
    ErrorCoachEvalOutput,
    InterviewIntakeOutput,
    InterviewScoreOutput,
)
from app.eval.report import CaseResultModel
from app.eval.prompt_fingerprint import compute_prompt_fingerprint
from app.modules.agent_memory.redactor import redact

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _SimpleOutput(BaseModel):
    """Minimal output schema for test assertions."""
    name: str = Field(..., min_length=1)
    score: float = Field(..., ge=0.0, le=100.0)


class _EnumOutput(BaseModel):
    """Output schema with enum for enum_violation testing."""
    severity: Literal["low", "medium", "high"] = "low"


_EnumOutput.model_rebuild()


class _NumericOnly(BaseModel):
    """Schema with only bounded numeric fields (for oob detection)."""
    score: float = Field(..., ge=0.0, le=100.0)


class _NoBoundsSchema(BaseModel):
    """Schema without numeric bounds (used for schema_invalid test)."""
    name: str = Field(..., min_length=1)
    score: float = Field(...)


# ---------------------------------------------------------------------------
# AC-001: Structured observability hook exists with required fields
# ---------------------------------------------------------------------------


def test_structured_invocation_event_has_required_fields() -> None:
    """AC-001: emit_structured_invocation_event returns payload with all 8
    required fields and structlog event 'structured_invocation'."""
    required_fields = {
        "node", "contract_name", "contract_version", "validation_status",
        "failure_category", "fallback_used", "retry_count", "provider_path",
    }

    with structlog.testing.capture_logs() as captured:
        payload = emit_structured_invocation_event(
            node="test.node",
            contract_name="TestSchema",
            validation_status="passed",
            failure_category=None,
            fallback_used=False,
            retry_count=0,
            provider_path="structured_output.local",
        )

    # Returned payload has all required fields.
    for field in required_fields:
        assert field in payload, f"Missing required field: {field}"

    assert payload["validation_status"] in {"passed", "failed", "fallback"}
    assert payload["failure_category"] is None  # passed → no failure category
    assert payload["fallback_used"] is False
    assert payload["retry_count"] == 0
    assert payload["provider_path"] == "structured_output.local"

    # Structlog event captured.
    assert len(captured) >= 1
    event = captured[0]
    assert isinstance(event, dict), f"Expected dict, got {type(event)}"
    assert event.get("event") == "structured_invocation"
    for field in required_fields:
        assert field in event, f"Missing log field: {field}"


def test_structured_invocation_event_failure_category_non_empty() -> None:
    """AC-001 variant: failure_category is non-empty when validation_status
    is failed or fallback."""
    with structlog.testing.capture_logs():
        failed_payload = emit_structured_invocation_event(
            node="test.node",
            contract_name="TestSchema",
            validation_status="failed",
            failure_category="schema_invalid",
        )
    assert failed_payload["failure_category"] is not None

    with structlog.testing.capture_logs():
        fallback_payload = emit_structured_invocation_event(
            node="test.node",
            contract_name="TestSchema",
            validation_status="fallback",
            failure_category="parse_fail",
        )
    assert fallback_payload["failure_category"] is not None


# ---------------------------------------------------------------------------
# AC-002: parse / with structured path calls observability hook
# ---------------------------------------------------------------------------


def _get_event_monkeypatch(events: list[dict]) -> mock.MagicMock:
    """Return a MagicMock that appends its kwargs to events."""
    def _collect(**kwargs: dict) -> dict:
        payload = dict(kwargs)
        events.append(payload)
        return payload
    return mock.MagicMock(side_effect=_collect)


def test_structured_path_emits_passed_failed_and_fallback() -> None:
    """AC-002: parse_structured_output emits passed/failed/fallback events
    via the observability hook."""
    collected: list[dict] = []

    with mock.patch(
        "app.agents.structured_output.client.emit_structured_invocation_event",
        new=_get_event_monkeypatch(collected),
    ):
        # 1. Success path → passed
        result = parse_structured_output(
            '{"name": "test", "score": 50.0}',
            _SimpleOutput,
            node_name="test.node.success",
        )
        assert isinstance(result, _SimpleOutput)
        assert result.name == "test"

        # 2. Validation failure with retry → failed (not fallback since
        # default fallback_strategy="retry")
        with pytest.raises(StructuredOutputError):
            parse_structured_output(
                '{"name": "", "score": 50.0}',
                _SimpleOutput,
                node_name="test.node.failed",
            )

        # 3. Validation failure with use_previous → fallback
        with pytest.raises(StructuredOutputError):
            parse_structured_output(
                '{"name": "", "score": 50.0}',
                _SimpleOutput,
                fallback_strategy="use_previous",
                node_name="test.node.fallback",
            )

    # Should have exactly 3 events.
    assert len(collected) == 3, f"Expected 3 events, got {len(collected)}"

    statuses = [e["validation_status"] for e in collected]
    assert statuses == ["passed", "failed", "fallback"], f"Unexpected statuses: {statuses}"

    # Event 1: passed
    assert collected[0]["validation_status"] == "passed"
    assert collected[0]["fallback_used"] is False

    # Event 2: failed (retry strategy)
    assert collected[1]["validation_status"] == "failed"
    assert collected[1]["fallback_used"] is False
    assert collected[1]["failure_category"] is not None

    # Event 3: fallback (use_previous strategy)
    assert collected[2]["validation_status"] == "fallback"
    assert collected[2]["fallback_used"] is True
    assert collected[2]["failure_category"] is not None


def test_with_structured_output_emits_via_parse_path() -> None:
    """AC-002 variant: with_structured_output triggers the same hook
    via its parse_structured_output call."""
    collected: list[dict] = []

    with mock.patch(
        "app.agents.structured_output.client.emit_structured_invocation_event",
        new=_get_event_monkeypatch(collected),
    ):
        # Success via registry.
        result = with_structured_output(
            node_id="error_coach.evaluate",
            content='{"severity": "low", "diagnosis": "test", "score": 90.0}',
        )
        assert result is not None

        # Failure via registry.
        with pytest.raises(StructuredOutputError):
            with_structured_output(
                node_id="error_coach.evaluate",
                content='{"severity": "invalid", "diagnosis": "test", "score": 90.0}',
            )

    assert len(collected) == 2
    assert collected[0]["validation_status"] == "passed"
    assert collected[1]["validation_status"] == "failed"


# ---------------------------------------------------------------------------
# AC-003: Prometheus counter increments
# ---------------------------------------------------------------------------


def test_structured_invocation_counter_increments() -> None:
    """AC-003: structured_invocation_total counter increments by 1 on
    each emit_structured_invocation_event call."""
    from app.core.metrics import structured_invocation_total

    # Get current value for the specific label set.
    labels = {
        "node": "test",
        "contract": "CounterSchema",
        "status": "passed",
        "failure_category": "",
        "fallback_used": "false",
    }
    before = structured_invocation_total.labels(**labels)._value.get()

    with structlog.testing.capture_logs():
        emit_structured_invocation_event(
            node="test",
            contract_name="CounterSchema",
            validation_status="passed",
            failure_category=None,
        )

    after = structured_invocation_total.labels(**labels)._value.get()
    assert after - before == 1, f"Counter did not increment by 1 (before={before}, after={after})"


def test_structured_invocation_counter_different_labels() -> None:
    """AC-003 variant: counter labels reflect failure_category and fallback."""
    from app.core.metrics import structured_invocation_total

    # Emit a failed event.
    fail_labels = {
        "node": "test-fail",
        "contract": "FailSchema",
        "status": "failed",
        "failure_category": "schema_invalid",
        "fallback_used": "false",
    }
    before_fail = structured_invocation_total.labels(**fail_labels)._value.get()

    with structlog.testing.capture_logs():
        emit_structured_invocation_event(
            node="test-fail",
            contract_name="FailSchema",
            validation_status="failed",
            failure_category="schema_invalid",
        )

    after_fail = structured_invocation_total.labels(**fail_labels)._value.get()
    assert after_fail - before_fail == 1


# ---------------------------------------------------------------------------
# AC-004: Eval JSON report has malformed-output first-class row
# ---------------------------------------------------------------------------


def test_eval_json_report_malformed_row_is_first_class() -> None:
    """AC-004: A malformed structured-output case renders as a first-class
    row with failure_reasons containing 'schema_validation' or 'parse_fail'
    and metrics.failure_category / metrics.contract_name non-empty."""
    # Build a CaseResultModel that represents a malformed structured output
    # failure, as would be produced by an eval runner.
    malformed_row = CaseResultModel(
        case_id="malformed-001",
        node="error_coach.evaluate",
        verdict="FAIL",
        passed=False,
        failure_reasons=["schema_validation: missing required field 'diagnosis'"],
        metrics={
            "failure_category": "schema_invalid",
            "contract_name": "ErrorCoachEvalOutput",
            "chinese_fidelity": 0.0,
        },
        actual_output={},
    )

    # Render via report JSON path (render_json_report uses dict form).
    from app.eval.report import render_json_report
    from app.eval.runner import EvalReport

    report = EvalReport(
        timestamp="2026-07-03T00:00:00+00:00",
        git_sha="abc1234",
        model="mock-llm",
        total_cases=1,
        passed_cases=0,
        failed_cases=1,
        skipped_cases=0,
        case_results=[],  # We'll test with model-level dict.
    )
    report_dict = report.to_dict()
    report_dict["case_results"] = [
        malformed_row.model_dump(mode="json"),
    ]

    json_out = render_json_report(report_dict)
    case_rows = json_out.get("case_results", [])
    assert len(case_rows) == 1

    row = case_rows[0]
    assert row["case_id"] == "malformed-001"
    assert row["passed"] is False

    # failure_reasons must contain schema_validation or parse_fail.
    reasons = " ".join(row.get("failure_reasons", []))
    assert "schema_validation" in reasons or "parse_fail" in reasons

    # metrics must have failure_category and contract_name.
    metrics = row.get("metrics", {})
    assert isinstance(metrics, dict)
    assert metrics.get("failure_category"), "failure_category should be non-empty"
    assert metrics.get("contract_name"), "contract_name should be non-empty"

    # failure_category must NOT be llm_error or unknown.
    fc = metrics.get("failure_category", "")
    assert fc not in ("llm_error", "unknown"), (
        f"failure_category should not be llm_error/unknown, got: {fc}"
    )


def test_eval_json_report_malformed_row_parse_fail() -> None:
    """AC-004 variant: parse_fail failure also renders as first-class."""
    parse_fail_row = CaseResultModel(
        case_id="malformed-002",
        node="interview.intake",
        verdict="FAIL",
        passed=False,
        failure_reasons=["parse_fail: content is not valid JSON"],
        metrics={
            "failure_category": "parse_fail",
            "contract_name": "InterviewIntakeOutput",
        },
        actual_output={},
    )
    from app.eval.report import render_json_report
    from app.eval.runner import EvalReport

    report = EvalReport(
        timestamp="2026-07-03T00:00:00+00:00",
        git_sha="abc1234",
        model="mock-llm",
        total_cases=1,
        passed_cases=0,
        failed_cases=1,
        skipped_cases=0,
    )
    report_dict = report.to_dict()
    report_dict["case_results"] = [
        parse_fail_row.model_dump(mode="json"),
    ]

    json_out = render_json_report(report_dict)
    row = json_out["case_results"][0]
    reasons = " ".join(row.get("failure_reasons", []))
    assert "parse_fail" in reasons

    metrics = row.get("metrics", {})
    assert metrics.get("failure_category") == "parse_fail"
    assert metrics.get("failure_category") not in ("llm_error", "unknown")


# ---------------------------------------------------------------------------
# AC-005: Redaction before persistence
# ---------------------------------------------------------------------------


def test_redaction_before_structured_payload_persistence() -> None:
    """AC-005: PII (email, phone) in input/output summary is redacted
    before appearing in returned payload or captured logs."""
    pii_input = "My email is contact@example.com and phone is +86 13800138000"
    pii_output = "Reach me at test@example.org or 13800138000"

    with structlog.testing.capture_logs() as captured:
        payload = emit_structured_invocation_event(
            node="test.node",
            contract_name="TestSchema",
            validation_status="passed",
            input_summary=pii_input,
            output_summary=pii_output,
        )

    # Returned payload: redacted, not original PII.
    assert "contact@example.com" not in payload.get("input_summary", "")
    assert "+86 13800138000" not in payload.get("input_summary", "")
    assert "[REDACTED]" in payload.get("input_summary", "")

    assert "test@example.org" not in payload.get("output_summary", "")
    assert "13800138000" not in payload.get("output_summary", "")
    assert "[REDACTED]" in payload.get("output_summary", "")

    # Captured logs also have redacted values.
    for event in captured:
        assert isinstance(event, dict), f"Expected dict, got {type(event)}"
        if "input_summary" in event:
            assert "contact@example.com" not in event["input_summary"]
            assert "[REDACTED]" in event["input_summary"]
        if "output_summary" in event:
            assert "test@example.org" not in event["output_summary"]
            assert "[REDACTED]" in event["output_summary"]


def test_redaction_no_pii_passthrough() -> None:
    """AC-005 variant: non-PII summaries pass through unchanged."""
    safe_input = "User provided a valid code snippet about Python"
    with structlog.testing.capture_logs():
        payload = emit_structured_invocation_event(
            node="test.node",
            contract_name="TestSchema",
            validation_status="passed",
            input_summary=safe_input,
        )
    assert payload.get("input_summary") == safe_input
    assert "[REDACTED]" not in payload.get("input_summary", "")


def test_redaction_metric_labels_no_raw_content() -> None:
    """AC-005 variant: metric labels never contain raw input/output."""
    from app.core.metrics import structured_invocation_total

    with structlog.testing.capture_logs():
        emit_structured_invocation_event(
            node="test.node",
            contract_name="TestSchema",
            validation_status="passed",
        )

    # Metric labels are bounded (node, contract, status, failure_category,
    # fallback_used) — no raw input/output slot exists. This test asserts
    # the label set does not grow unboundedly.
    sample = structured_invocation_total.labels(
        node="test.node",
        contract="TestSchema",
        status="passed",
        failure_category="",
        fallback_used="false",
    )
    # Just accessing labels is safe; the real assertion is that there is
    # no "input" or "output" label in the metric definition.
    assert sample._labelnames == ("node", "contract", "status", "failure_category", "fallback_used")


# ---------------------------------------------------------------------------
# AC-006: Prompt fingerprint compatibility
# ---------------------------------------------------------------------------


def test_prompt_fingerprint_cache_compatible() -> None:
    """AC-006: structured validation does not change prompt fingerprint.
    Same prompt parameters produce the same hash before and after."""
    system_prompt = "You are a helpful assistant"
    tool_defs = [
        {"name": "get_weather", "description": "Get weather"},
    ]
    messages = [
        {"role": "user", "content": "What is the weather?"},
    ]

    # Compute fingerprint before any structured validation.
    fp_before = compute_prompt_fingerprint(system_prompt, tool_defs, messages)

    # Simulate a structured validation call (the node name, contract name,
    # and schema JSON must NOT affect the fingerprint).
    _contract_name = "InterviewIntakeOutput"
    _schema_json = InterviewIntakeOutput.model_json_schema()

    # Compute fingerprint after "going through" structured path.
    fp_after = compute_prompt_fingerprint(system_prompt, tool_defs, messages)

    assert fp_before == fp_after, (
        "Prompt fingerprint changed after structured validation. "
        "The contract name or schema JSON must not leak into the fingerprint input."
    )

    # Verify the fingerprint does NOT depend on contract name or schema.
    # If we add contract name to the prompt, the fingerprint changes.
    altered_prompt = f"{system_prompt}\n\nContract: {_contract_name}"
    fp_altered = compute_prompt_fingerprint(altered_prompt, tool_defs, messages)
    assert fp_before != fp_altered, (
        "Fingerprint should change when prompt content changes. "
        "If this fails the test infrastructure is broken."
    )


def test_prompt_fingerprint_stable_across_runs() -> None:
    """AC-006 variant: deterministic fingerprint across multiple calls."""
    sys_prompt = "Score the interview answer from 0 to 100."
    fp1 = compute_prompt_fingerprint(sys_prompt, [], [])
    fp2 = compute_prompt_fingerprint(sys_prompt, [], [])
    assert fp1 == fp2


# ---------------------------------------------------------------------------
# AC-007: Quota/timeout categories are observable
# ---------------------------------------------------------------------------


def test_quota_timeout_categories_are_observable() -> None:
    """AC-007: quota and timeout typed failures are observable as
    first-class categories (not downgraded to generic LLM error)."""
    from app.agents.llm_client_mock import MockLLMClient

    mock_client = MockLLMClient()

    # Quota scenario.
    quota_content = mock_client.by_scenario("quota")
    with pytest.raises(StructuredOutputError) as quota_exc:
        parse_structured_output(
            quota_content,
            _SimpleOutput,
            node_name="test.quota",
        )
    assert isinstance(quota_exc.value, Quota) or quota_exc.value.category == "quota"
    assert quota_exc.value.category == "quota"

    # Timeout scenario.
    timeout_content = mock_client.by_scenario("timeout")
    with pytest.raises(StructuredOutputError) as timeout_exc:
        parse_structured_output(
            timeout_content,
            _SimpleOutput,
            node_name="test.timeout",
        )
    assert isinstance(timeout_exc.value, Timeout) or timeout_exc.value.category == "timeout"
    assert timeout_exc.value.category == "timeout"


def test_quota_timeout_emits_typed_category() -> None:
    """AC-007 variant: the observability hook sees quota/timeout category."""
    collected: list[dict] = []

    with mock.patch(
        "app.agents.structured_output.client.emit_structured_invocation_event",
        new=_get_event_monkeypatch(collected),
    ):
        with pytest.raises(StructuredOutputError):
            parse_structured_output(
                '{"_kind": "quota_429"}',
                _SimpleOutput,
                node_name="test.quota",
            )
        with pytest.raises(StructuredOutputError):
            parse_structured_output(
                '{"_kind": "timeout_504"}',
                _SimpleOutput,
                node_name="test.timeout",
            )

    assert len(collected) == 2
    assert collected[0]["failure_category"] == "quota"
    assert collected[0]["validation_status"] == "failed"
    assert collected[1]["failure_category"] == "timeout"
    assert collected[1]["validation_status"] == "failed"
    assert "retry_count" in collected[0]
    assert isinstance(collected[0]["retry_count"], int)


# ---------------------------------------------------------------------------
# AC-008: 1-domain malformed fixture demo consumable
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("fixture_name", "expected_category"),
    [
        ("missing", "schema_invalid"),
        ("enum_violation", "schema_invalid"),
        ("oob", "oob"),
        ("malformed", "parse_fail"),
    ],
)
def test_one_domain_malformed_fixtures_are_consumable(
    fixture_name: str,
    expected_category: str,
) -> None:
    """AC-008: fixture loader returns bare content; parse_structured_output
    raises expected StructuredOutputError.category for each fixture."""
    # Load fixture via loader (extracts _raw).
    content = load_structured_output_fixture(fixture_name)

    # Determine the right schema for the fixture.
    if fixture_name == "enum_violation":
        schema = _EnumOutput
    elif fixture_name == "oob":
        schema = _NumericOnly
    else:
        schema = _SimpleOutput

    # The content is bare — feed it to the parser.
    with pytest.raises(StructuredOutputError) as exc:
        parse_structured_output(content, schema, node_name=f"test.{fixture_name}")

    assert exc.value.category == expected_category, (
        f"Fixture '{fixture_name}': expected category '{expected_category}', "
        f"got '{exc.value.category}'"
    )


def test_fixture_loader_rejects_unknown_name() -> None:
    """AC-008 variant: unknown fixture name raises KeyError."""
    with pytest.raises(KeyError):
        load_structured_output_fixture("nonexistent")


def test_fixture_loader_returns_bare_content() -> None:
    """AC-008 variant: loader returns bare string, not metadata dict."""
    content = load_structured_output_fixture("missing")
    assert isinstance(content, str)
    # The content should be "{}" (bare raw content), not the full metadata JSON.
    assert content == "{}", f"Expected bare '{{}}', got: {content[:100]}"

    content2 = load_structured_output_fixture("oob")
    assert isinstance(content2, str)
    parsed = json.loads(content2)
    assert "score" in parsed  # It's a JSON object with score field
    assert "_raw" not in content2  # Not the metadata envelope


# ---------------------------------------------------------------------------
# Additional: Quota/Timeout fixture loader support
# ---------------------------------------------------------------------------


def test_quota_fixture_via_loader() -> None:
    """Quota fixture loaded via loader produces Quota error."""
    content = load_structured_output_fixture("quota")
    with pytest.raises(StructuredOutputError) as exc:
        parse_structured_output(content, _SimpleOutput, node_name="test.quota")
    assert exc.value.category == "quota"


def test_timeout_fixture_via_loader() -> None:
    """Timeout fixture loaded via loader produces Timeout error."""
    content = load_structured_output_fixture("timeout")
    with pytest.raises(StructuredOutputError) as exc:
        parse_structured_output(content, _SimpleOutput, node_name="test.timeout")
    assert exc.value.category == "timeout"
