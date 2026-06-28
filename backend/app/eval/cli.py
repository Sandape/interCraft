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
from app.eval.golden_loader import load_golden_cases
from app.eval.report import EvalReportModel, render_markdown_report
from app.eval.runner import EvalReport, EvalRunner

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
        if args.markdown_out:
            _write_markdown(report, Path(args.markdown_out))
        if args.report_out:
            _write_json_report(report, Path(args.report_out))
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

    # Print human-readable summary to stderr (so stdout can carry --json).
    if not args.json:
        print(f"[eval] status={report.status if hasattr(report, 'status') else 'COMPLETED'}", file=sys.stderr)
        print(f"[eval] total={report.total_cases} passed={report.passed_cases} failed={report.failed_cases} skipped={report.skipped_cases}", file=sys.stderr)

    # Write artifacts.
    if args.markdown_out:
        _write_markdown(report, Path(args.markdown_out))
    if args.report_out:
        _write_json_report(report, Path(args.report_out))

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
            "staleCaseCount": getattr(report, "stale_case_count", 0),
            "artifacts": {
                "json": str(args.report_out) if args.report_out else "",
                "markdown": str(args.markdown_out) if args.markdown_out else "",
            },
        }


def _write_json_report(report: "EvalReport", path: Path) -> None:
    """Write the JSON report artifact (EvalReportModel) to ``path``."""
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
    run_p.set_defaults(func=cmd_run)

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