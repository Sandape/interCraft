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


def test_experiment_compare_cli_emits_quality_cost_latency_delta(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.json"
    candidate = tmp_path / "candidate.json"
    baseline.write_text(
        json.dumps(
            {
                "runId": "baseline",
                "aggregatePassRate": 0.7,
                "costUsd": 1.0,
                "latencyMs": 1200,
            }
        ),
        encoding="utf-8",
    )
    candidate.write_text(
        json.dumps(
            {
                "runId": "candidate",
                "aggregatePassRate": 0.8,
                "costUsd": 1.1,
                "latencyMs": 900,
            }
        ),
        encoding="utf-8",
    )

    proc = _run_cli(
        "experiment-compare",
        "--baseline",
        str(baseline),
        "--candidate",
        str(candidate),
        "--json",
    )

    assert proc.returncode == 0, proc.stderr
    body = json.loads(proc.stdout[proc.stdout.find("{") :])
    assert body["baselineRunId"] == "baseline"
    assert body["candidateRunId"] == "candidate"
    assert body["qualityDelta"] == 0.1
    assert body["costDeltaUsd"] == 0.1
    assert body["latencyDeltaMs"] == -300
