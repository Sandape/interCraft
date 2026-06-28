"""CLI entrypoint for the REQ-033 redaction audit (T028, US10).

Implements the contract documented in
``specs/033-eval-pm-dashboard/contracts/eval-langsmith-cli.md`` §Redaction
Audit:

  python -m app.modules.telemetry_contracts.redaction audit \\
      --environment production \\
      --sample docs/evidence/<run_id>/export-sample.json \\
      --out docs/evidence/<run_id>/redaction-check.md \\
      [--json]

Behavior:

- Reads the sample JSON payload (a single export-payload-shaped dict OR
  a list of such dicts).
- Routes each sample through :func:`app.eval.export_policy.enforce_export_policy`
  to detect forbidden production content (FR-032).
- Writes a Markdown audit report to ``--out`` (per
  ``docs/evidence/033-eval-pm-dashboard/redaction-check-template.md``).
- With ``--json``, emits the machine-readable audit summary to stdout.
- Exit codes per the contract:
  - 0  — all samples PASSED.
  - 1  — operational failure (file not found, JSON parse error, IO).
  - 2  — invalid arguments (missing env, unknown flag, bad env value).
  - 3  — policy violation (any forbidden production content detected).

Warnings (deprecation / non-fatal notes) go to stderr.

US6 LangSmith sync work will call :func:`app.eval.export_policy.
prepare_export_payload` (not this CLI); this CLI exists for the manual /
CI redaction audit required by FR-035 + SC-008.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

import structlog

from app.eval.export_policy import (
    FORBIDDEN_PRODUCTION_KEYS,
    PolicyViolation,
    enforce_export_policy,
    find_forbidden_keys,
)
from app.modules.telemetry_contracts.redaction import (
    audit_redaction,
    production_default_context,
)

logger = structlog.get_logger("telemetry.redaction_cli")

VALID_ENVIRONMENTS: frozenset[str] = frozenset(
    {"local", "ci", "staging", "production", "dev", "prod"}
)


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SampleAudit:
    """Per-sample audit record."""

    sample_id: str
    privacy_class: str
    redaction_status: str
    verdict: str
    violations: list[str]
    notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class AuditReport:
    """Aggregate audit report."""

    audit_id: str
    environment: str
    policy_version: str
    sample_count: int
    forbidden_content_failures: int
    result: str
    evidence_ref: str
    samples: list[SampleAudit]
    timestamp: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "auditId": self.audit_id,
            "environment": self.environment.upper(),
            "policyVersion": self.policy_version,
            "sampleCount": self.sample_count,
            "forbiddenContentFailures": self.forbidden_content_failures,
            "result": self.result,
            "evidenceRef": self.evidence_ref,
            "samples": [
                {
                    "sampleId": s.sample_id,
                    "privacyClass": s.privacy_class,
                    "redactionStatus": s.redaction_status,
                    "verdict": s.verdict,
                    "violations": list(s.violations),
                    "notes": list(s.notes),
                }
                for s in self.samples
            ],
            "timestamp": self.timestamp,
        }


# ---------------------------------------------------------------------------
# Core audit logic (pure, callable from tests)
# ---------------------------------------------------------------------------


def _audit_id(now: datetime | None = None) -> str:
    """Generate a deterministic-shaped audit id.

    Format: ``redaction-YYYYMMDD-NNN`` (timestamp-only for now; the CLI
    does not guarantee global uniqueness — that's the caller's job).
    """
    now = now or datetime.now(UTC)
    return now.strftime("redaction-%Y%m%d-%H%M%S")


def _normalize_samples(raw: Any) -> list[dict[str, Any]]:
    """Accept either a single dict or a list of dicts as the sample input."""
    if isinstance(raw, list):
        return [s for s in raw if isinstance(s, dict)]
    if isinstance(raw, dict):
        # Heuristic: if it has a 'samples' list, expand it; otherwise
        # treat the dict as a single sample.
        if isinstance(raw.get("samples"), list):
            return [s for s in raw["samples"] if isinstance(s, dict)]
        return [raw]
    raise ValueError(f"sample JSON must be dict or list of dicts, got {type(raw).__name__}")


def audit_samples(
    samples: Iterable[dict[str, Any]],
    *,
    environment: str,
    policy_version: str = "v1",
    evidence_ref: str = "",
    now: datetime | None = None,
) -> AuditReport:
    """Run the redaction audit over ``samples``.

    Pure function — no file IO. CLI entry point wraps this and writes the
    Markdown + JSON outputs.
    """
    norm_env = environment.strip().lower()
    now = now or datetime.now(UTC)
    sample_list = list(samples)
    sample_audits: list[SampleAudit] = []
    failure_count = 0

    for idx, sample in enumerate(sample_list):
        sample_id = str(sample.get("event_id") or sample.get("case_id") or f"sample-{idx:03d}")
        privacy_class = str(sample.get("privacy_class") or "UNKNOWN")
        redaction_status = str(sample.get("redaction_status") or "NOT_REQUIRED")
        try:
            enforce_export_policy(sample, norm_env, sample_id=sample_id)
            verdict = "PASSED"
            violations: list[str] = []
            notes: list[str] = []
        except PolicyViolation as exc:
            verdict = "FAILED"
            violations = list(exc.violations)
            notes = [str(exc)]
            failure_count += 1

        sample_audits.append(
            SampleAudit(
                sample_id=sample_id,
                privacy_class=privacy_class,
                redaction_status=redaction_status,
                verdict=verdict,
                violations=violations,
                notes=notes,
            )
        )

    overall = "PASSED" if failure_count == 0 else "FAILED"
    return AuditReport(
        audit_id=_audit_id(now),
        environment=norm_env,
        policy_version=policy_version,
        sample_count=len(sample_list),
        forbidden_content_failures=failure_count,
        result=overall,
        evidence_ref=evidence_ref,
        samples=sample_audits,
        timestamp=now.isoformat(),
    )


def render_markdown(report: AuditReport) -> str:
    """Render the audit report as Markdown for ``--out``.

    Format follows ``docs/evidence/033-eval-pm-dashboard/
    redaction-check-template.md``.
    """
    lines: list[str] = []
    lines.append(f"# Redaction Audit Report — {report.environment.upper()}")
    lines.append("")
    lines.append(f"- **audit_id**: `{report.audit_id}`")
    lines.append(f"- **environment**: `{report.environment.upper()}`")
    lines.append(f"- **policy_version**: `{report.policy_version}`")
    lines.append(f"- **sample_count**: `{report.sample_count}`")
    lines.append(f"- **forbidden_content_failures**: `{report.forbidden_content_failures}`")
    lines.append(f"- **timestamp**: `{report.timestamp}`")
    if report.evidence_ref:
        lines.append(f"- **evidence_ref**: `{report.evidence_ref}`")
    lines.append("")
    lines.append("## Samples")
    lines.append("")
    lines.append("| sample_id | privacy_class | redaction_status | verdict | violations |")
    lines.append("|---|---|---|---|---|")
    for s in report.samples:
        verdict_icon = "PASS" if s.verdict == "PASSED" else "FAIL"
        violations_str = ", ".join(s.violations) if s.violations else "—"
        lines.append(
            f"| `{s.sample_id}` | {s.privacy_class} | {s.redaction_status} "
            f"| {verdict_icon} | {violations_str} |"
        )
    lines.append("")
    lines.append(f"## Overall Result")
    lines.append("")
    lines.append(f"**{report.result}** — {report.forbidden_content_failures} of "
                 f"{report.sample_count} samples failed the redaction audit.")
    lines.append("")
    lines.append(f"_forbidden keys checked: {sorted(FORBIDDEN_PRODUCTION_KEYS)}_")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.modules.telemetry_contracts.redaction audit",
        description="Run a redaction audit on a JSON sample of export payloads.",
    )
    parser.add_argument(
        "--environment",
        required=True,
        choices=sorted(VALID_ENVIRONMENTS),
        help="Target environment for the audit.",
    )
    parser.add_argument(
        "--sample",
        required=True,
        type=Path,
        help="Path to the sample JSON file (dict or list of dicts).",
    )
    parser.add_argument(
        "--out",
        required=True,
        type=Path,
        help="Path to write the Markdown audit report.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON summary to stdout.",
    )
    parser.add_argument(
        "--reviewer",
        default="",
        help="Reviewer name to record in the audit report (optional).",
    )
    return parser


def cmd_audit(args: argparse.Namespace) -> int:
    sample_path: Path = args.sample
    out_path: Path = args.out
    environment: str = args.environment

    if not sample_path.exists():
        print(f"[redaction_cli] sample file not found: {sample_path}", file=sys.stderr)
        return 1

    try:
        raw = json.loads(sample_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"[redaction_cli] JSON parse error in {sample_path}: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"[redaction_cli] read failure on {sample_path}: {exc}", file=sys.stderr)
        return 1

    try:
        samples = _normalize_samples(raw)
    except ValueError as exc:
        print(f"[redaction_cli] {exc}", file=sys.stderr)
        return 2

    if not samples:
        print("[redaction_cli] no samples found in input", file=sys.stderr)
        return 2

    report = audit_samples(
        samples,
        environment=environment,
        policy_version="v1",
        evidence_ref=str(out_path),
    )

    # Write Markdown report.
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(render_markdown(report), encoding="utf-8")
    except OSError as exc:
        print(f"[redaction_cli] failed to write {out_path}: {exc}", file=sys.stderr)
        return 1

    # Emit JSON summary if requested.
    if args.json:
        payload = report.to_dict()
        if args.reviewer:
            payload["reviewer"] = args.reviewer
        print(json.dumps(payload, default=str, ensure_ascii=False))

    # Return exit code per contract.
    if report.result == "FAILED":
        return 3
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return cmd_audit(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())


__all__ = [
    "AuditReport",
    "SampleAudit",
    "VALID_ENVIRONMENTS",
    "audit_samples",
    "cmd_audit",
    "main",
    "render_markdown",
]