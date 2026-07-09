from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_BACKEND = _REPO_ROOT / "backend"


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "app.eval.cli", *args],
        cwd=_BACKEND,
        capture_output=True,
        text=True,
        env=dict(os.environ),
        timeout=60,
    )


def _payload(stdout: str) -> dict:
    first = stdout.find("{")
    assert first != -1, stdout
    return json.loads(stdout[first:])


def test_judge_calibrate_cli_reports_blocking_enabled(tmp_path: Path) -> None:
    labels = tmp_path / "labels.json"
    labels.write_text(
        json.dumps([{"human_passed": True, "judge_passed": True} for _ in range(30)]),
        encoding="utf-8",
    )

    proc = _run_cli("judge-calibrate", "--labels", str(labels), "--owner", "ai-ops", "--json")

    assert proc.returncode == 0, proc.stderr
    body = _payload(proc.stdout)
    assert body["calibrationStatus"] == "BLOCKING_ENABLED"
    assert body["humanLabelCount"] == 30
    assert body["agreementRate"] == 1.0


def test_judge_run_cli_is_report_only_by_default(tmp_path: Path) -> None:
    report = tmp_path / "report.json"
    report.write_text(
        json.dumps(
            {
                "runId": "run-1",
                "caseResults": [
                    {
                        "caseId": "case-1",
                        "passed": False,
                        "deterministicMetrics": {"score": 0.2},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    proc = _run_cli("judge-run", "--report", str(report), "--json")

    assert proc.returncode == 0, proc.stderr
    body = _payload(proc.stdout)
    assert body["blockingEnabled"] is False
    assert body["verdicts"][0]["caseId"] == "case-1"
    assert body["verdicts"][0]["blocksMerge"] is False
