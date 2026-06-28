"""REQ-033 US7 T122 — Failed-case trace/run/case link tests.

Locks the contract from tasks.md US7:

> T122: Write failing failed-case trace-link tests in
> backend/tests/eval/test_033_failed_case_trace_links.py. Verify report
> links identify trace/run/case or explicitly state "trace unavailable".

The eval report rendering (US5 + US7) must surface three references per
failed case so developers can jump from the eval report to local
artifacts + the originating trace/run:

- ``trace_id`` — the OTel trace hex id (or "unavailable").
- ``run_id`` — the eval/agent run UUID (or "unknown").
- ``case_id`` — always present (per case).
- ``artifact_ref`` — local artifact path (or "unavailable").
- ``langsmith_url`` — LangSmith deep-link (or "unavailable" when not
  enabled per US6 deferral).

TDD: assertions fail until T125 (report.py extension) + T127 (OTel
trace extraction adapter) + T126 (TraceRunRef helpers) land.

All tests are pure-Python (no DB / no async). They read
``app.eval.report.render_json_report`` + ``render_markdown_report`` and
assert the contract documented in ``specs/033-eval-pm-dashboard/contracts/
eval-langsmith-cli.md``.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from uuid import UUID, uuid4

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
    trace_id: str | None = None,
    artifact_ref: str | None = None,
    run_id: UUID | None = None,
    node: str = "interview.score",
) -> CaseResult:
    """Build a synthetic CaseResult with optional trace + artifact refs."""
    metrics: dict[str, Any_dict_compatible] = {  # type: ignore[valid-type]
        "chinese_fidelity": 0.95,
    }
    if trace_id is not None:
        metrics["trace_id"] = trace_id
    if artifact_ref is not None:
        metrics["artifact_ref"] = artifact_ref
    return CaseResult(
        case_id=case_id,
        node=node,
        passed=passed,
        metrics=metrics,
        actual_output={"score": 9},
        failure_reasons=[] if passed else ["chinese_fidelity"],
        label=f"{case_id} label",
        expected_fidelity_pass=True,
        run_id=run_id,
    )


def _build_report(
    failed_with_trace: int = 1,
    failed_without_trace: int = 0,
    passed_count: int = 0,
    run_id: UUID | None = None,
) -> EvalReport:
    """Build a synthetic EvalReport with controlled failed cases.

    ``failed_with_trace`` failed cases include a trace_id; ``failed_without_trace``
    cases leave it None so the report must render "unavailable" explicitly.
    """
    run_id = run_id or uuid4()
    cases: list[CaseResult] = []
    # Failed-with-trace cases (one per row in the failed-case drilldown table).
    for i in range(failed_with_trace):
        cases.append(
            _make_case(
                case_id=f"failed_traced_{i}",
                passed=False,
                trace_id=f"abc{i:030x}",
                artifact_ref=f"docs/evidence/case_failed_traced_{i}.json",
                run_id=run_id,
            )
        )
    # Failed-without-trace cases (must render "unavailable" not crash / not silent).
    for i in range(failed_without_trace):
        cases.append(
            _make_case(
                case_id=f"failed_untraced_{i}",
                passed=False,
                trace_id=None,
                artifact_ref=None,
                run_id=run_id,
            )
        )
    # Passed cases (must NOT appear in the failed-case drilldown table).
    for i in range(passed_count):
        cases.append(
            _make_case(
                case_id=f"passed_{i}",
                passed=True,
                trace_id=f"def{i:030x}",
                run_id=run_id,
            )
        )

    return EvalReport(
        timestamp="2026-06-29T00:00:00+00:00",
        git_sha="abc1234",
        model="deepseek-v4-pro",
        total_cases=len(cases),
        passed_cases=passed_count,
        failed_cases=failed_with_trace + failed_without_trace,
        skipped_cases=0,
        per_node={},
        case_results=cases,
        run_id=run_id,
        started_at="2026-06-29T00:00:00+00:00",
        finished_at="2026-06-29T00:00:01+00:00",
        model_version="deepseek-v4-pro",
        version_context=VersionContext.unknown(environment="LOCAL"),
        aggregate_pass_rate=passed_count / len(cases) if cases else 0.0,
        known_regression_recall=1.0,
        stale_case_count=0,
        source_revision="abc1234",
        branch="feature/us7",
        prompt_fingerprint="fp-us7",
        rubric_version="v1",
        environment="LOCAL",
    )


# ---------------------------------------------------------------------------
# JSON report — failed-case trace link fields
# ---------------------------------------------------------------------------


class TestFailedCaseTraceLinksJSON:
    """The JSON report must surface trace/run/case identifiers per failed case."""

    def test_failed_case_has_trace_id_when_present(self) -> None:
        report = _build_report(failed_with_trace=2, failed_without_trace=0)
        out = render_json_report(report)
        failed = [cr for cr in out["case_results"] if not cr["passed"]]
        assert len(failed) == 2
        for cr in failed:
            # trace_id must be a non-empty hex string (or the literal "unavailable")
            assert "trace_id" in cr, f"case {cr['case_id']} missing trace_id"
            assert cr["trace_id"] != "unknown", (
                f"case {cr['case_id']} uses 'unknown' — must use real trace or 'unavailable'"
            )
            assert cr["trace_id"] != "", (
                f"case {cr['case_id']} has empty trace_id"
            )

    def test_failed_case_has_run_id_when_present(self) -> None:
        run_id = uuid4()
        report = _build_report(failed_with_trace=1, failed_without_trace=0, run_id=run_id)
        out = render_json_report(report)
        failed = [cr for cr in out["case_results"] if not cr["passed"]]
        assert len(failed) == 1
        # run_id on each per-case row must equal the parent run's id.
        assert str(failed[0]["run_id"]) == str(run_id)

    def test_failed_case_has_case_id_always(self) -> None:
        report = _build_report(failed_with_trace=2, failed_without_trace=1)
        out = render_json_report(report)
        for cr in out["case_results"]:
            assert cr["case_id"], "every case must have a non-empty case_id"
            assert cr["case_id"] != "unknown", (
                f"case_id 'unknown' is invalid: {cr['case_id']!r}"
            )

    def test_failed_case_without_trace_says_unavailable_explicitly(self) -> None:
        """Missing trace must be the literal string 'unavailable' (T123 contract)."""
        report = _build_report(failed_with_trace=0, failed_without_trace=3)
        out = render_json_report(report)
        failed = [cr for cr in out["case_results"] if not cr["passed"]]
        assert len(failed) == 3
        for cr in failed:
            # Per T123 contract: missing trace must render the literal
            # "unavailable" — never None, never empty string, never silent omission.
            assert cr.get("trace_id") == "unavailable", (
                f"case {cr['case_id']} must have trace_id == 'unavailable', "
                f"got {cr.get('trace_id')!r}"
            )

    def test_failed_case_has_artifact_ref(self) -> None:
        report = _build_report(failed_with_trace=1, failed_without_trace=1)
        out = render_json_report(report)
        failed = [cr for cr in out["case_results"] if not cr["passed"]]
        for cr in failed:
            assert "artifact_ref" in cr, (
                f"case {cr['case_id']} missing artifact_ref"
            )
            # artifact_ref can be the path or "unavailable" — never empty.
            assert cr["artifact_ref"], (
                f"case {cr['case_id']} has empty artifact_ref"
            )

    def test_json_report_serializes_with_all_three_refs(self) -> None:
        """The full JSON must include trace_id / run_id / case_id per row."""
        report = _build_report(failed_with_trace=2)
        out = render_json_report(report)
        # Top-level run_id present.
        assert "run_id" in out
        # Per-case: every required field exists.
        for cr in out["case_results"]:
            assert "trace_id" in cr
            assert "run_id" in cr
            assert "case_id" in cr
            assert "artifact_ref" in cr


# ---------------------------------------------------------------------------
# Markdown report — Failed-case drilldown section contract
# ---------------------------------------------------------------------------


class TestFailedCaseTraceLinksMarkdown:
    """The Markdown drilldown section must render trace/run/case refs."""

    def test_markdown_has_failed_case_drilldown_section(self) -> None:
        report = _build_report(failed_with_trace=2)
        md = render_markdown_report(report)
        # US5 contract requires the drilldown section header.
        assert "## Failed-case drilldown" in md, (
            "Failed-case drilldown section header missing"
        )

    def test_markdown_drilldown_table_has_required_columns(self) -> None:
        report = _build_report(failed_with_trace=2)
        md = render_markdown_report(report)
        # Header row of the drilldown table must include the canonical
        # US7 columns: case_id, trace, run_id, artifact.
        # The renderer may use slightly different naming; check the
        # essential columns are present.
        # Look for the drilldown table header.
        section_match = re.search(
            r"## Failed-case drilldown.*?(?=\n## |\Z)",
            md,
            flags=re.DOTALL,
        )
        assert section_match, "drilldown section not found"
        section = section_match.group(0)
        # Required columns: Case ID, Trace (per US7 T122)
        assert "Case ID" in section, "drilldown table missing 'Case ID' column"
        assert "Trace" in section, "drilldown table missing 'Trace' column"

    def test_markdown_failed_case_with_trace_renders_id(self) -> None:
        report = _build_report(failed_with_trace=1)
        md = render_markdown_report(report)
        # The traced case id should appear with a trace_id-like hex.
        # We don't pin the exact hex (T127 determines it), but the row
        # must contain a non-trivial identifier (not just "unavailable").
        # Look for the case_id in the drilldown section.
        section = re.search(
            r"## Failed-case drilldown.*?(?=\n## |\Z)",
            md,
            flags=re.DOTALL,
        ).group(0)
        assert "failed_traced_0" in section
        # Trace column should have a non-"unavailable" value when the
        # case carries a trace_id. Either hex or "unavailable" is OK.
        # We pin "unavailable" absence:
        assert "failed_traced_0" in section
        # Find the row by case_id and inspect adjacent trace column.
        row_match = re.search(
            r"\|\s*`?failed_traced_0`?\s*\|.*?\|\s*`([^`]+)`\s*\|",
            section,
        )
        assert row_match, (
            f"could not extract the trace column for failed_traced_0:\n{section}"
        )
        trace_val = row_match.group(1)
        assert trace_val != "unavailable", (
            f"failed_traced_0 should render real trace id, got {trace_val!r}"
        )
        assert trace_val != "unknown", (
            f"failed_traced_0 must not use 'unknown' for trace, got {trace_val!r}"
        )

    def test_markdown_failed_case_without_trace_says_unavailable(self) -> None:
        """T123: missing trace must render 'unavailable' explicitly in markdown."""
        report = _build_report(failed_with_trace=0, failed_without_trace=2)
        md = render_markdown_report(report)
        section = re.search(
            r"## Failed-case drilldown.*?(?=\n## |\Z)",
            md,
            flags=re.DOTALL,
        ).group(0)
        # The untraced case rows must say "unavailable" in the trace column.
        # We grep for the literal cell value, anchored on the case id.
        row_match = re.search(
            r"\|\s*`?failed_untraced_0`?\s*\|.*?\|\s*`?(unavailable)`?\s*\|",
            section,
        )
        assert row_match, (
            "failed_untraced_0 row should render 'unavailable' for trace — "
            f"section was:\n{section}"
        )

    def test_markdown_drilldown_only_includes_failed_cases(self) -> None:
        """Passed cases must NOT appear in the failed-case drilldown table."""
        report = _build_report(failed_with_trace=1, passed_count=2)
        md = render_markdown_report(report)
        section = re.search(
            r"## Failed-case drilldown.*?(?=\n## |\Z)",
            md,
            flags=re.DOTALL,
        ).group(0)
        # passed_0/1 should not appear in the drilldown section.
        assert "passed_0" not in section, (
            "drilldown table incorrectly includes passed cases"
        )
        assert "passed_1" not in section


# ---------------------------------------------------------------------------
# Round-trip — JSON / Markdown / DB-shaped data stays in sync
# ---------------------------------------------------------------------------


class TestTraceLinkContractInvariants:
    """Cross-format invariants that any future refactor must preserve."""

    def test_run_id_at_top_level_matches_per_case_run_id(self) -> None:
        report = _build_report(failed_with_trace=2)
        out = render_json_report(report)
        top_run_id = out["run_id"]
        for cr in out["case_results"]:
            assert str(cr["run_id"]) == str(top_run_id)

    def test_drilldown_table_row_count_matches_failed_count(self) -> None:
        report = _build_report(failed_with_trace=3, failed_without_trace=2, passed_count=1)
        md = render_markdown_report(report)
        section = re.search(
            r"## Failed-case drilldown.*?(?=\n## |\Z)",
            md,
            flags=re.DOTALL,
        ).group(0)
        # Count table rows (skip header + separator).
        body_rows = [
            line
            for line in section.splitlines()
            if line.startswith("|") and not line.startswith("|---") and "Case ID" not in line
        ]
        # 3 + 2 = 5 failed cases.
        assert len(body_rows) == 5, (
            f"drilldown should have 5 rows, got {len(body_rows)}:\n{section}"
        )


# ---------------------------------------------------------------------------
# Type alias import shim (avoids forward-ref to typing.Any for older mypy)
# ---------------------------------------------------------------------------

from typing import Any as Any_dict_compatible  # noqa: E402