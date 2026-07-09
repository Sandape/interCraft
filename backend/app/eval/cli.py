"""CLI entry point for the eval suite (T040 + T048 + T051).

Usage:
    uv run python -m app.eval.cli run --mode mock
    uv run python -m app.eval.cli run --mode mock --node interview.score
    uv run python -m app.eval.cli run --mode mock --report-out /tmp/eval.json

    # REQ-033 US5 (T048): full flag set
    uv run python -m app.eval.cli run \\
        --suite golden \\
        --report-out docs/evidence/<run_id>/eval-report.json \\
        --markdown-out docs/evidence/<run_id>/eval-report.md \\
        --env ci \\
        --source-revision $(git rev-parse --short HEAD) \\
        --branch $(git rev-parse --abbrev-ref HEAD) \\
        --json

    # REQ-033 US5 (T051): dual-approval override record
    uv run python -m app.eval.cli override-record \\
        --run-id <id> --gate pr_eval \\
        --pm-approver alice --technical-approver bob \\
        --reason "hotfix" --evidence path/to/eval-report.md --json

Exit codes (per contracts/eval-langsmith-cli.md §Shared CLI Rules):
    0 — success / all active cases pass
    1 — operational failure (e.g. nightly budget exhausted → INCOMPLETE)
    2 — invalid arguments
    3 — policy / redaction violation (e.g. override missing dual approval)
    4 — eval gate failed (deterministic prompt-adjacent failure)
"""
from __future__ import annotations

import argparse
import asyncio
import ipaddress
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse
from uuid import uuid4

import structlog

from app.eval.export_policy import PolicyViolation
from app.eval.experiment_compare import compare_experiments
from app.eval.golden_loader import load_golden_cases
from app.eval.judge import calibrate_judge_rubric, default_judge_rubric, run_judge_cases
from app.eval.langsmith_sync import LangSmithSyncError, sync_report_to_langsmith
from app.eval.prompt_proposals import (
    approve_prompt_proposal,
    compare_prompt_proposal,
    create_prompt_proposal,
    proposal_from_payload,
    proposal_to_payload,
    reject_prompt_proposal,
)
from app.eval.report import EvalReportModel, render_markdown_report, write_req045_report_artifacts
from app.eval.runner import EvalReport, EvalRunner
from app.eval.schemas import Environment, ExportDestination, RepresentationLevel
from app.modules.telemetry_contracts.export_policy import (
    DestinationPolicyInput,
    decide_export_policy,
)

logger = structlog.get_logger("eval.cli")

# Default location of golden cases — version-controlled alongside spec.
_DEFAULT_SPEC_DIR = (
    Path(__file__).resolve().parents[3] / "specs" / "026-agent-eval-loop"
)

# Supported values per contracts/eval-langsmith-cli.md.
_VALID_SUITES: frozenset[str] = frozenset({"golden", "nightly", "regression"})
_VALID_ENVS: frozenset[str] = frozenset({"local", "ci", "staging", "production"})
_VALID_GATES: frozenset[str] = frozenset(
    {"pr_eval", "baseline_refresh", "emergency_override"}
)
_VALID_SYNC_LANGSMITH: frozenset[str] = frozenset({"never", "auto", "require"})


# ---------------------------------------------------------------------------
# Override-record in-memory store (T051)
# ---------------------------------------------------------------------------
# Persistent storage for dual-approval override records.
# [FOLLOW-UP: US8 (badcases lifecycle) will persist these to the
# ``override_records`` DB table via ``set_override_record_sink`` so that
# audit trails survive process restarts. Until US8 ships, records live
# only in process memory and are LOST on restart.]
# Append-only list with a soft cap to prevent unbounded growth in long-
# running processes (rate-limiting note: no per-process rate cap; callers
# should enforce their own limits).
_MAX_OVERRIDE_RECORDS = 1000
_OVERRIDE_RECORDS: list[dict[str, object]] = []


def get_override_records() -> list[dict[str, object]]:
    """Return a copy of all recorded override records (test/inspection only)."""
    return list(_OVERRIDE_RECORDS)


def reset_override_records() -> None:
    """Clear the override-records store (test/inspection only)."""
    _OVERRIDE_RECORDS.clear()


def set_override_record_sink(sink: Callable[[dict[str, object]], None] | None) -> None:
    """Register a persistence sink (used by US8 badcases integration).

    When set, every successfully validated override record is forwarded to
    ``sink(record)`` AFTER being appended to the in-memory list. Pass
    ``None`` to clear. The sink must not raise; if it does the in-memory
    append still stands and the exception is swallowed (audit failures
    must never block the CLI exit).
    """
    global _override_sink
    _override_sink = sink


_override_sink: Callable[[dict[str, object]], None] | None = None


# ---------------------------------------------------------------------------
# `run` subcommand (T040 + T048)
# ---------------------------------------------------------------------------


def cmd_run(args: argparse.Namespace) -> int:
    spec_dir = Path(args.spec_dir) if args.spec_dir else _DEFAULT_SPEC_DIR
    suite = args.suite or "golden"
    if suite not in _VALID_SUITES:
        print(
            f"[eval] invalid --suite {suite!r}; expected one of {sorted(_VALID_SUITES)}",
            file=sys.stderr,
        )
        return 2
    sync_mode = getattr(args, "sync_langsmith", "never") or "never"
    if sync_mode not in _VALID_SYNC_LANGSMITH:
        print(
            f"[eval] invalid --sync-langsmith {sync_mode!r}; expected one of {sorted(_VALID_SYNC_LANGSMITH)}",
            file=sys.stderr,
        )
        return 2
    env = (args.env or "ci").strip().lower()
    if env not in _VALID_ENVS:
        print(
            f"[eval] invalid --env {env!r}; expected one of {sorted(_VALID_ENVS)}",
            file=sys.stderr,
        )
        return 2
    # CI smoke contract: the canonical CLI requires explicit output paths
    # OR --json. Without either, refuse with exit 2 (invalid args).
    if not args.json and not args.report_out and not args.markdown_out:
        print(
            "[eval] --report-out / --markdown-out / --json is required "
            "to capture eval artifacts (FR-013); refusing with exit 2",
            file=sys.stderr,
        )
        return 2
    nightly = bool(args.nightly)
    real_model = bool(args.real_model)
    nightly_real_model = nightly and real_model

    cases = load_golden_cases(spec_dir)
    if not cases:
        print(f"[eval] no golden cases found under {spec_dir}/golden/", file=sys.stderr)
        return 2

    if args.node:
        cases = [c for c in cases if c.node == args.node]
        if not cases:
            print(f"[eval] no cases match --node={args.node}", file=sys.stderr)
            return 2

    active_cases = [c for c in cases if c.status == "active"]
    print(
        f"[eval] loaded {len(cases)} cases ({len(active_cases)} active, "
        f"{len(cases) - len(active_cases)} stale); suite={suite} env={env}",
        file=sys.stderr,
    )

    # Budget check (T049): when nightly real-model is requested, evaluate
    # the cap BEFORE running. Exits 1 + status INCOMPLETE on exhaustion.
    budget_tokens = args.budget_tokens
    budget_cost = args.budget_cost_usd
    runner = EvalRunner(
        cases=cases,
        mode="real" if real_model else "mock",
        model_name=args.model_name
        or ("deepseek-v4-pro" if real_model else "mock-llm"),
        environment=env.upper(),
        release_stage="DEVELOPMENT",
        schema_version="v1",
        rubric_version=args.rubric_version or "unknown",
        branch=args.branch,
        nightly_real_model=nightly_real_model,
        budget_tokens=budget_tokens,
        budget_cost_usd=budget_cost,
    )
    within, reason = runner.check_budget()
    if nightly_real_model and not within:
        # Build a minimal INCOMPLETE report (no cases run).
        report = runner.build_incomplete_report(reason)
        args.langsmith_export_status = "DISABLED"
        args.langsmith_url = "unavailable"
        if args.markdown_out and args.report_out:
            write_req045_report_artifacts(
                report,
                json_path=Path(args.report_out),
                markdown_path=Path(args.markdown_out),
                suite=suite,
                dataset_version=f"{suite}-v1",
                langsmith_export_status="DISABLED",
            )
        elif args.markdown_out:
            _write_markdown(report, Path(args.markdown_out))
        elif args.report_out:
            _write_json_report(report, Path(args.report_out), args=args)
        payload = _build_cli_payload(report, args)
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(
                f"[eval] nightly budget exhausted: {reason}; status=INCOMPLETE",
                file=sys.stderr,
            )
        return 1

    report = asyncio.run(runner.run_all())
    # Apply source_revision override after run_all (run_all captures the
    # git-detected value during construction; we want to honor the CLI flag).
    if args.source_revision:
        try:
            report.source_revision = args.source_revision
        except Exception:  # dataclass frozen? ignore
            pass

    sync_status = "DISABLED"
    sync_url = "unavailable"
    sync_required_failed = False
    if sync_mode != "never":
        from app.eval.report import normalize_req045_report

        sync_payload = normalize_req045_report(
            report,
            suite=suite,
            dataset_version=f"{suite}-v1",
            artifacts={
                "json": str(args.report_out) if args.report_out else "",
                "markdown": str(args.markdown_out) if args.markdown_out else "",
            },
        )
        try:
            sync_result = sync_report_to_langsmith(
                sync_payload,
                mode=sync_mode,  # type: ignore[arg-type]
                project=None,
            )
        except LangSmithSyncError as exc:
            sync_status = "FAILED"
            sync_url = "unavailable"
            sync_required_failed = True
            print(f"[eval] required LangSmith sync failed: {exc}", file=sys.stderr)
        else:
            sync_status = sync_result.sync_status
            sync_url = sync_result.url
            if sync_result.error_message:
                print(
                    f"[eval] LangSmith sync status={sync_status}: {sync_result.error_message}",
                    file=sys.stderr,
                )
    args.langsmith_export_status = sync_status
    args.langsmith_url = sync_url

    # Print human-readable summary to stderr (so stdout can carry --json).
    if not args.json:
        print(f"[eval] status={report.status if hasattr(report, 'status') else 'COMPLETED'}", file=sys.stderr)
        print(f"[eval] total={report.total_cases} passed={report.passed_cases} failed={report.failed_cases} skipped={report.skipped_cases}", file=sys.stderr)

    # Write artifacts.
    if args.markdown_out and args.report_out:
        write_req045_report_artifacts(
            report,
            json_path=Path(args.report_out),
            markdown_path=Path(args.markdown_out),
            suite=suite,
            dataset_version=f"{suite}-v1",
            langsmith_export_status=sync_status,
            langsmith_url=sync_url,
        )
    elif args.markdown_out:
        _write_markdown(report, Path(args.markdown_out))
    elif args.report_out:
        _write_json_report(report, Path(args.report_out), args=args)

    # Emit JSON body to stdout.
    if args.json:
        payload = _build_cli_payload(report, args)
        print(json.dumps(payload, ensure_ascii=False))
    else:
        # Human-readable summary on stdout too, for ad-hoc inspection.
        print(
            f"Run: {report.run_id} status={getattr(report, 'status', 'COMPLETED')} "
            f"pass_rate={report.aggregate_pass_rate:.2%}",
        )

    if sync_required_failed:
        return 1
    # Exit code: 0 if all active cases pass; 4 (gate failed) otherwise.
    if report.failed_cases == 0:
        return 0
    return 4


def _build_cli_payload(report: "EvalReport", args: argparse.Namespace) -> dict[str, object]:
    """Build the canonical CLI JSON payload per contracts/eval-langsmith-cli.md."""
    # Prefer EvalReportModel fields when available; fall back to dataclass.
    try:
        artifacts = {
            "json": str(args.report_out) if args.report_out else "",
            "markdown": str(args.markdown_out) if args.markdown_out else "",
        }
        model = EvalReportModel.from_eval_report(report, artifacts=artifacts)
        return {
            "runId": str(model.run_id),
            "status": model.status,
            "sourceRevision": model.source_revision,
            "branch": model.branch,
            "environment": model.environment,
            "aggregatePassRate": model.aggregate_pass_rate,
            "knownRegressionRecall": model.known_regression_recall,
            "datasetVersion": f"{args.suite or 'golden'}-v1",
            "langsmithExportStatus": getattr(args, "langsmith_export_status", "DISABLED"),
            "langsmithUrl": getattr(args, "langsmith_url", "unavailable"),
            "staleCaseCount": model.stale_case_count,
            "artifacts": {
                "json": artifacts["json"],
                "markdown": artifacts["markdown"],
            },
            "startedAt": model.started_at,
            "completedAt": model.completed_at,
            "versionContext": model.version_context,
            "totalCases": model.total_cases,
            "passedCases": model.passed_cases,
            "failedCases": model.failed_cases,
            "skippedCases": model.skipped_cases,
            "model": model.model,
            "modelVersion": model.model_version,
        }
    except Exception as exc:  # pragma: no cover — defensive
        logger.warning("eval.cli.payload_build_failed", error=str(exc))
        return {
            "runId": str(report.run_id),
            "status": getattr(report, "status", "UNKNOWN"),
            "sourceRevision": getattr(report, "source_revision", "unknown"),
            "branch": getattr(report, "branch", "unknown"),
            "environment": getattr(report, "environment", "unknown"),
            "aggregatePassRate": getattr(report, "aggregate_pass_rate", 0.0),
            "knownRegressionRecall": getattr(report, "known_regression_recall", 1.0),
            "datasetVersion": f"{args.suite or 'golden'}-v1",
            "langsmithExportStatus": getattr(args, "langsmith_export_status", "DISABLED"),
            "langsmithUrl": getattr(args, "langsmith_url", "unavailable"),
            "staleCaseCount": getattr(report, "stale_case_count", 0),
            "artifacts": {
                "json": str(args.report_out) if args.report_out else "",
                "markdown": str(args.markdown_out) if args.markdown_out else "",
            },
        }


def _write_json_report(report: "EvalReport", path: Path, *, args: argparse.Namespace | None = None) -> None:
    """Write the JSON report artifact (EvalReportModel) to ``path``."""
    if args is not None:
        markdown_path = Path(getattr(args, "markdown_out", "") or path.with_suffix(".md"))
        write_req045_report_artifacts(
            report,
            json_path=path,
            markdown_path=markdown_path,
            suite=getattr(args, "suite", "golden") or "golden",
            dataset_version=f"{getattr(args, 'suite', 'golden') or 'golden'}-v1",
            langsmith_export_status=getattr(args, "langsmith_export_status", "DISABLED"),
            langsmith_url=getattr(args, "langsmith_url", "unavailable"),
        )
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    model = EvalReportModel.from_eval_report(report)
    path.write_text(model.to_json(), encoding="utf-8")


def _write_markdown(report: "EvalReport", path: Path) -> None:
    """Write the Markdown rendering to ``path``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    md = render_markdown_report(report)
    path.write_text(md, encoding="utf-8")


# ---------------------------------------------------------------------------
# `override-record` subcommand (T051)
# ---------------------------------------------------------------------------


def cmd_override_record(args: argparse.Namespace) -> str | int:
    """CLI entry for the dual-approval override command.

    Hard-fails (exit 3) when either the PM business owner or the
    technical owner signature is missing (FR-024).

    Returns:
        - the JSON payload string when ``--json`` is set
          (caller — typically ``main()`` — prints it to stdout and exits 0).
        - the int exit code (0) on plain-text success.

    Raises:
        PolicyViolation when dual approval / reason / evidence missing
        (caller converts to exit 3).
    """
    # Normalize ``json_output`` / ``json`` — programmatic callers may use
    # either attribute name (the test fixture uses ``json_output``).
    if not hasattr(args, "json") and hasattr(args, "json_output"):
        args.json = bool(args.json_output)
    payload = _build_override_record(args)
    if getattr(args, "json", False):
        # Return JSON body — caller prints it.
        return json.dumps(payload, ensure_ascii=False)
    print(f"Override recorded: {payload['overrideId']} for run {payload['runId']}")
    return 0


def _validate_evidence(raw: str) -> None:
    """Validate override evidence path/URL; raise PolicyViolation on bad input.

    Rules (governance — reviewer issue #4):
    - ``http(s)://`` URLs: reject loopback / private / link-local hosts to
      avoid exfiltration of override records to internal admin pages.
      Public DNS names and IPs are accepted.
    - ``file://`` URLs and absolute filesystem paths: accepted as-is (CI
      runners may legitimately reference ``/var/log/eval-report.md``).
    - Bare relative paths: reject ``..`` segments to prevent path traversal.
    - Any other scheme: rejected (avoid ``ftp://``, ``javascript:``, etc.).
    """
    parsed = urlparse(raw)
    if parsed.scheme in ("http", "https"):
        host = (parsed.hostname or "").lower()
        if host == "localhost":
            raise PolicyViolation(
                f"override evidence URL points to loopback {host!r}",
                environment="n/a",
                violations=["evidence_private_url"],
                sample_id="",
            )
        try:
            if ipaddress.ip_address(host).is_private:
                raise PolicyViolation(
                    f"override evidence URL points to private address {host!r}",
                    environment="n/a",
                    violations=["evidence_private_url"],
                    sample_id="",
                )
        except ValueError:
            # host is a DNS name, not an IP literal — assume public.
            pass
        return
    if parsed.scheme == "file":
        return
    if parsed.scheme == "":
        if ".." in Path(raw).parts:
            raise PolicyViolation(
                f"override evidence path contains '..': {raw!r}",
                environment="n/a",
                violations=["evidence_path_traversal"],
                sample_id="",
            )
        return
    raise PolicyViolation(
        f"override evidence scheme {parsed.scheme!r} not allowed "
        "(use http/https/file/relative path)",
        environment="n/a",
        violations=["evidence_bad_scheme"],
        sample_id="",
    )


def _build_override_record(args: argparse.Namespace) -> dict[str, object]:
    """Validate + build the override record; raise PolicyViolation on hard fail.

    The CLI-level wrapper (:func:`cmd_override_record`) catches this and
    emits the JSON error / exit-3. Programmatic callers can call
    :func:`_build_override_record` directly to get the dict.
    """
    if not args.pm_approver or not str(args.pm_approver).strip():
        raise PolicyViolation(
            "override requires pm_approver (FR-024)",
            environment="n/a",
            violations=["missing_pm_approver"],
            sample_id=str(args.run_id or ""),
        )
    if not args.technical_approver or not str(args.technical_approver).strip():
        raise PolicyViolation(
            "override requires technical_approver (FR-024)",
            environment="n/a",
            violations=["missing_technical_approver"],
            sample_id=str(args.run_id or ""),
        )
    if not args.reason or not str(args.reason).strip():
        raise PolicyViolation(
            "override requires reason (FR-024)",
            environment="n/a",
            violations=["missing_reason"],
            sample_id=str(args.run_id or ""),
        )
    if not args.evidence or not str(args.evidence).strip():
        raise PolicyViolation(
            "override requires evidence (FR-024)",
            environment="n/a",
            violations=["missing_evidence"],
            sample_id=str(args.run_id or ""),
        )
    gate = str(args.gate or "").strip()
    if gate not in _VALID_GATES:
        raise ValueError(
            f"invalid gate {gate!r}; expected one of {sorted(_VALID_GATES)}"
        )

    # Governance (reviewer issue #4): bound reason length + validate evidence
    # path / URL to refuse obvious abuse vectors. Hard-fail with policy
    # violation so the CLI exits 3 (not 2) — same as missing dual approval.
    if len(str(args.reason or "")) > 2000:
        raise PolicyViolation(
            "override reason exceeds 2000 character cap (governance)",
            environment="n/a",
            violations=["reason_too_long"],
            sample_id=str(args.run_id or ""),
        )
    _evidence_raw = str(args.evidence or "").strip()
    if _evidence_raw:
        try:
            _validate_evidence(_evidence_raw)
        except PolicyViolation as exc:
            # Re-raise with the actual run_id on the sample_id field.
            raise PolicyViolation(
                str(exc),
                environment=exc.environment,
                violations=exc.violations,
                sample_id=str(args.run_id or ""),
            ) from exc

    record: dict[str, object] = {
        "overrideId": f"override-{uuid4()}",
        "runId": str(args.run_id),
        "gate": gate,
        "pmApprover": str(args.pm_approver).strip(),
        "technicalApprover": str(args.technical_approver).strip(),
        "reason": str(args.reason).strip(),
        "evidenceRef": str(args.evidence).strip(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    _OVERRIDE_RECORDS.append(record)
    # Soft cap to prevent unbounded growth in long-running processes.
    if len(_OVERRIDE_RECORDS) > _MAX_OVERRIDE_RECORDS:
        del _OVERRIDE_RECORDS[: len(_OVERRIDE_RECORDS) - _MAX_OVERRIDE_RECORDS]
    # Forward to optional persistence sink (US8 wires this to badcases table).
    if _override_sink is not None:
        try:
            _override_sink(record)
        except Exception:  # pragma: no cover — sink must not block CLI
            logger.warning("eval.override_sink_failed", overrideId=record["overrideId"])
    logger.info(
        "eval.override_recorded",
        overrideId=record["overrideId"],
        runId=record["runId"],
        gate=record["gate"],
        pm=record["pmApprover"],
        tech=record["technicalApprover"],
    )
    return record


def cmd_langsmith_sync(args: argparse.Namespace) -> str | int:
    """Sync an existing REQ-045 local report to LangSmith."""
    report_path = Path(args.report)
    if not report_path.exists():
        raise ValueError(f"report not found: {report_path}")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    try:
        result = sync_report_to_langsmith(
            report,
            mode="require",
            project=args.project,
            export_policy_decision_id=args.destination_policy,
        )
    except LangSmithSyncError as exc:
        payload = {
            "runId": str(report.get("runId") or report.get("run_id") or "unknown"),
            "syncStatus": "FAILED",
            "project": args.project,
            "dataset": "unavailable",
            "experimentName": "unavailable",
            "url": "unavailable",
            "errorMessage": str(exc),
            "exportPolicyDecisionId": args.destination_policy,
        }
        if getattr(args, "json", False):
            print(json.dumps(payload, ensure_ascii=False))
        return 1
    payload = result.to_payload()
    if getattr(args, "json", False):
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(f"LangSmith sync {result.sync_status}: {result.url}")
    return 0


def cmd_export_audit(args: argparse.Namespace) -> int:
    """Audit whether a payload may be exported to an external destination."""

    sample_path = Path(args.sample)
    if not sample_path.exists():
        raise ValueError(f"sample not found: {sample_path}")
    payload = json.loads(sample_path.read_text(encoding="utf-8"))
    result = decide_export_policy(
        DestinationPolicyInput(
            destination=ExportDestination(args.destination),
            environment=Environment(args.env),
            requested_level=RepresentationLevel(args.representation),
            policy_version=args.policy_version,
            owner=args.owner,
            access_scope=args.access_scope,
            retention_days=args.retention_days,
            allowed_content_classes=tuple(args.allowed_content_class or ()),
            sample_rate=args.sample_rate,
            payload=payload,
        )
    )
    out = result.to_payload()
    if getattr(args, "json", False):
        print(json.dumps(out, ensure_ascii=False))
    elif result.allowed:
        print(
            "Export allowed: "
            f"{out['decision']['destination']} {out['decision']['representationLevel']}"
        )
    else:
        print(
            "Export blocked: "
            f"{out['decision']['blockedReason'] or out['decision']['representationLevel']}",
            file=sys.stderr,
        )
    return 0 if result.allowed else 3


def cmd_judge_calibrate(args: argparse.Namespace) -> int:
    labels_path = Path(args.labels)
    if not labels_path.exists():
        raise ValueError(f"labels not found: {labels_path}")
    labels = json.loads(labels_path.read_text(encoding="utf-8"))
    if not isinstance(labels, list):
        raise ValueError("labels must be a JSON array")
    rubric = calibrate_judge_rubric(
        labels,
        owner=args.owner,
        waiver_reason=args.waiver_reason,
    )
    payload = {
        "rubricId": rubric.rubric_id,
        "rubricVersion": rubric.version,
        "calibrationStatus": rubric.calibration_status.value,
        "humanLabelCount": rubric.human_label_count,
        "agreementRate": rubric.agreement_rate,
        "waiverReason": rubric.waiver_reason,
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(f"Judge calibration {payload['calibrationStatus']} agreement={rubric.agreement_rate:.2%}")
    return 0


def cmd_judge_run(args: argparse.Namespace) -> int:
    report_path = Path(args.report)
    if not report_path.exists():
        raise ValueError(f"report not found: {report_path}")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    rubric = default_judge_rubric(owner=args.owner, version=args.rubric_version)
    result = run_judge_cases(list(report.get("caseResults") or []), rubric=rubric)
    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    else:
        print(f"Judge verdicts: {len(result['verdicts'])} blocking={result['blockingEnabled']}")
    return 0


def cmd_experiment_compare(args: argparse.Namespace) -> int:
    baseline_path = Path(args.baseline)
    candidate_path = Path(args.candidate)
    if not baseline_path.exists():
        raise ValueError(f"baseline report not found: {baseline_path}")
    if not candidate_path.exists():
        raise ValueError(f"candidate report not found: {candidate_path}")
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    result = compare_experiments(
        baseline=baseline,
        candidate=candidate,
        min_quality_delta=args.min_quality_delta,
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    else:
        print(
            f"Comparison {result['comparisonId']}: {result['recommendation']} "
            f"quality_delta={result['qualityDelta']:.2%}"
        )
    return 0


def cmd_prompt_proposal_create(args: argparse.Namespace) -> int:
    proposal = create_prompt_proposal(
        source_run_ids=args.source_run_id,
        source_case_ids=args.source_case_id,
        target_graph=args.target_graph,
        target_node=args.target_node,
        candidate_fingerprint=args.candidate_fingerprint,
        expected_impact=args.expected_impact,
    )
    payload = proposal_to_payload(proposal)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(f"Prompt proposal {payload['proposalId']} {payload['status']}")
    return 0


def _load_prompt_proposal(path: str):
    return proposal_from_payload(json.loads(Path(path).read_text(encoding="utf-8")))


def cmd_prompt_proposal_compare(args: argparse.Namespace) -> int:
    proposal = compare_prompt_proposal(
        _load_prompt_proposal(args.proposal),
        comparison_run_id=args.comparison_run_id,
    )
    print(json.dumps(proposal_to_payload(proposal), ensure_ascii=False))
    return 0


def cmd_prompt_proposal_approve(args: argparse.Namespace) -> int:
    proposal = approve_prompt_proposal(_load_prompt_proposal(args.proposal), owner=args.owner)
    print(json.dumps(proposal_to_payload(proposal), ensure_ascii=False))
    return 0


def cmd_prompt_proposal_reject(args: argparse.Namespace) -> int:
    proposal = reject_prompt_proposal(
        _load_prompt_proposal(args.proposal),
        owner=args.owner,
        reason=args.reason,
    )
    print(json.dumps(proposal_to_payload(proposal), ensure_ascii=False))
    return 0


# ---------------------------------------------------------------------------
# argparse plumbing
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="app.eval.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)

    # ---- run subcommand ----
    run_p = sub.add_parser("run", help="Run the eval suite against golden cases")
    run_p.add_argument(
        "--suite",
        choices=sorted(_VALID_SUITES),
        default="golden",
        help="eval suite to run: golden (default) | nightly | regression",
    )
    run_p.add_argument(
        "--mode",
        choices=["mock", "real"],
        default=None,
        help="mock = stub LLM (default); real = call DeepSeek (burns quota)",
    )
    run_p.add_argument(
        "--node",
        default=None,
        help="filter cases by node id (e.g. interview.score)",
    )
    run_p.add_argument(
        "--spec-dir",
        default=None,
        help=f"path to spec dir (default: {_DEFAULT_SPEC_DIR})",
    )
    run_p.add_argument(
        "--report-out",
        default=None,
        help="path to write JSON report",
    )
    run_p.add_argument(
        "--markdown-out",
        default=None,
        help="path to write Markdown report",
    )
    run_p.add_argument(
        "--model-name",
        default=None,
        help="override model name in report",
    )
    # T048 new flags.
    run_p.add_argument(
        "--env",
        choices=sorted(_VALID_ENVS),
        default="ci",
        help="environment label (local | ci | staging | production)",
    )
    run_p.add_argument(
        "--source-revision",
        default=None,
        help="git SHA / source revision to stamp on the report",
    )
    run_p.add_argument(
        "--branch",
        default=None,
        help="git branch to stamp on the report",
    )
    run_p.add_argument(
        "--real-model",
        action="store_true",
        help="use real LLM (DeepSeek) instead of stub",
    )
    run_p.add_argument(
        "--nightly",
        action="store_true",
        help="run in nightly mode (enables budget check)",
    )
    run_p.add_argument(
        "--budget-tokens",
        type=int,
        default=None,
        help="nightly token budget to check before running",
    )
    run_p.add_argument(
        "--budget-cost-usd",
        type=float,
        default=None,
        help="nightly cost budget (USD) to check before running",
    )
    run_p.add_argument(
        "--rubric-version",
        default="unknown",
        help="rubric version label to stamp on the report",
    )
    run_p.add_argument(
        "--json",
        action="store_true",
        dest="json",
        help="emit machine-readable JSON to stdout",
    )
    run_p.add_argument(
        "--sync-langsmith",
        choices=sorted(_VALID_SYNC_LANGSMITH),
        default="never",
        help="LangSmith sync mode: never | auto | require",
    )
    run_p.set_defaults(func=cmd_run)

    # ---- langsmith-sync subcommand ----
    ls_p = sub.add_parser(
        "langsmith-sync",
        help="Sync an existing REQ-045 local eval report to LangSmith",
    )
    ls_p.add_argument("--report", required=True, help="path to REQ-045 eval-report.json")
    ls_p.add_argument("--project", required=True, help="LangSmith project name")
    ls_p.add_argument(
        "--destination-policy",
        required=False,
        default=None,
        help="export policy decision id or version authorizing the sync",
    )
    ls_p.add_argument("--json", action="store_true", dest="json")
    ls_p.set_defaults(func=cmd_langsmith_sync)

    # ---- export-audit subcommand ----
    audit_p = sub.add_parser(
        "export-audit",
        help="Audit destination export policy for a sample payload",
    )
    audit_p.add_argument("--sample", required=True, help="path to JSON sample payload")
    audit_p.add_argument(
        "--destination",
        choices=[item.value for item in ExportDestination],
        required=True,
    )
    audit_p.add_argument(
        "--env",
        choices=[item.value for item in Environment],
        required=True,
    )
    audit_p.add_argument(
        "--representation",
        choices=[item.value for item in RepresentationLevel],
        required=True,
    )
    audit_p.add_argument("--policy-version", default="req045.v1")
    audit_p.add_argument("--owner", default=None)
    audit_p.add_argument("--access-scope", default=None)
    audit_p.add_argument("--retention-days", type=int, default=None)
    audit_p.add_argument("--allowed-content-class", action="append", default=[])
    audit_p.add_argument("--sample-rate", type=float, default=1.0)
    audit_p.add_argument("--json", action="store_true", dest="json")
    audit_p.set_defaults(func=cmd_export_audit)

    # ---- judge-calibrate subcommand ----
    judge_cal_p = sub.add_parser(
        "judge-calibrate",
        help="Calibrate the REQ-045 judge rubric against human labels",
    )
    judge_cal_p.add_argument("--labels", required=True, help="path to labels JSON array")
    judge_cal_p.add_argument("--owner", required=True, help="rubric owner")
    judge_cal_p.add_argument("--waiver-reason", default=None)
    judge_cal_p.add_argument("--json", action="store_true", dest="json")
    judge_cal_p.set_defaults(func=cmd_judge_calibrate)

    # ---- judge-run subcommand ----
    judge_run_p = sub.add_parser(
        "judge-run",
        help="Run the deterministic REQ-045 judge over an eval report",
    )
    judge_run_p.add_argument("--report", required=True, help="path to REQ-045 eval report")
    judge_run_p.add_argument("--owner", default="ai-ops")
    judge_run_p.add_argument("--rubric-version", default="rubric.req045.v1")
    judge_run_p.add_argument("--json", action="store_true", dest="json")
    judge_run_p.set_defaults(func=cmd_judge_run)

    # ---- experiment-compare subcommand ----
    compare_p = sub.add_parser(
        "experiment-compare",
        help="Compare baseline and candidate REQ-045 eval reports",
    )
    compare_p.add_argument("--baseline", required=True, help="baseline eval report JSON")
    compare_p.add_argument("--candidate", required=True, help="candidate eval report JSON")
    compare_p.add_argument("--min-quality-delta", type=float, default=0.0)
    compare_p.add_argument("--json", action="store_true", dest="json")
    compare_p.set_defaults(func=cmd_experiment_compare)

    # ---- prompt-proposal subcommands ----
    proposal_p = sub.add_parser(
        "prompt-proposal",
        help="Create or review REQ-045 prompt improvement proposals",
    )
    proposal_sub = proposal_p.add_subparsers(dest="proposal_cmd", required=True)
    proposal_create = proposal_sub.add_parser("create", help="Create a prompt proposal")
    proposal_create.add_argument("--source-run-id", action="append", required=True)
    proposal_create.add_argument("--source-case-id", action="append", required=True)
    proposal_create.add_argument("--target-graph", required=True)
    proposal_create.add_argument("--target-node", required=True)
    proposal_create.add_argument("--candidate-fingerprint", required=True)
    proposal_create.add_argument("--expected-impact", required=True)
    proposal_create.add_argument("--json", action="store_true", dest="json")
    proposal_create.set_defaults(func=cmd_prompt_proposal_create)
    proposal_compare = proposal_sub.add_parser("compare", help="Attach comparison evidence")
    proposal_compare.add_argument("--proposal", required=True)
    proposal_compare.add_argument("--comparison-run-id", required=True)
    proposal_compare.set_defaults(func=cmd_prompt_proposal_compare)
    proposal_approve = proposal_sub.add_parser("approve", help="Approve a compared proposal")
    proposal_approve.add_argument("--proposal", required=True)
    proposal_approve.add_argument("--owner", required=True)
    proposal_approve.set_defaults(func=cmd_prompt_proposal_approve)
    proposal_reject = proposal_sub.add_parser("reject", help="Reject a proposal")
    proposal_reject.add_argument("--proposal", required=True)
    proposal_reject.add_argument("--owner", required=True)
    proposal_reject.add_argument("--reason", required=True)
    proposal_reject.set_defaults(func=cmd_prompt_proposal_reject)

    # ---- override-record subcommand ----
    or_p = sub.add_parser(
        "override-record",
        help="Record a dual-approval override for an eval gate (FR-024)",
    )
    or_p.add_argument("--run-id", required=True, help="target eval run id")
    or_p.add_argument(
        "--gate",
        required=True,
        choices=sorted(_VALID_GATES),
        help="gate being overridden",
    )
    # Mark the dual-approval fields + reason + evidence as optional at
    # argparse level so we can produce exit-3 (policy violation) on
    # missing dual approval instead of exit-2 (invalid args). Per FR-024,
    # the dual-approval failure is a policy violation, not an arg error.
    or_p.add_argument(
        "--pm-approver",
        required=False,
        default=None,
        help="PM business owner name",
    )
    or_p.add_argument(
        "--technical-approver",
        required=False,
        default=None,
        help="technical owner name",
    )
    or_p.add_argument(
        "--reason",
        required=False,
        default=None,
        help="override reason text",
    )
    or_p.add_argument(
        "--evidence",
        required=False,
        default=None,
        help="path or URL to override evidence (eval-report, RFC, etc.)",
    )
    or_p.add_argument(
        "--json",
        action="store_true",
        dest="json",
        help="emit JSON to stdout",
    )
    or_p.set_defaults(func=cmd_override_record)

    args = parser.parse_args(argv)
    # Default --mode from --real-model.
    if hasattr(args, "mode") and args.mode is None:
        args.mode = "real" if getattr(args, "real_model", False) else "mock"

    try:
        result = args.func(args)
    except PolicyViolation as exc:
        # Hard fail (exit 3).
        if getattr(args, "json", False):
            print(
                json.dumps(
                    {
                        "error": "policy_violation",
                        "code": 3,
                        "message": str(exc),
                        "violations": list(exc.violations),
                    },
                    ensure_ascii=False,
                )
            )
        else:
            print(f"[eval] policy violation: {exc}", file=sys.stderr)
        return 3
    except ValueError as exc:
        # Invalid args (e.g. bad gate).
        if getattr(args, "json", False):
            print(json.dumps({"error": "invalid_args", "message": str(exc)}, ensure_ascii=False))
        else:
            print(f"[eval] invalid args: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # pragma: no cover — defensive
        logger.exception("eval.cli.unexpected_error", error=str(exc))
        print(f"[eval] unexpected error: {exc}", file=sys.stderr)
        return 1

    # cmd_override_record returns the JSON string when --json set;
    # cmd_run returns an int exit code. Convert if needed.
    if isinstance(result, str):
        print(result)
        return 0
    return int(result)


if __name__ == "__main__":
    sys.exit(main())
