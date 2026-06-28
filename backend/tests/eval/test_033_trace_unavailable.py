"""REQ-033 US7 T123 — Trace-unavailable report tests.

Locks the contract from tasks.md US7:

> T123: Write failing trace-unavailable report tests in
> backend/tests/eval/test_033_trace_unavailable.py. Verify missing
> traces are explicit, not silent.

The eval report must NEVER silently omit a trace id. When the OTel
trace id is missing (no active span, init_tracing was never called,
or the recording layer was disabled), the report must render the
literal string ``"unavailable"`` in every trace column. This is a
US7 + T123 contract:

- trace_id (per-case) == "unavailable"
- trace_id (run-level / top-level) == "unavailable" or explicitly empty
- langsmith_url (per-case) == "unavailable" when LangSmith not enabled
  (US6 is deferred per user decision — LangSmith SDK is NOT installed;
  the contract degrades gracefully).
- The report never crashes when trace is missing.

TDD: assertions fail until T125 (report.py extension) + T127 (OTel
trace id extraction adapter) + T126 (TraceRunRef helpers) land.
"""
from __future__ import annotations

import re
from uuid import uuid4

import pytest

from app.eval.report import render_json_report, render_markdown_report
from app.eval.runner import CaseResult, EvalReport
from app.modules.telemetry_contracts.schemas import VersionContext


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------


def _make_case(
    case_id: str,
    passed: bool,
    metrics_extra: dict | None = None,
) -> CaseResult:
    metrics = {"chinese_fidelity": 0.95}
    if metrics_extra:
        metrics.update(metrics_extra)
    return CaseResult(
        case_id=case_id,
        node="interview.score",
        passed=passed,
        metrics=metrics,
        actual_output={"score": 9},
        failure_reasons=[] if passed else ["chinese_fidelity"],
        label=f"{case_id}",
        expected_fidelity_pass=True,
        run_id=None,
    )


def _build_empty_trace_report(failed_count: int = 1) -> EvalReport:
    """Build a report where every case has NO trace_id.

    This is the canonical "trace unavailable" scenario.
    """
    cases = [
        _make_case(case_id=f"untraced_{i}", passed=False) for i in range(failed_count)
    ]
    return EvalReport(
        timestamp="2026-06-29T00:00:00+00:00",
        git_sha="unknown",
        model="deepseek-v4-pro",
        total_cases=len(cases),
        passed_cases=0,
        failed_cases=len(cases),
        skipped_cases=0,
        per_node={},
        case_results=cases,
        run_id=uuid4(),
        started_at="2026-06-29T00:00:00+00:00",
        finished_at="2026-06-29T00:00:01+00:00",
        model_version="deepseek-v4-pro",
        version_context=VersionContext.unknown(environment="LOCAL"),
        aggregate_pass_rate=0.0,
        known_regression_recall=1.0,
        stale_case_count=0,
        source_revision="unknown",
        branch="unknown",
        prompt_fingerprint="unknown",
        rubric_version="unknown",
        environment="LOCAL",
    )


# ---------------------------------------------------------------------------
# Per-case trace_id = "unavailable"
# ---------------------------------------------------------------------------


class TestPerCaseTraceUnavailable:
    """When no OTel trace is active, every per-case row says 'unavailable'."""

    def test_json_per_case_trace_id_is_unavailable(self) -> None:
        report = _build_empty_trace_report(failed_count=3)
        out = render_json_report(report)
        for cr in out["case_results"]:
            assert cr.get("trace_id") == "unavailable", (
                f"case {cr['case_id']} must have trace_id == 'unavailable', "
                f"got {cr.get('trace_id')!r}"
            )

    def test_json_per_case_artifact_ref_is_unavailable(self) -> None:
        report = _build_empty_trace_report(failed_count=2)
        out = render_json_report(report)
        for cr in out["case_results"]:
            assert cr.get("artifact_ref") == "unavailable", (
                f"case {cr['case_id']} must have artifact_ref == 'unavailable', "
                f"got {cr.get('artifact_ref')!r}"
            )

    def test_json_per_case_langsmith_url_is_unavailable(self) -> None:
        """T123 + US6 deferred: LangSmith URL must be 'unavailable', never None."""
        report = _build_empty_trace_report(failed_count=2)
        out = render_json_report(report)
        for cr in out["case_results"]:
            ls_url = cr.get("langsmith_url")
            assert ls_url == "unavailable", (
                f"case {cr['case_id']} must have langsmith_url == 'unavailable' "
                f"when US6 deferred, got {ls_url!r}"
            )

    def test_json_per_case_trace_id_never_none(self) -> None:
        """T123 hard rule: never None, never empty string."""
        report = _build_empty_trace_report(failed_count=5)
        out = render_json_report(report)
        for cr in out["case_results"]:
            assert cr.get("trace_id") is not None
            assert cr.get("trace_id") != ""
            assert cr.get("trace_id") != "unknown"


# ---------------------------------------------------------------------------
# Markdown drilldown — trace unavailable rendering
# ---------------------------------------------------------------------------


class TestMarkdownTraceUnavailable:
    """Markdown drilldown table must show 'unavailable' explicitly."""

    def test_markdown_drilldown_shows_unavailable_for_all_untraced_cases(self) -> None:
        report = _build_empty_trace_report(failed_count=3)
        md = render_markdown_report(report)
        section = re.search(
            r"## Failed-case drilldown.*?(?=\n## |\Z)",
            md,
            flags=re.DOTALL,
        )
        assert section, "Failed-case drilldown section missing"
        section = section.group(0)
        # Every untraced case should have 'unavailable' in the trace column.
        for i in range(3):
            case_id = f"untraced_{i}"
            row_match = re.search(
                rf"\|\s*`?{case_id}`?\s*\|.*?\|\s*`?(unavailable)`?\s*\|",
                section,
            )
            assert row_match, (
                f"{case_id} row should render 'unavailable' in trace column — "
                f"section was:\n{section}"
            )

    def test_markdown_langsmith_url_says_unavailable(self) -> None:
        """T123 + US6 deferred: the debug identifiers section must say
        'trace unavailable' (or equivalent explicit unavailable marker)
        for the LangSmith URL when LangSmith is not configured."""
        report = _build_empty_trace_report(failed_count=1)
        md = render_markdown_report(report)
        # The debug identifiers section (US5 §4) carries the LangSmith URL.
        # When US6 is deferred, this line must read 'unavailable' explicitly.
        debug_section = re.search(
            r"## Debug identifiers.*?(?=\n## |\Z)",
            md,
            flags=re.DOTALL,
        )
        assert debug_section, "Debug identifiers section missing"
        debug = debug_section.group(0)
        # Must say 'unavailable' or 'trace unavailable' for the LangSmith line.
        assert "unavailable" in debug.lower(), (
            f"Debug identifiers section must mark LangSmith as unavailable — "
            f"got:\n{debug}"
        )


# ---------------------------------------------------------------------------
# No crash + graceful degradation
# ---------------------------------------------------------------------------


class TestGracefulDegradation:
    """The renderer must NOT crash when trace is unavailable (T123)."""

    def test_renderer_does_not_raise_on_no_trace(self) -> None:
        report = _build_empty_trace_report(failed_count=5)
        # Both renders must succeed.
        json_out = render_json_report(report)
        md = render_markdown_report(report)
        assert json_out["case_results"]
        assert "## Failed-case drilldown" in md

    def test_renderer_with_zero_failed_cases_does_not_crash(self) -> None:
        """Empty failed-case set: drilldown section says 'No failing cases.'"""
        cases = [
            _make_case(case_id="p_0", passed=True),
            _make_case(case_id="p_1", passed=True),
        ]
        report = EvalReport(
            timestamp="2026-06-29T00:00:00+00:00",
            git_sha="unknown",
            model="deepseek-v4-pro",
            total_cases=2,
            passed_cases=2,
            failed_cases=0,
            skipped_cases=0,
            per_node={},
            case_results=cases,
            run_id=uuid4(),
            started_at="2026-06-29T00:00:00+00:00",
            finished_at="2026-06-29T00:00:01+00:00",
            model_version="deepseek-v4-pro",
            version_context=VersionContext.unknown(environment="LOCAL"),
            aggregate_pass_rate=1.0,
            known_regression_recall=1.0,
            stale_case_count=0,
            source_revision="unknown",
            branch="unknown",
            prompt_fingerprint="unknown",
            rubric_version="unknown",
            environment="LOCAL",
        )
        md = render_markdown_report(report)
        # Even with zero failed cases, the drilldown section is rendered.
        assert "## Failed-case drilldown" in md
        # And it must say "No failing cases." (or equivalent) — not crash.
        assert "No failing cases" in md

    def test_partial_trace_some_cases_have_some_dont(self) -> None:
        """Mixed report: some cases have trace, some don't. Untraced must say
        'unavailable'; traced must keep the real hex id."""
        cases = [
            _make_case(
                case_id="traced_0",
                passed=False,
                metrics_extra={"trace_id": "0123456789abcdef0123456789abcdef"},
            ),
            _make_case(case_id="untraced_0", passed=False),
            _make_case(
                case_id="traced_1",
                passed=False,
                metrics_extra={"trace_id": "fedcba9876543210fedcba9876543210"},
            ),
        ]
        report = EvalReport(
            timestamp="2026-06-29T00:00:00+00:00",
            git_sha="unknown",
            model="deepseek-v4-pro",
            total_cases=3,
            passed_cases=0,
            failed_cases=3,
            skipped_cases=0,
            per_node={},
            case_results=cases,
            run_id=uuid4(),
            started_at="2026-06-29T00:00:00+00:00",
            finished_at="2026-06-29T00:00:01+00:00",
            model_version="deepseek-v4-pro",
            version_context=VersionContext.unknown(environment="LOCAL"),
            aggregate_pass_rate=0.0,
            known_regression_recall=1.0,
            stale_case_count=0,
            source_revision="unknown",
            branch="unknown",
            prompt_fingerprint="unknown",
            rubric_version="unknown",
            environment="LOCAL",
        )
        out = render_json_report(report)
        for cr in out["case_results"]:
            if cr["case_id"] == "traced_0":
                assert cr["trace_id"] == "0123456789abcdef0123456789abcdef"
            elif cr["case_id"] == "traced_1":
                assert cr["trace_id"] == "fedcba9876543210fedcba9876543210"
            elif cr["case_id"] == "untraced_0":
                assert cr["trace_id"] == "unavailable"
            else:  # pragma: no cover
                pytest.fail(f"unexpected case_id: {cr['case_id']!r}")