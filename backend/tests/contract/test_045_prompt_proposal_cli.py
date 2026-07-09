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


def test_prompt_proposal_create_cli_outputs_ready_for_comparison() -> None:
    proc = _run_cli(
        "prompt-proposal",
        "create",
        "--source-run-id",
        "run-1",
        "--source-case-id",
        "case-1",
        "--target-graph",
        "interview",
        "--target-node",
        "score",
        "--candidate-fingerprint",
        "sha256:candidate",
        "--expected-impact",
        "Improve score fidelity",
        "--json",
    )

    assert proc.returncode == 0, proc.stderr
    body = json.loads(proc.stdout[proc.stdout.find("{") :])
    assert body["status"] == "READY_FOR_COMPARISON"
    assert body["targetGraph"] == "interview"
    assert body["targetNode"] == "score"
