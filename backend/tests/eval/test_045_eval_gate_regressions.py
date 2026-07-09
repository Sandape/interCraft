from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_BACKEND = _REPO_ROOT / "backend"


def test_regression_case_returns_exit_four(tmp_path: Path) -> None:
    spec_dir = tmp_path / "spec"
    golden = spec_dir / "golden"
    golden.mkdir(parents=True)
    (golden / "failing.json").write_text(
        """
{
  "case_id": "regression-english-answer",
  "node": "interview.score",
  "label": "English output should fail Chinese fidelity",
  "source": "manual",
  "input_state": {},
  "llm_response": "This answer is intentionally English only.",
  "expected_language": "zh-CN",
  "expected_contains": [],
  "status": "active"
}
""".strip(),
        encoding="utf-8",
    )

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.eval.cli",
            "run",
            "--spec-dir",
            str(spec_dir),
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
        ],
        cwd=_BACKEND,
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert proc.returncode == 4, proc.stderr
