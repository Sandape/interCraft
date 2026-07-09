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


def test_run_sync_langsmith_never_reports_disabled(tmp_path: Path) -> None:
    proc = _run_cli(
        "run",
        "--suite",
        "golden",
        "--env",
        "ci",
        "--report-out",
        str(tmp_path / "report.json"),
        "--markdown-out",
        str(tmp_path / "report.md"),
        "--sync-langsmith",
        "never",
        "--json",
    )

    assert proc.returncode in (0, 4), proc.stderr
    body = _payload(proc.stdout)
    assert body["langsmithExportStatus"] == "DISABLED"


def test_run_sync_langsmith_require_without_credentials_exits_one(tmp_path: Path) -> None:
    proc = _run_cli(
        "run",
        "--suite",
        "golden",
        "--env",
        "ci",
        "--report-out",
        str(tmp_path / "report.json"),
        "--markdown-out",
        str(tmp_path / "report.md"),
        "--sync-langsmith",
        "require",
        "--json",
    )

    assert proc.returncode == 1
    body = _payload(proc.stdout)
    assert body["langsmithExportStatus"] == "FAILED"
