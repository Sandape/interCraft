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


def _json(stdout: str) -> dict:
    first = stdout.find("{")
    assert first != -1, stdout
    return json.loads(stdout[first:])


def test_export_audit_allows_production_langsmith_full_content(tmp_path: Path) -> None:
    sample = tmp_path / "sample.json"
    sample.write_text(
        json.dumps({"messages": [{"role": "user", "content": "resume text"}]}),
        encoding="utf-8",
    )

    proc = _run_cli(
        "export-audit",
        "--sample",
        str(sample),
        "--destination",
        "LANGSMITH",
        "--env",
        "PRODUCTION",
        "--representation",
        "FULL_CONTENT",
        "--owner",
        "ai-ops",
        "--access-scope",
        "langsmith-prod-ai-debuggers",
        "--retention-days",
        "30",
        "--allowed-content-class",
        "resume_text",
        "--json",
    )

    assert proc.returncode == 0, proc.stderr
    body = _json(proc.stdout)
    assert body["allowed"] is True
    assert body["decision"]["destination"] == "LANGSMITH"
    assert body["decision"]["environment"] == "PRODUCTION"
    assert body["decision"]["representationLevel"] == "FULL_CONTENT"
    assert body["secretPaths"] == []


def test_export_audit_blocks_operational_secret(tmp_path: Path) -> None:
    sample = tmp_path / "sample.json"
    sample.write_text(json.dumps({"Authorization": "Bearer live-secret"}), encoding="utf-8")

    proc = _run_cli(
        "export-audit",
        "--sample",
        str(sample),
        "--destination",
        "LANGSMITH",
        "--env",
        "PRODUCTION",
        "--representation",
        "FULL_CONTENT",
        "--owner",
        "ai-ops",
        "--access-scope",
        "langsmith-prod-ai-debuggers",
        "--retention-days",
        "30",
        "--allowed-content-class",
        "llm_input",
        "--json",
    )

    assert proc.returncode == 3
    body = _json(proc.stdout)
    assert body["allowed"] is False
    assert body["decision"]["representationLevel"] == "BLOCKED"
    assert body["decision"]["blockedReason"] == "operational_secret_detected"
    assert body["secretPaths"] == ["Authorization"]
