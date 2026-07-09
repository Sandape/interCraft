"""JSON + Markdown rendering for ``EvalReport``.

REQ-033 Sub-batch 1 (US5 / US7 / US9 / FR-014, FR-015, FR-016):

- ``render_json_report(results) -> dict``: top-level dict with
  ``run_id`` / ``started_at`` / ``finished_at`` / ``git_sha`` /
  ``model_version`` / aggregate counts + per-node + per-case rows.
  Stable across runs so CI artifact diffing works.
- ``render_markdown_report(results) -> str``: human-readable report with
  six sections (Header / Summary / Per-case verdicts / Debug
  identifiers / Failed-case drilldown / Aggregate stats). See T050.
- ``EvalReportModel`` (Pydantic v2): the canonical stable JSON shape for
  eval reports. Mirrors ``EvalReport`` dataclass but adds
  validation-friendly defaults (``"unknown"`` for missing version
  fields per SC-010) and stable ``to_json`` / ``from_json`` round-trip.
  Locked by T047.

Backward compatibility: ``render_json_report`` accepts the *legacy*
shape (plain ``dict`` from ``EvalReport.to_dict()``) as well as the
modern ``EvalReport`` dataclass. If ``run_id`` is missing from the input
it is auto-generated so old callers don't have to change at once.

Usage::

    from app.eval.runner import EvalReport, run_eval_suite
    from app.eval.report import render_json_report, render_markdown_report

    report = await run_eval_suite(cases)
    out = render_json_report(report)
    Path("report.json").write_text(json.dumps(out, indent=2))
    Path("report.md").write_text(render_markdown_report(report))
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.eval.runner import CaseResult, EvalReport


def _coerce_report(report: EvalReport | dict[str, Any]) -> dict[str, Any]:
    """Normalize ``EvalReport`` or its dict form into a plain dict.

    Guarantees the returned dict has all REQ-033 Sub-batch 1 fields
    (``run_id`` / ``started_at`` / ``finished_at`` / ``git_sha`` /
    ``model_version``). Missing values are filled with safe defaults so
    the rendered JSON / Markdown stay schema-stable across runs.
    """
    if isinstance(report, EvalReport):
        base = report.to_dict()
    elif isinstance(report, dict):
        base = dict(report)
    else:
        raise TypeError(
            f"report must be EvalReport or dict, got {type(report).__name__}"
        )

    # run_id — auto-fill if missing (legacy callers).
    raw_run_id = base.get("run_id")
    if not raw_run_id:
        base["run_id"] = str(uuid4())
    elif isinstance(raw_run_id, UUID) or not isinstance(raw_run_id, str):
        base["run_id"] = str(raw_run_id)

    # started_at / finished_at — derive from legacy `timestamp` if missing.
    ts = base.get("timestamp") or ""
    base.setdefault("started_at", ts)
    base.setdefault("finished_at", ts)

    base.setdefault("git_sha", "unknown")
    base.setdefault("model_version", base.get("model", "unknown"))
    base.setdefault("model", base.get("model", "unknown"))

    base.setdefault("total_cases", 0)
    base.setdefault("passed_cases", 0)
    base.setdefault("failed_cases", 0)
    base.setdefault("skipped_cases", 0)
    base.setdefault("per_node", {})
    base.setdefault("case_results", [])

    return base


def render_json_report(report: EvalReport | dict[str, Any]) -> dict[str, Any]:
    """Return the canonical JSON-friendly dict for an ``EvalReport``.

    Top-level shape::

        {
          "run_id": "uuid4",
          "started_at": "ISO 8601",
          "finished_at": "ISO 8601",
          "timestamp": "ISO 8601",  # legacy alias for finished_at
          "git_sha": "...",
          "model": "...",
          "model_version": "...",
          "total_cases": int,
          "passed_cases": int,
          "failed_cases": int,
          "skipped_cases": int,
          "per_node": { node: {total, passed, pass_rate, avg_chinese_fidelity} },
          "case_results": [ {
            case_id, node, passed, run_id, trace_id, artifact_ref,
            langsmith_url, ...
          }, ... ]
        }

    REQ-033 US7 (T125): each ``case_results`` row carries the four
    reference fields as top-level keys so downstream consumers
    (PM dashboard, badcase review, CI artifact diff) can join
    without walking the ``metrics`` dict:

    - ``trace_id`` — OTel trace id hex, or the literal string
      ``"unavailable"`` when no span was active.
    - ``run_id`` — eval run UUID (string form). Mirrors the parent
      ``EvalReport.run_id`` so per-case rows are independently
      joinable.
    - ``artifact_ref`` — local artifact path, or
      ``"unavailable"`` when no path was recorded.
    - ``langsmith_url`` — LangSmith deep link, or
      ``"unavailable"`` when LangSmith is not enabled (US6 deferred
      per user decision).
    """
    out = _coerce_report(report)
    # Ensure per-case run_id + trace/run references are present
    # (REQ-033 US7 join fields — T125 + T126).
    run_id = out["run_id"]
    for cr in out["case_results"]:
        if not isinstance(cr, dict):
            continue
        # run_id (US7 join field).
        if not cr.get("run_id"):
            cr["run_id"] = run_id
        elif isinstance(cr.get("run_id"), UUID):
            cr["run_id"] = str(cr["run_id"])
        # trace_id / artifact_ref — promote from metrics when present,
        # else default to the canonical "unavailable" marker (US7 T123).
        metrics = cr.get("metrics") or {}
        if not isinstance(metrics, dict):
            metrics = {}
        trace_id = cr.get("trace_id") or metrics.get("trace_id")
        if trace_id is None or trace_id == "" or trace_id == "unknown":
            trace_id = "unavailable"
        cr["trace_id"] = str(trace_id)
        artifact_ref = cr.get("artifact_ref") or metrics.get("artifact_ref")
        if artifact_ref is None or artifact_ref == "":
            artifact_ref = "unavailable"
        cr["artifact_ref"] = str(artifact_ref)
        # langsmith_url — US6 deferred, always "unavailable" unless the
        # case / report explicitly carries a non-empty URL.
        ls_url = (
            cr.get("langsmith_url")
            or metrics.get("langsmith_url")
            or out.get("langsmith_url")
        )
        if ls_url is None or ls_url == "" or ls_url == "unknown":
            ls_url = "unavailable"
        cr["langsmith_url"] = str(ls_url)
        # Persist metrics back if we promoted trace_id/artifact_ref
        # from the row level (keep them both visible for back-compat).
        if "trace_id" not in metrics and cr.get("trace_id") != "unavailable":
            metrics["trace_id"] = cr["trace_id"]
        if "artifact_ref" not in metrics and cr.get("artifact_ref") != "unavailable":
            metrics["artifact_ref"] = cr["artifact_ref"]
        cr["metrics"] = metrics
    return out


def render_markdown_report(report: EvalReport | dict[str, Any]) -> str:
    """Return a Markdown rendering of the eval report (human-readable).

    REQ-033 US5 (T050) contract: the output contains six sections:

    1. **Header** — runId, sourceRevision, branch, environment, status,
       started/completed, model version.
    2. **Summary** — aggregate pass rate, known regression recall,
       stale case count, total budget.
    3. **Per-case verdicts** — table with caseId / verdict /
       failure reason / trace id / artifact ref.
    4. **Debug identifiers** — runId / sourceRevision / branch + artifact
       paths + (optional) LangSmith URL.
    5. **Failed-case drilldown** — local artifact path + trace link +
       LangSmith link (or "trace unavailable" marker when missing).
    6. **Aggregate stats** — charts-as-table matching JSON values.

    Deterministic: same input dict → same output bytes.
    """
    out = _coerce_report(report)
    lines: list[str] = []

    # ---- Section 1: Header ----
    run_id = out["run_id"]
    status = out.get("status") or (
        "PASSED" if int(out.get("failed_cases", 0) or 0) == 0
        and int(out.get("total_cases", 0) or 0) > 0
        else "FAILED"
    )
    source_rev = out.get("source_revision") or out.get("git_sha") or "unknown"
    branch = out.get("branch") or "unknown"
    environment = out.get("environment") or "unknown"
    model_version = out.get("model_version") or out.get("model") or "unknown"
    started_at = out.get("started_at") or out.get("timestamp") or "unknown"
    finished_at = out.get("finished_at") or out.get("timestamp") or "unknown"
    version_ctx = out.get("version_context") or {}

    lines.append("# Eval Report\n\n")
    lines.append("## Header\n\n")
    lines.append(f"- **Run ID**: `{run_id}`\n")
    lines.append(f"- **Status**: `{status}`\n")
    lines.append(f"- **Source Revision**: `{source_rev}`\n")
    lines.append(f"- **Branch**: `{branch}`\n")
    lines.append(f"- **Environment**: `{environment}`\n")
    lines.append(f"- **Model**: `{model_version}`\n")
    lines.append(f"- **Started At**: `{started_at}`\n")
    lines.append(f"- **Completed At**: `{finished_at}`\n")
    lines.append(
        f"- **Schema Version**: "
        f"`{version_ctx.get('schema_version') or version_ctx.get('schemaVersion') or 'unknown'}`\n"
    )
    lines.append(
        f"- **App Version**: "
        f"`{version_ctx.get('app_version') or version_ctx.get('appVersion') or 'unknown'}`\n"
    )
    lines.append("\n")

    # ---- Section 2: Summary ----
    aggregate = float(out.get("aggregate_pass_rate", 0.0) or 0.0)
    known_regression = float(out.get("known_regression_recall", 1.0) or 1.0)
    stale_count = int(out.get("stale_case_count", 0) or 0)
    total_budget = out.get("total_budget") or "unknown"
    lines.append("## Summary\n\n")
    lines.append(f"- **Aggregate Pass Rate**: `{aggregate:.2%}`\n")
    lines.append(f"- **Known Regression Recall**: `{known_regression:.2%}`\n")
    lines.append(f"- **Stale Case Count**: `{stale_count}`\n")
    lines.append(f"- **Total Budget**: `{total_budget}`\n")
    lines.append(f"- **Total Cases**: `{int(out.get('total_cases', 0) or 0)}`\n")
    lines.append(f"- **Passed**: `{int(out.get('passed_cases', 0) or 0)}`\n")
    lines.append(f"- **Failed**: `{int(out.get('failed_cases', 0) or 0)}`\n")
    lines.append(f"- **Skipped**: `{int(out.get('skipped_cases', 0) or 0)}`\n\n")

    # ---- Section 3: Per-case verdicts ----
    lines.append("## Per-case verdicts\n\n")
    case_results = out.get("case_results") or []
    if not case_results:
        lines.append("_No cases._\n\n")
    else:
        lines.append(
            "| Case ID | Verdict | Failure reason | Trace ID | Artifact ref |\n"
        )
        lines.append("|---|---|---|---|---|\n")
        for cr in case_results:
            if not isinstance(cr, dict):
                continue
            verdict = "PASS" if cr.get("passed") else "FAIL"
            if any("stale_case_skipped" in fr for fr in (cr.get("failure_reasons") or [])):
                verdict = "STALE"
            reasons = ", ".join(cr.get("failure_reasons") or []) or "—"
            # trace id from CaseResult.metrics if present, else 'unavailable'.
            trace_id = "unavailable"
            artifact_ref = "unavailable"
            metrics = cr.get("metrics") or {}
            if isinstance(metrics, dict):
                trace_id = metrics.get("trace_id") or trace_id
                artifact_ref = metrics.get("artifact_ref") or artifact_ref
            # Direct fields (rendered by newer code) take precedence.
            trace_id = cr.get("trace_id") or trace_id
            artifact_ref = cr.get("artifact_ref") or artifact_ref
            if trace_id in (None, "", "unknown"):
                trace_id = "unavailable"
            if artifact_ref in (None, "", "unknown"):
                artifact_ref = "unavailable"
            lines.append(
                f"| `{cr.get('case_id', '')}` | {verdict} | {reasons} | "
                f"`{trace_id}` | `{artifact_ref}` |\n"
            )
        lines.append("\n")

    # ---- Section 4: Debug identifiers ----
    artifacts = out.get("artifacts") or {}
    lines.append("## Debug identifiers\n\n")
    lines.append(f"- **runId**: `{run_id}`\n")
    lines.append(f"- **sourceRevision**: `{source_rev}`\n")
    lines.append(f"- **branch**: `{branch}`\n")
    lines.append(
        f"- **artifact.json**: `{artifacts.get('json') or 'docs/evidence/' + str(run_id) + '/eval-report.json'}`\n"
    )
    lines.append(
        f"- **artifact.markdown**: `{artifacts.get('markdown') or 'docs/evidence/' + str(run_id) + '/eval-report.md'}`\n"
    )
    # LangSmith URL only if LangSmith enabled and ref present.
    langsmith_url = out.get("langsmith_url") or out.get("langsmithUrl") or ""
    if langsmith_url and langsmith_url != "unavailable":
        lines.append(f"- **LangSmith URL**: `{langsmith_url}`\n")
    else:
        lines.append("- **LangSmith URL**: `trace unavailable` (LangSmith not enabled)\n")
    lines.append("\n")

    # ---- Section 5: Failed-case drilldown ----
    lines.append("## Failed-case drilldown\n\n")
    failed_cases = [cr for cr in case_results if isinstance(cr, dict) and not cr.get("passed")]
    if not failed_cases:
        lines.append("_No failing cases._\n\n")
    else:
        lines.append("| Case ID | Node | Trace | Artifact | LangSmith |\n")
        lines.append("|---|---|---|---|---|\n")
        for cr in failed_cases:
            case_id = cr.get("case_id", "unknown")
            node = cr.get("node", "unknown")
            metrics = cr.get("metrics") or {}
            trace_id = (
                cr.get("trace_id")
                or (metrics.get("trace_id") if isinstance(metrics, dict) else None)
                or "unavailable"
            )
            artifact_ref = (
                cr.get("artifact_ref")
                or (metrics.get("artifact_ref") if isinstance(metrics, dict) else None)
                or f"docs/evidence/{run_id}/cases/{case_id}.json"
            )
            ls_url = (
                cr.get("langsmith_url")
                or (metrics.get("langsmith_url") if isinstance(metrics, dict) else None)
                or "trace unavailable"
            )
            lines.append(
                f"| `{case_id}` | `{node}` | `{trace_id}` | `{artifact_ref}` | `{ls_url}` |\n"
            )
        lines.append("\n")

    # ---- Section 6: Aggregate stats ----
    lines.append("## Aggregate stats\n\n")
    lines.append("| Metric | Value |\n|---|---:|\n")
    lines.append(f"| Aggregate Pass Rate | {aggregate:.2%} |\n")
    lines.append(f"| Known Regression Recall | {known_regression:.2%} |\n")
    lines.append(f"| Stale Case Count | {stale_count} |\n")
    lines.append(f"| Total Cases | {int(out.get('total_cases', 0) or 0)} |\n")
    lines.append(f"| Passed | {int(out.get('passed_cases', 0) or 0)} |\n")
    lines.append(f"| Failed | {int(out.get('failed_cases', 0) or 0)} |\n")
    lines.append(f"| Skipped | {int(out.get('skipped_cases', 0) or 0)} |\n\n")

    # Per-node breakdown (kept for backwards compatibility / richer detail).
    if out.get("per_node"):
        lines.append("### Per-node breakdown\n\n")
        lines.append("| Node | Total | Passed | Pass rate | Avg fidelity |\n")
        lines.append("|---|---:|---:|---:|---:|\n")
        for node, stats in sorted(out["per_node"].items()):
            total = int(stats.get("total", 0))
            passed = int(stats.get("passed", 0))
            pass_rate = stats.get("pass_rate", 0.0)
            avg_fid = stats.get("avg_chinese_fidelity", 0.0)
            lines.append(
                f"| `{node}` | {total} | {passed} | "
                f"{pass_rate:.2%} | {avg_fid:.3f} |\n"
            )
        lines.append("\n")

    return "".join(lines)


def parse_timestamp(ts: str) -> datetime | None:
    """Parse an ISO 8601 timestamp; return ``None`` on failure.

    Convenience helper for downstream consumers that want to sort /
    filter reports by wall-clock time.
    """
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts)
    except ValueError:
        return None


def normalize_req045_report(
    report: EvalReport | dict[str, Any],
    *,
    suite: str = "golden",
    dataset_version: str = "golden-v1",
    artifacts: dict[str, str] | None = None,
    langsmith_export_status: str = "DISABLED",
    langsmith_url: str = "unavailable",
    export_policy_decision_id: str | None = None,
) -> dict[str, Any]:
    """Return the REQ-045 camelCase eval report contract."""
    out = render_json_report(report)
    run_id = str(out.get("run_id") or out.get("runId") or uuid4())
    case_results: list[dict[str, Any]] = []
    for raw_case in out.get("case_results", []) or []:
        if not isinstance(raw_case, dict):
            continue
        metrics = raw_case.get("metrics") if isinstance(raw_case.get("metrics"), dict) else {}
        case_node = str(raw_case.get("node") or "unknown")
        graph = case_node.split(".", 1)[0] if "." in case_node else "unknown"
        trace_id = raw_case.get("trace_id") or metrics.get("trace_id") or "unavailable"
        span_id = raw_case.get("span_id") or metrics.get("span_id") or "unavailable"
        artifact_ref = raw_case.get("artifact_ref") or metrics.get("artifact_ref") or "unavailable"
        case_langsmith_url = raw_case.get("langsmith_url") or metrics.get("langsmith_url") or langsmith_url
        case_results.append(
            {
                "caseId": str(raw_case.get("case_id") or "unknown"),
                "runId": str(raw_case.get("run_id") or run_id),
                "lifecycle": str(raw_case.get("lifecycle") or "GOLDEN"),
                "graph": graph,
                "node": case_node,
                "passed": bool(raw_case.get("passed")),
                "failureReasons": list(raw_case.get("failure_reasons") or []),
                "deterministicMetrics": dict(metrics),
                "expectedFidelityPass": bool(raw_case.get("expected_fidelity_pass", True)),
                "traceId": str(trace_id or "unavailable"),
                "spanId": str(span_id or "unavailable"),
                "artifactRef": str(artifact_ref or "unavailable"),
                "langsmithUrl": str(case_langsmith_url or "unavailable"),
                "judgeVerdicts": list(raw_case.get("judge_verdicts") or []),
            }
        )

    return {
        "schemaVersion": "045.eval-report.v1",
        "runId": run_id,
        "suite": suite,
        "environment": str(out.get("environment") or "LOCAL").upper(),
        "status": str(out.get("status") or ("PASSED" if int(out.get("failed_cases", 0) or 0) == 0 else "FAILED")),
        "sourceRevision": str(out.get("source_revision") or out.get("git_sha") or "unknown"),
        "branch": str(out.get("branch") or "unknown"),
        "datasetVersion": dataset_version,
        "promptFingerprint": str(out.get("prompt_fingerprint") or "unknown"),
        "rubricVersion": str(out.get("rubric_version") or "unknown"),
        "modelVersion": str(out.get("model_version") or out.get("model") or "unknown"),
        "startedAt": str(out.get("started_at") or out.get("timestamp") or "unknown"),
        "finishedAt": str(out.get("finished_at") or out.get("timestamp") or "unknown"),
        "aggregatePassRate": float(out.get("aggregate_pass_rate", 0.0) or 0.0),
        "knownRegressionRecall": float(out.get("known_regression_recall", 1.0) or 1.0),
        "tokenUsage": {
            "inputTokens": int(out.get("input_tokens", 0) or 0),
            "outputTokens": int(out.get("output_tokens", 0) or 0),
            "totalTokens": int(out.get("total_tokens", 0) or 0),
        },
        "costUsd": float(out.get("budget_cost_used_usd", 0.0) or 0.0),
        "latencyMs": int(out.get("latency_ms", 0) or 0),
        "langsmithExportStatus": langsmith_export_status,
        "exportPolicyDecisionId": export_policy_decision_id,
        "langsmithUrl": langsmith_url or "unavailable",
        "artifacts": artifacts or {"json": "", "markdown": ""},
        "caseResults": case_results,
    }


def render_req045_markdown_report(payload: dict[str, Any]) -> str:
    """Render a concise Markdown companion for a REQ-045 JSON payload."""
    has_judge = any(case.get("judgeVerdicts") for case in payload.get("caseResults", []))
    lines = [
        "# REQ-045 Eval Report\n\n",
        f"- Run ID: `{payload['runId']}`\n",
        f"- Status: `{payload['status']}`\n",
        f"- Suite: `{payload['suite']}`\n",
        f"- Environment: `{payload['environment']}`\n",
        f"- Dataset: `{payload['datasetVersion']}`\n",
        f"- Source Revision: `{payload['sourceRevision']}`\n",
        f"- LangSmith: `{payload['langsmithExportStatus']}`\n\n",
        "## Case Results\n\n",
        "| Case ID | Lifecycle | Passed | Trace | Artifact | LangSmith"
        + (" | Judge | Blocks |" if has_judge else " |")
        + "\n",
        "|---|---|---:|---|---|---"
        + ("|---:|---:|" if has_judge else "|")
        + "\n",
    ]
    for case in payload.get("caseResults", []):
        judge_bits = ""
        if has_judge:
            verdicts = case.get("judgeVerdicts") or []
            first = verdicts[0] if verdicts else {}
            judge_bits = (
                f" | `{first.get('score', 'unavailable')}` | "
                f"{bool(first.get('blocksMerge', False))}"
            )
        lines.append(
            f"| `{case['caseId']}` | `{case['lifecycle']}` | {case['passed']} | "
            f"`{case['traceId']}` | `{case['artifactRef']}` | `{case['langsmithUrl']}`"
            f"{judge_bits} |\n"
        )
    return "".join(lines)


def write_req045_report_artifacts(
    report: EvalReport | dict[str, Any],
    *,
    json_path: Path,
    markdown_path: Path,
    suite: str = "golden",
    dataset_version: str = "golden-v1",
    langsmith_export_status: str = "DISABLED",
    langsmith_url: str = "unavailable",
    export_policy_decision_id: str | None = None,
) -> dict[str, Any]:
    artifacts = {"json": str(json_path), "markdown": str(markdown_path)}
    payload = normalize_req045_report(
        report,
        suite=suite,
        dataset_version=dataset_version,
        artifacts=artifacts,
        langsmith_export_status=langsmith_export_status,
        langsmith_url=langsmith_url,
        export_policy_decision_id=export_policy_decision_id,
    )
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(render_req045_markdown_report(payload), encoding="utf-8")
    return payload


# ---------------------------------------------------------------------------
# EvalReportModel — Pydantic v2 stable eval report contract (T047)
# ---------------------------------------------------------------------------


# Canonical valid ``status`` values per data-model.md §EvalRun.
_VALID_REPORT_STATUSES: frozenset[str] = frozenset(
    {"STARTED", "PASSED", "FAILED", "INCOMPLETE", "SYNCED", "SYNC_FAILED"}
)


def _normalize_unknown(v: Any) -> str:
    """Empty / None → ``"unknown"`` (SC-010 normalization)."""
    if v is None:
        return "unknown"
    if isinstance(v, str) and not v.strip():
        return "unknown"
    return str(v)


class CaseResultModel(BaseModel):
    """Per-case verdict Pydantic model (T047).

    Mirrors ``CaseResult`` from ``app.eval.runner``. Field semantics per
    data-model.md §EvalCaseResult + REQ-033 US7 (trace id + artifact
    ref for debug).
    """

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    case_id: str
    node: str
    verdict: str = "PASS"  # PASS / FAIL / STALE / SKIPPED / ERROR
    passed: bool = True
    failure_reasons: list[str] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    actual_output: dict[str, Any] = Field(default_factory=dict)
    trace_id: str = "unavailable"  # explicit per US7 contract
    artifact_ref: str = "unavailable"
    run_id: str = "unknown"
    label: str = ""
    expected_fidelity_pass: bool = True

    @field_validator("verdict")
    @classmethod
    def _normalize_verdict(cls, v: str) -> str:
        norm = (v or "").upper()
        if norm not in {"PASS", "FAIL", "STALE", "SKIPPED", "ERROR", "PENDING"}:
            return "ERROR"
        return norm

    @field_validator("trace_id", "artifact_ref", "run_id")
    @classmethod
    def _normalize_id(cls, v: Any) -> str:
        return _normalize_unknown(v)

    @classmethod
    def from_case_result(cls, cr: "CaseResult | dict[str, Any]") -> "CaseResultModel":
        """Build from either a ``CaseResult`` dataclass or a dict."""
        if isinstance(cr, CaseResult):
            verdict = "PASS" if cr.passed else "FAIL"
            if any("stale_case_skipped" in fr for fr in cr.failure_reasons):
                verdict = "STALE"
            return cls(
                case_id=cr.case_id,
                node=cr.node,
                verdict=verdict,
                passed=cr.passed,
                failure_reasons=list(cr.failure_reasons),
                metrics=dict(cr.metrics),
                actual_output=dict(cr.actual_output),
                trace_id=cr.metrics.get("trace_id", "unavailable")
                if isinstance(cr.metrics, dict)
                else "unavailable",
                artifact_ref=cr.metrics.get("artifact_ref", "unavailable")
                if isinstance(cr.metrics, dict)
                else "unavailable",
                run_id=str(cr.run_id) if cr.run_id else "unknown",
                label=cr.label,
                expected_fidelity_pass=cr.expected_fidelity_pass,
            )
        # dict path.
        verdict = cr.get("verdict") or ("PASS" if cr.get("passed") else "FAIL")
        return cls(
            case_id=str(cr.get("case_id", "unknown")),
            node=str(cr.get("node", "unknown")),
            verdict=str(verdict),
            passed=bool(cr.get("passed", True)),
            failure_reasons=list(cr.get("failure_reasons") or []),
            metrics=dict(cr.get("metrics") or {}),
            actual_output=dict(cr.get("actual_output") or {}),
            trace_id=str(cr.get("trace_id", "unavailable")),
            artifact_ref=str(cr.get("artifact_ref", "unavailable")),
            run_id=str(cr.get("run_id", "unknown")),
            label=str(cr.get("label", "")),
            expected_fidelity_pass=bool(cr.get("expected_fidelity_pass", True)),
        )


class EvalReportModel(BaseModel):
    """Stable Pydantic v2 model for eval report artifacts (T047).

    Field semantics per ``data-model.md §EvalRun``:

    - ``runId`` / ``sourceRevision`` / ``branch`` / ``environment`` /
      ``status`` are required strings.
    - ``aggregatePassRate`` / ``knownRegressionRecall`` are floats in
      ``[0.0, 1.0]``.
    - ``staleCaseCount`` is a non-negative int.
    - ``startedAt`` / ``completedAt`` are ISO 8601 strings.
    - ``versionContext`` is the camelCase dict from ``VersionContext.to_dict()``.
    - ``artifacts`` is a dict with ``json`` and ``markdown`` keys.
    - ``caseResults`` is a list of :class:`CaseResultModel`.

    SC-010 compliance: missing optional fields default to ``"unknown"``,
    never None / empty.

    Round-trip: ``to_json`` / ``from_json`` preserve every field.
    """

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    run_id: str
    source_revision: str = "unknown"
    branch: str = "unknown"
    environment: str = "LOCAL"
    status: str = "STARTED"
    aggregate_pass_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    known_regression_recall: float = Field(default=1.0, ge=0.0, le=1.0)
    stale_case_count: int = Field(default=0, ge=0)
    version_context: dict[str, Any] = Field(default_factory=dict)
    started_at: str = ""
    completed_at: str = ""
    artifacts: dict[str, str] = Field(default_factory=dict)
    case_results: list[CaseResultModel] = Field(default_factory=list)
    # Optional metadata preserved for backward compat.
    model: str = "unknown"
    model_version: str = "unknown"
    git_sha: str = "unknown"
    total_cases: int = Field(default=0, ge=0)
    passed_cases: int = Field(default=0, ge=0)
    failed_cases: int = Field(default=0, ge=0)
    skipped_cases: int = Field(default=0, ge=0)
    per_node: dict[str, dict[str, float]] = Field(default_factory=dict)
    prompt_fingerprint: str = "unknown"
    rubric_version: str = "unknown"

    @field_validator("status")
    @classmethod
    def _valid_status(cls, v: str) -> str:
        norm = (v or "").upper()
        if norm not in _VALID_REPORT_STATUSES:
            return "STARTED"
        return norm

    @field_validator(
        "source_revision",
        "branch",
        "environment",
        "model",
        "model_version",
        "git_sha",
        "prompt_fingerprint",
        "rubric_version",
        "started_at",
        "completed_at",
    )
    @classmethod
    def _normalize_unknown_str(cls, v: Any) -> str:
        return _normalize_unknown(v)

    @classmethod
    def from_eval_report(
        cls,
        report: "EvalReport | dict[str, Any]",
        *,
        artifacts: dict[str, str] | None = None,
    ) -> "EvalReportModel":
        """Build from an ``EvalReport`` dataclass or dict.

        Missing fields default to ``"unknown"`` (SC-010). The mapping
        covers both the legacy ``timestamp`` alias and the explicit
        ``started_at`` / ``finished_at`` US9 fields.
        """
        if isinstance(report, EvalReport):
            data: dict[str, Any] = report.to_dict()
        else:
            data = dict(report)

        run_id = data.get("run_id")
        if run_id is None:
            run_id = str(uuid4())
        elif not isinstance(run_id, str):
            run_id = str(run_id)

        case_results_raw = data.get("case_results") or data.get("caseResults") or []
        case_results = [
            CaseResultModel.from_case_result(cr) for cr in case_results_raw
        ]

        started_at = data.get("started_at") or data.get("timestamp") or ""
        completed_at = data.get("finished_at") or data.get("timestamp") or ""
        version_context = data.get("version_context") or data.get("versionContext") or {}

        # Honor explicit ``status`` (e.g. INCOMPLETE for budget-exhausted
        # nightly runs). Fall back to deriving from failed_cases when the
        # source is a legacy EvalReport without an explicit status.
        raw_status = data.get("status")
        if raw_status:
            status = str(raw_status).upper()
        elif int(data.get("total_cases", 0) or 0) == 0:
            # No cases ran — start as STARTED.
            status = "STARTED"
        elif int(data.get("failed_cases", 0) or 0) == 0:
            status = "PASSED"
        else:
            status = "FAILED"

        return cls(
            run_id=run_id,
            source_revision=data.get("source_revision")
            or data.get("sourceRevision")
            or data.get("git_sha")
            or "unknown",
            branch=data.get("branch") or "unknown",
            environment=data.get("environment") or "LOCAL",
            status=status,
            aggregate_pass_rate=float(data.get("aggregate_pass_rate", 0.0) or 0.0),
            known_regression_recall=float(
                data.get("known_regression_recall", 1.0) or 1.0
            ),
            stale_case_count=int(data.get("stale_case_count", 0) or 0),
            version_context=version_context,
            started_at=started_at,
            completed_at=completed_at,
            artifacts=artifacts or {},
            case_results=case_results,
            model=data.get("model") or "unknown",
            model_version=data.get("model_version") or data.get("model") or "unknown",
            git_sha=data.get("git_sha") or data.get("source_revision") or "unknown",
            total_cases=int(data.get("total_cases", 0) or 0),
            passed_cases=int(data.get("passed_cases", 0) or 0),
            failed_cases=int(data.get("failed_cases", 0) or 0),
            skipped_cases=int(data.get("skipped_cases", 0) or 0),
            per_node=dict(data.get("per_node") or {}),
            prompt_fingerprint=data.get("prompt_fingerprint") or "unknown",
            rubric_version=data.get("rubric_version") or "unknown",
        )

    def to_json(self, *, path: Path | None = None) -> str:
        """Serialize to a canonical JSON string.

        If ``path`` is provided, also write to disk and return the JSON
        body (no return-type change).
        """
        payload = self.model_dump(mode="json", by_alias=False)
        out = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
        if path is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(out, encoding="utf-8")
        return out

    @classmethod
    def from_json(cls, payload: str | bytes | Path) -> "EvalReportModel":
        """Re-hydrate from a JSON string, bytes, or file path.

        Round-trip preserves every field including version_context dict.
        """
        if isinstance(payload, Path):
            raw = payload.read_text(encoding="utf-8")
        elif isinstance(payload, bytes):
            raw = payload.decode("utf-8")
        else:
            raw = payload
        data = json.loads(raw)
        # Re-hydrate nested case results.
        if "case_results" in data:
            data["case_results"] = [
                CaseResultModel.model_validate(c) for c in data["case_results"]
            ]
        return cls.model_validate(data)


__all__ = [
    "CaseResultModel",
    "EvalReportModel",
    "normalize_req045_report",
    "parse_timestamp",
    "render_req045_markdown_report",
    "render_json_report",
    "render_markdown_report",
    "write_req045_report_artifacts",
]
