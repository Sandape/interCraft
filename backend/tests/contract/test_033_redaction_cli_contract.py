"""REQ-033 US10 — redaction / retention CLI contract tests (T027).

Pins down the CLI surface documented in
``specs/033-eval-pm-dashboard/contracts/eval-langsmith-cli.md``. The
test invokes the CLI modules in-process (no subprocess) so failures
surface as a single ``pytest`` failure rather than a process exit
mismatch.

Exit-code matrix:

- ``0`` — PASSED.
- ``1`` — operational failure (file not found, IO error).
- ``2`` — invalid arguments (unknown env / no samples / unparseable).
- ``3`` — policy violation (any forbidden production content detected).

Note: exit code ``4`` is reserved for the *eval gate* (CLI run command
under ``app.eval.cli``) — redaction/retention do not use it. This
contract test only checks the redaction/retention subset.

JSON shape sanity:

- ``auditId``, ``environment`` (UPPER), ``policyVersion``, ``sampleCount``,
  ``forbiddenContentFailures``, ``result``, ``evidenceRef``.
- Retention check: ``environment``, ``checkedRows``, ``expiredCount``,
  ``earliestExpiredAt``, ``earliestTraceId``, ``dryRun``,
  ``policyVersion``, ``nextCleanupAt``.
"""
from __future__ import annotations

import argparse
import io
import json
import subprocess
import sys
from contextlib import redirect_stderr, redirect_stdout
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

pytestmark = pytest.mark.contract

from app.modules.telemetry_contracts.redaction_cli import (
    AuditReport,
    SampleAudit,
    VALID_ENVIRONMENTS as REDACTION_VALID_ENVIRONMENTS,
    audit_samples,
    cmd_audit,
    main as redaction_main,
    render_markdown,
)
from app.modules.telemetry_contracts.retention_cli import (
    RetentionCheckReport,
    TraceRunRefRow,
    VALID_ENVIRONMENTS as RETENTION_VALID_ENVIRONMENTS,
    check_retention,
    cmd_check,
    main as retention_main,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_sample(tmp_path: Path, payload) -> Path:
    path = tmp_path / "export-sample.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _run_redaction_cli(
    *,
    environment: str,
    sample_path: Path,
    out_path: Path,
    json_flag: bool = False,
    reviewer: str = "",
) -> tuple[int, str, str]:
    """Invoke ``cmd_audit`` with captured stdout / stderr."""
    buf_out = io.StringIO()
    buf_err = io.StringIO()
    args = argparse.Namespace(
        environment=environment,
        sample=sample_path,
        out=out_path,
        json=json_flag,
        reviewer=reviewer,
    )
    with redirect_stdout(buf_out), redirect_stderr(buf_err):
        rc = cmd_audit(args)
    return rc, buf_out.getvalue(), buf_err.getvalue()


def _run_retention_cli(
    *,
    environment: str,
    json_flag: bool = True,
    dry_run: bool = True,
) -> tuple[int, str, str]:
    """Invoke ``cmd_check`` with captured stdout / stderr."""
    buf_out = io.StringIO()
    buf_err = io.StringIO()
    args = argparse.Namespace(
        environment=environment,
        json=json_flag,
        dry_run=dry_run,
    )
    with redirect_stdout(buf_out), redirect_stderr(buf_err):
        rc = cmd_check(args)
    return rc, buf_out.getvalue(), buf_err.getvalue()


# ---------------------------------------------------------------------------
# Happy path — JSON shape
# ---------------------------------------------------------------------------


def test_redaction_cli_passed_produces_exit_0_and_json_shape(tmp_path: Path) -> None:
    """Synthetic CI payload → exit 0 + JSON matches the contract shape."""
    sample = {
        "event_id": "evt-001",
        "environment": "ci",
        "privacy_class": "PUBLIC_METADATA",
        "redaction_status": "NOT_REQUIRED",
        "properties": {"case_id": "c.001", "score": 9.0},
    }
    sample_path = _write_sample(tmp_path, sample)
    out_path = tmp_path / "redaction-check.md"

    rc, out, err = _run_redaction_cli(
        environment="ci", sample_path=sample_path, out_path=out_path, json_flag=True
    )
    assert rc == 0
    assert err == ""  # no warnings on the happy path
    body = json.loads(out)
    # Contract shape per spec.
    for key in (
        "auditId",
        "environment",
        "policyVersion",
        "sampleCount",
        "forbiddenContentFailures",
        "result",
        "evidenceRef",
    ):
        assert key in body, f"missing contract key {key}"
    assert body["environment"] == "CI"
    assert body["sampleCount"] == 1
    assert body["forbiddenContentFailures"] == 0
    assert body["result"] == "PASSED"
    assert body["evidenceRef"] == str(out_path)
    # Markdown file was written.
    assert out_path.exists()
    md = out_path.read_text(encoding="utf-8")
    assert "PASSED" in md
    assert "evt-001" in md


def test_redaction_cli_failed_production_exits_3(tmp_path: Path) -> None:
    """Forbidden production resume content → exit 3 + JSON FAILED."""
    sample = {
        "event_id": "evt-bad-001",
        "environment": "production",
        "privacy_class": "PUBLIC_METADATA",
        "redaction_status": "PENDING",
        "properties": {
            "case_id": "case.prod.001",
            "resume_text": "raw sensitive content",
        },
    }
    sample_path = _write_sample(tmp_path, sample)
    out_path = tmp_path / "redaction-check.md"

    rc, out, err = _run_redaction_cli(
        environment="production",
        sample_path=sample_path,
        out_path=out_path,
        json_flag=True,
    )
    assert rc == 3
    body = json.loads(out)
    assert body["forbiddenContentFailures"] >= 1
    assert body["result"] == "FAILED"
    assert body["environment"] == "PRODUCTION"
    # Markdown should also mark this as FAIL.
    md = out_path.read_text(encoding="utf-8")
    assert "FAILED" in md
    assert "resume_text" in md


def test_redaction_cli_list_of_samples_aggregates(tmp_path: Path) -> None:
    """A list of samples is audited; the JSON aggregates verdicts."""
    sample = [
        {
            "event_id": "evt-ok",
            "environment": "ci",
            "properties": {"score": 9},
        },
        {
            "event_id": "evt-bad",
            "environment": "production",
            "properties": {"resume_text": "x"},
        },
    ]
    sample_path = _write_sample(tmp_path, sample)
    out_path = tmp_path / "redaction-check.md"

    rc, out, _ = _run_redaction_cli(
        environment="production",
        sample_path=sample_path,
        out_path=out_path,
        json_flag=True,
    )
    assert rc == 3  # mixed bag → one forbidden → FAILED
    body = json.loads(out)
    assert body["sampleCount"] == 2
    assert body["forbiddenContentFailures"] >= 1
    # Per-sample shape.
    assert len(body["samples"]) == 2


# ---------------------------------------------------------------------------
# Exit codes — invalid args (2), missing file (1), unparseable (1)
# ---------------------------------------------------------------------------


def test_redaction_cli_missing_file_exits_1(tmp_path: Path) -> None:
    out_path = tmp_path / "redaction-check.md"
    rc, _, err = _run_redaction_cli(
        environment="production", sample_path=tmp_path / "missing.json", out_path=out_path
    )
    assert rc == 1
    assert "not found" in err.lower()


def test_redaction_cli_unparseable_json_exits_1(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{not-json", encoding="utf-8")
    out_path = tmp_path / "redaction-check.md"
    rc, _, err = _run_redaction_cli(
        environment="production", sample_path=bad, out_path=out_path
    )
    assert rc == 1
    assert "json" in err.lower() or "parse" in err.lower()


def test_redaction_cli_unknown_env_exits_2(tmp_path: Path) -> None:
    """Invalid env string is rejected by argparse (exit 2)."""
    sample_path = _write_sample(tmp_path, {})
    out_path = tmp_path / "redaction-check.md"
    with pytest.raises(SystemExit) as exc_info:
        redaction_main(
            [
                "--environment", "moon",
                "--sample", str(sample_path),
                "--out", str(out_path),
                "--json",
            ]
        )
    assert exc_info.value.code == 2


def test_redaction_cli_no_samples_exits_2(tmp_path: Path) -> None:
    sample_path = _write_sample(tmp_path, [])
    out_path = tmp_path / "redaction-check.md"
    rc, _, err = _run_redaction_cli(
        environment="production", sample_path=sample_path, out_path=out_path
    )
    assert rc == 2
    assert "no samples" in err.lower()


# ---------------------------------------------------------------------------
# ``--json`` flag is machine-readable
# ---------------------------------------------------------------------------


def test_redaction_cli_json_flag_emits_valid_json(tmp_path: Path) -> None:
    """``--json`` emits a JSON document parseable by ``json.loads``."""
    sample_path = _write_sample(
        tmp_path, {"environment": "staging", "properties": {"score": 9}}
    )
    out_path = tmp_path / "redaction-check.md"
    rc, out, _ = _run_redaction_cli(
        environment="staging", sample_path=sample_path, out_path=out_path, json_flag=True
    )
    assert rc == 0
    # JSON must parse without errors.
    body = json.loads(out)
    assert body["environment"] == "STAGING"
    assert body["result"] == "PASSED"


def test_redaction_cli_without_json_emits_no_stdout_json(tmp_path: Path) -> None:
    """Without ``--json`` the CLI does not emit a JSON document to stdout."""
    sample_path = _write_sample(
        tmp_path, {"environment": "staging", "properties": {"score": 9}}
    )
    out_path = tmp_path / "redaction-check.md"
    rc, out, _ = _run_redaction_cli(
        environment="staging", sample_path=sample_path, out_path=out_path, json_flag=False
    )
    assert rc == 0
    # stdout should be empty (no JSON emitted).
    assert out.strip() == ""


# ---------------------------------------------------------------------------
# Retention CLI
# ---------------------------------------------------------------------------


def test_retention_cli_check_exit_0_and_json_shape() -> None:
    """Empty store → exit 0 + valid JSON shape (no rows expired)."""
    rc, out, err = _run_retention_cli(environment="production", json_flag=True, dry_run=True)
    assert rc == 0
    body = json.loads(out)
    for key in (
        "environment",
        "checkedRows",
        "expiredCount",
        "earliestExpiredAt",
        "earliestTraceId",
        "dryRun",
        "policyVersion",
        "nextCleanupAt",
        "policyAction",
        "maxAgeDays",
        "timestamp",
    ):
        assert key in body, f"missing retention contract key {key}"
    assert body["environment"] == "PRODUCTION"
    assert body["checkedRows"] == 0
    assert body["expiredCount"] == 0
    assert body["dryRun"] is True  # FR-035a — production always dry-run
    assert body["policyAction"] == "delete"
    assert body["maxAgeDays"] == 30


def test_retention_cli_check_aggregation() -> None:
    """In-process check function aggregates expired rows correctly."""
    now = datetime(2026, 7, 1, 0, 0, 0, tzinfo=UTC)
    rows = [
        TraceRunRefRow(
            trace_id="trace-old",
            environment="production",
            privacy_class="REDACTED_SUMMARY",
            redaction_status="PASSED",
            retention_expires_at=now - timedelta(days=10),
        ),
        TraceRunRefRow(
            trace_id="trace-fresh",
            environment="production",
            privacy_class="REDACTED_SUMMARY",
            redaction_status="PASSED",
            retention_expires_at=now + timedelta(days=10),
        ),
    ]
    report = check_retention(rows, environment="production", now=now)
    assert report.environment == "production"
    assert report.checked_rows == 2
    assert report.expired_count == 1
    assert report.earliest_trace_id == "trace-old"
    assert report.dry_run is True  # production override


def test_retention_cli_production_always_dry_run() -> None:
    """``dry_run=False`` is overridden to True for production (FR-035a)."""
    now = datetime(2026, 7, 1, 0, 0, 0, tzinfo=UTC)
    rows = [
        TraceRunRefRow(
            trace_id="trace-1",
            environment="production",
            privacy_class="REDACTED_SUMMARY",
            redaction_status="PASSED",
            retention_expires_at=now - timedelta(days=5),
        ),
    ]
    report = check_retention(rows, environment="production", dry_run=False, now=now)
    assert report.dry_run is True


def test_retention_cli_staging_7_day_max_age() -> None:
    """Staging reports ``maxAgeDays=7`` and ``action=archive``."""
    report = check_retention([], environment="staging")
    assert report.max_age_days == 7
    assert report.policy_action == "archive"


def test_retention_cli_unknown_env_exits_2() -> None:
    with pytest.raises(SystemExit) as exc_info:
        retention_main(["--environment", "moon", "--json"])
    assert exc_info.value.code == 2


# ---------------------------------------------------------------------------
# Markdown rendering sanity
# ---------------------------------------------------------------------------


def test_redaction_markdown_template_has_required_sections() -> None:
    """The Markdown audit report contains all template-required sections."""
    report = AuditReport(
        audit_id="redaction-20260628-120000",
        environment="production",
        policy_version="v1",
        sample_count=2,
        forbidden_content_failures=1,
        result="FAILED",
        evidence_ref="docs/evidence/033-eval-pm-dashboard/redaction-check.md",
        samples=[
            SampleAudit(
                sample_id="evt-1",
                privacy_class="PUBLIC_METADATA",
                redaction_status="PENDING",
                verdict="PASSED",
                violations=[],
            ),
            SampleAudit(
                sample_id="evt-2",
                privacy_class="SENSITIVE_USER_CONTENT",
                redaction_status="FAILED",
                verdict="FAILED",
                violations=["resume_text"],
            ),
        ],
        timestamp=datetime(2026, 6, 28, 12, 0, 0, tzinfo=UTC).isoformat(),
    )
    md = render_markdown(report)
    assert "Redaction Audit Report" in md
    assert "audit_id" in md
    assert "PRODUCTION" in md
    assert "policy_version" in md
    assert "sample_count" in md
    assert "Samples" in md
    assert "evt-1" in md
    assert "evt-2" in md
    assert "FAILED" in md
    assert "Overall Result" in md


# ---------------------------------------------------------------------------
# Valid environments
# ---------------------------------------------------------------------------


def test_redaction_cli_valid_environments_include_required() -> None:
    for env in ("local", "ci", "staging", "production"):
        assert env in REDACTION_VALID_ENVIRONMENTS


def test_retention_cli_valid_environments_include_required() -> None:
    for env in ("local", "ci", "staging", "production"):
        assert env in RETENTION_VALID_ENVIRONMENTS


# ---------------------------------------------------------------------------
# Smoke — the real entry point runs and exits cleanly via ``python -m``
# ---------------------------------------------------------------------------


def test_redaction_cli_module_invocation_succeeds(tmp_path: Path) -> None:
    """End-to-end: ``python -m app.modules.telemetry_contracts.redaction_cli`` runs."""
    sample_path = _write_sample(
        tmp_path,
        [{"environment": "ci", "properties": {"score": 9}}],
    )
    out_path = tmp_path / "out.md"
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.modules.telemetry_contracts.redaction_cli",
            "--environment", "ci",
            "--sample", str(sample_path),
            "--out", str(out_path),
            "--json",
        ],
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).resolve().parents[2]),
        timeout=30,
    )
    assert proc.returncode == 0, proc.stderr
    body = json.loads(proc.stdout)
    assert body["result"] == "PASSED"


def test_retention_cli_module_invocation_succeeds() -> None:
    """End-to-end: ``python -m app.modules.telemetry_contracts.retention_cli`` runs."""
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.modules.telemetry_contracts.retention_cli",
            "--environment", "production",
            "--json",
        ],
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).resolve().parents[2]),
        timeout=30,
    )
    assert proc.returncode == 0, proc.stderr
    body = json.loads(proc.stdout)
    assert body["environment"] == "PRODUCTION"
    assert body["dryRun"] is True