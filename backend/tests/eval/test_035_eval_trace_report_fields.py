from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.eval.golden_loader import GoldenCase
from app.eval.report import render_json_report
from app.eval.runner import CaseResult, EvalReport, EvalRunner


def _case() -> GoldenCase:
    return GoldenCase(
        case_id="req035_case",
        node="interview.score",
        label="REQ-035 trace linked case",
        source="promoted",
        input_state={
            "trace_id": "trace_req035",
            "llm_call_id": "llm_req035",
            "badcase_id": "badcase_req035",
            "usage": {
                "prompt_tokens": 120,
                "completion_tokens": 30,
                "estimated_cost": 0.0045,
                "latency_ms": 640,
            },
            "regression_delta": -0.12,
        },
        llm_response='{"score": 8, "feedback": "候选人回答完整。"}',
        expected_score_range=None,
        expected_contains=[],
    )


@pytest.mark.asyncio
async def test_eval_runner_links_case_to_trace_llm_badcase_and_usage(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = EvalRunner(cases=[], mode="mock")

    async def fake_invoke(_case: GoldenCase):
        return {"score_dimensions": {"task_success": 0.8, "privacy_leakage": 1.0}}

    monkeypatch.setattr(runner, "_invoke_node", fake_invoke)

    result = await runner.run_case(_case())

    assert result.trace_id == "trace_req035"
    assert result.llm_call_id == "llm_req035"
    assert result.badcase_id == "badcase_req035"
    assert result.score_dimensions["task_success"] == 0.8
    assert result.score_dimensions["chinese_fidelity"] >= 0.0
    assert result.regression_delta == -0.12
    assert result.prompt_tokens == 120
    assert result.completion_tokens == 30
    assert result.estimated_cost == 0.0045
    assert result.latency_ms == 640


def test_eval_report_json_exposes_req035_debug_fields() -> None:
    result = CaseResult(
        case_id="req035_case",
        node="interview.score",
        passed=False,
        metrics={},
        actual_output={},
        failure_reasons=["regression"],
        trace_id="trace_req035",
        llm_call_id="llm_req035",
        badcase_id="badcase_req035",
        score_dimensions={"task_success": 0.8},
        regression_delta=-0.12,
        prompt_tokens=120,
        completion_tokens=30,
        estimated_cost=0.0045,
        latency_ms=640,
    )
    report = EvalReport(
        timestamp=datetime.now(UTC).isoformat(),
        git_sha="abc123",
        model="mock",
        total_cases=1,
        passed_cases=0,
        failed_cases=1,
        skipped_cases=0,
        case_results=[result],
        run_id=uuid4(),
    )

    body = render_json_report(report)
    row = body["case_results"][0]

    assert row["trace_id"] == "trace_req035"
    assert row["llm_call_id"] == "llm_req035"
    assert row["badcase_id"] == "badcase_req035"
    assert row["score_dimensions"] == {"task_success": 0.8}
    assert row["regression_delta"] == -0.12
    assert row["total_tokens"] == 150
    assert body["total_tokens"] == 150
    assert body["estimated_cost"] == 0.0045
    assert body["avg_latency_ms"] == 640
