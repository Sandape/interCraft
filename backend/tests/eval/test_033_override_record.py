"""REQ-033 US5 — Dual-approval override record tests (T046).

Locks the override-record CLI contract from
``specs/033-eval-pm-dashboard/contracts/eval-langsmith-cli.md`` and
FR-024 (dual approval mandatory for baseline refresh / emergency
override):

- Subcommand ``override-record`` accepts:
  ``--run-id``, ``--gate {pr_eval,baseline_refresh,emergency_override}``,
  ``--pm-approver``, ``--technical-approver``, ``--reason``,
  ``--evidence``, ``--json``.
- Hard fail (exit 3 + ``PolicyViolation``) when either approver is
  missing.
- ``reason`` is required.
- ``evidence`` is required.
- Output JSON contains: ``overrideId``, ``runId``, ``gate``,
  ``pmApprover``, ``technicalApprover``, ``reason``, ``evidenceRef``,
  ``timestamp``.
- Persists to a structured audit record (currently in-process list; can
  be promoted to DB later).

TDD: assertions fail until T051 implementation lands.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from app.eval.export_policy import PolicyViolation

_REPO_ROOT = Path(__file__).resolve().parents[3]
_BACKEND = _REPO_ROOT / "backend"


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    """Run ``python -m app.eval.cli`` and capture output."""
    cmd = [sys.executable, "-m", "app.eval.cli", *args]
    return subprocess.run(
        cmd,
        cwd=str(_BACKEND),
        capture_output=True,
        text=True,
        env=None,
        timeout=30,
    )


# ---------------------------------------------------------------------------
# Programmatic API (testable in-process)
# ---------------------------------------------------------------------------


class TestOverrideRecordDualApproval:
    """Hard fail if either approver is missing (FR-024)."""

    def test_both_approvers_provided_succeeds(self) -> None:
        from app.eval.cli import cmd_override_record
        import argparse

        args = argparse.Namespace(
            run_id="run-2026-06-28-001",
            gate="pr_eval",
            pm_approver="alice_pm",
            technical_approver="bob_tech",
            reason="hotfix for prod regression",
            evidence="docs/evidence/run-001/eval-report.md",
            json_output=True,
        )
        result = cmd_override_record(args)
        # Result is the JSON body string when --json is set.
        assert isinstance(result, str), (
            f"cmd_override_record should return JSON string when --json set; got {type(result)}"
        )
        payload = json.loads(result)
        assert payload["runId"] == "run-2026-06-28-001"
        assert payload["gate"] == "pr_eval"
        assert payload["pmApprover"] == "alice_pm"
        assert payload["technicalApprover"] == "bob_tech"
        assert payload["reason"] == "hotfix for prod regression"
        assert payload["evidenceRef"] == "docs/evidence/run-001/eval-report.md"
        assert "overrideId" in payload
        assert "timestamp" in payload

    def test_missing_pm_approver_raises_policy_violation(self) -> None:
        from app.eval.cli import cmd_override_record
        import argparse

        args = argparse.Namespace(
            run_id="run-x",
            gate="pr_eval",
            pm_approver=None,  # missing
            technical_approver="bob_tech",
            reason="test",
            evidence="test.md",
            json_output=False,
        )
        with pytest.raises(PolicyViolation):
            cmd_override_record(args)

    def test_missing_technical_approver_raises_policy_violation(self) -> None:
        from app.eval.cli import cmd_override_record
        import argparse

        args = argparse.Namespace(
            run_id="run-x",
            gate="pr_eval",
            pm_approver="alice_pm",
            technical_approver=None,  # missing
            reason="test",
            evidence="test.md",
            json_output=False,
        )
        with pytest.raises(PolicyViolation):
            cmd_override_record(args)

    def test_missing_both_approvers_raises_policy_violation(self) -> None:
        from app.eval.cli import cmd_override_record
        import argparse

        args = argparse.Namespace(
            run_id="run-x",
            gate="baseline_refresh",
            pm_approver=None,
            technical_approver=None,
            reason="test",
            evidence="test.md",
            json_output=False,
        )
        with pytest.raises(PolicyViolation):
            cmd_override_record(args)

    def test_empty_string_approver_is_rejected(self) -> None:
        """Empty string approvers must be rejected (FR-024)."""
        from app.eval.cli import cmd_override_record
        import argparse

        args = argparse.Namespace(
            run_id="run-x",
            gate="emergency_override",
            pm_approver="   ",  # whitespace
            technical_approver="bob_tech",
            reason="test",
            evidence="test.md",
            json_output=False,
        )
        with pytest.raises(PolicyViolation):
            cmd_override_record(args)


# ---------------------------------------------------------------------------
# Required fields
# ---------------------------------------------------------------------------


class TestOverrideRecordRequiredFields:
    """reason and evidence are mandatory (FR-024)."""

    def test_missing_reason_raises(self) -> None:
        from app.eval.cli import cmd_override_record
        import argparse

        args = argparse.Namespace(
            run_id="run-x",
            gate="pr_eval",
            pm_approver="alice",
            technical_approver="bob",
            reason=None,
            evidence="test.md",
            json_output=False,
        )
        with pytest.raises((PolicyViolation, ValueError)):
            cmd_override_record(args)

    def test_missing_evidence_raises(self) -> None:
        from app.eval.cli import cmd_override_record
        import argparse

        args = argparse.Namespace(
            run_id="run-x",
            gate="pr_eval",
            pm_approver="alice",
            technical_approver="bob",
            reason="test reason",
            evidence=None,
            json_output=False,
        )
        with pytest.raises((PolicyViolation, ValueError)):
            cmd_override_record(args)

    def test_empty_reason_rejected(self) -> None:
        from app.eval.cli import cmd_override_record
        import argparse

        args = argparse.Namespace(
            run_id="run-x",
            gate="pr_eval",
            pm_approver="alice",
            technical_approver="bob",
            reason="",
            evidence="test.md",
            json_output=False,
        )
        with pytest.raises((PolicyViolation, ValueError)):
            cmd_override_record(args)


# ---------------------------------------------------------------------------
# JSON output shape
# ---------------------------------------------------------------------------


class TestOverrideRecordJSONShape:
    """JSON output keys must match contract (FR-024)."""

    def test_json_contains_all_required_keys(self) -> None:
        from app.eval.cli import cmd_override_record
        import argparse

        args = argparse.Namespace(
            run_id="run-001",
            gate="pr_eval",
            pm_approver="alice",
            technical_approver="bob",
            reason="hotfix",
            evidence="path/to/eval.md",
            json_output=True,
        )
        out = cmd_override_record(args)
        payload = json.loads(out)
        required_keys = {
            "overrideId",
            "runId",
            "gate",
            "pmApprover",
            "technicalApprover",
            "reason",
            "evidenceRef",
            "timestamp",
        }
        assert required_keys.issubset(set(payload.keys())), (
            f"missing keys: {required_keys - set(payload.keys())}"
        )

    def test_timestamp_is_iso8601(self) -> None:
        from app.eval.cli import cmd_override_record
        import argparse

        args = argparse.Namespace(
            run_id="run-001",
            gate="pr_eval",
            pm_approver="alice",
            technical_approver="bob",
            reason="hotfix",
            evidence="path",
            json_output=True,
        )
        out = cmd_override_record(args)
        payload = json.loads(out)
        ts = payload["timestamp"]
        # Must be parseable as ISO 8601.
        from datetime import datetime
        # Allow trailing Z.
        try:
            datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except ValueError:
            pytest.fail(f"timestamp {ts!r} not parseable as ISO 8601")

    def test_override_id_is_unique_per_call(self) -> None:
        from app.eval.cli import cmd_override_record
        import argparse

        args = argparse.Namespace(
            run_id="run-001",
            gate="pr_eval",
            pm_approver="alice",
            technical_approver="bob",
            reason="hotfix",
            evidence="path",
            json_output=True,
        )
        out_a = json.loads(cmd_override_record(args))
        out_b = json.loads(cmd_override_record(args))
        assert out_a["overrideId"] != out_b["overrideId"], (
            "Two override calls produced identical overrideId — must be unique"
        )


# ---------------------------------------------------------------------------
# Gate enum
# ---------------------------------------------------------------------------


class TestOverrideRecordGateEnum:
    """--gate must be one of the documented values."""

    @pytest.mark.parametrize(
        "gate",
        ["pr_eval", "baseline_refresh", "emergency_override"],
    )
    def test_valid_gates_accepted(self, gate: str) -> None:
        from app.eval.cli import cmd_override_record
        import argparse

        args = argparse.Namespace(
            run_id="run-001",
            gate=gate,
            pm_approver="alice",
            technical_approver="bob",
            reason="r",
            evidence="e",
            json_output=True,
        )
        out = cmd_override_record(args)
        payload = json.loads(out)
        assert payload["gate"] == gate

    def test_invalid_gate_raises_value_error(self) -> None:
        from app.eval.cli import cmd_override_record
        import argparse

        args = argparse.Namespace(
            run_id="run-001",
            gate="not_a_gate",
            pm_approver="alice",
            technical_approver="bob",
            reason="r",
            evidence="e",
            json_output=True,
        )
        with pytest.raises((ValueError, SystemExit)):
            cmd_override_record(args)


# ---------------------------------------------------------------------------
# CLI integration (subprocess smoke)
# ---------------------------------------------------------------------------


class TestOverrideRecordCLI:
    """Subprocess smoke: CLI exit codes match the contract."""

    def test_cli_override_record_success_exits_zero(self) -> None:
        proc = _run_cli(
            "override-record",
            "--run-id", "run-001",
            "--gate", "pr_eval",
            "--pm-approver", "alice",
            "--technical-approver", "bob",
            "--reason", "test reason",
            "--evidence", "test.md",
            "--json",
        )
        assert proc.returncode == 0, (
            f"successful override should exit 0; got {proc.returncode}; stderr={proc.stderr}"
        )

    def test_cli_override_record_missing_tech_exits_three(self) -> None:
        proc = _run_cli(
            "override-record",
            "--run-id", "run-002",
            "--gate", "pr_eval",
            "--pm-approver", "alice",
            "--reason", "missing technical",
            "--evidence", "test.md",
            "--json",
        )
        # Hard fail: exit 3 (policy violation per contracts §Shared CLI Rules).
        assert proc.returncode == 3, (
            f"missing technical approver should exit 3; got {proc.returncode}; "
            f"stderr={proc.stderr}; stdout={proc.stdout}"
        )

    def test_cli_override_record_missing_reason_exits_three(self) -> None:
        proc = _run_cli(
            "override-record",
            "--run-id", "run-003",
            "--gate", "pr_eval",
            "--pm-approver", "alice",
            "--technical-approver", "bob",
            "--evidence", "test.md",
            "--json",
        )
        assert proc.returncode in (2, 3), (
            f"missing reason should fail; got {proc.returncode}; stderr={proc.stderr}"
        )