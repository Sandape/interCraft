from __future__ import annotations

from uuid import uuid4

from app.eval.report import normalize_req045_report
from app.eval.runner import CaseResult, EvalReport
from app.modules.telemetry_contracts.schemas import VersionContext


def _report() -> EvalReport:
    run_id = uuid4()
    return EvalReport(
        timestamp="2026-07-05T01:03:00+00:00",
        git_sha="abc123",
        model="mock-llm",
        total_cases=1,
        passed_cases=1,
        failed_cases=0,
        skipped_cases=0,
        case_results=[
            CaseResult(
                case_id="interview-score-regression-001",
                node="interview.score_llm",
                passed=True,
                metrics={
                    "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
                    "span_id": "00f067aa0ba902b7",
                    "artifact_ref": "docs/evidence/run/cases/case.json",
                },
                run_id=run_id,
            )
        ],
        run_id=run_id,
        started_at="2026-07-05T01:00:00+00:00",
        finished_at="2026-07-05T01:03:00+00:00",
        source_revision="abc123",
        branch="codex/045",
        environment="CI",
        version_context=VersionContext.unknown(environment="CI"),
        aggregate_pass_rate=1.0,
        known_regression_recall=1.0,
        prompt_fingerprint="pf_test",
        rubric_version="rv_test",
    )


def test_req045_eval_report_uses_camel_case_contract() -> None:
    payload = normalize_req045_report(
        _report(),
        suite="golden",
        dataset_version="golden-v2",
        artifacts={"json": "report.json", "markdown": "report.md"},
        langsmith_export_status="DISABLED",
    )

    assert payload["schemaVersion"] == "045.eval-report.v1"
    assert payload["runId"]
    assert payload["sourceRevision"] == "abc123"
    assert payload["datasetVersion"] == "golden-v2"
    assert payload["aggregatePassRate"] == 1.0
    assert payload["langsmithExportStatus"] == "DISABLED"
    assert payload["artifacts"] == {"json": "report.json", "markdown": "report.md"}


def test_req045_case_results_have_required_links_or_unavailable() -> None:
    payload = normalize_req045_report(_report(), suite="golden", dataset_version="golden-v2")
    case = payload["caseResults"][0]

    assert case["runId"] == payload["runId"]
    assert case["lifecycle"] == "GOLDEN"
    assert case["graph"] == "interview"
    assert case["node"] == "interview.score_llm"
    assert case["traceId"] == "4bf92f3577b34da6a3ce929d0e0e4736"
    assert case["spanId"] == "00f067aa0ba902b7"
    assert case["artifactRef"] == "docs/evidence/run/cases/case.json"
    assert case["langsmithUrl"] == "unavailable"


def test_req045_missing_links_are_explicit_unavailable() -> None:
    report = _report()
    report.case_results[0].metrics = {}

    case = normalize_req045_report(report, suite="golden", dataset_version="golden-v2")[
        "caseResults"
    ][0]

    assert case["traceId"] == "unavailable"
    assert case["spanId"] == "unavailable"
    assert case["artifactRef"] == "unavailable"
    assert case["langsmithUrl"] == "unavailable"
