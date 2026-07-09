from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_BACKEND = _REPO_ROOT / "backend"


def test_badcase_promote_cli_accepts_badcase_json(tmp_path: Path) -> None:
    badcase = tmp_path / "badcase.json"
    badcase.write_text(
        json.dumps(
            {
                "badcaseId": "bc-cli",
                "type": "EVAL_REGRESSION",
                "privacyClass": "REDACTED_SUMMARY",
                "redactionStatus": "PASSED",
            }
        ),
        encoding="utf-8",
    )

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.modules.badcases.cli",
            "promote",
            "--badcase-json",
            str(badcase),
            "--reviewer",
            "pm",
            "--reason",
            "protect regression",
            "--lifecycle",
            "CANDIDATE",
            "--dataset-version",
            "candidate-v1",
            "--json",
        ],
        cwd=_BACKEND,
        capture_output=True,
        text=True,
        env=dict(os.environ, BADCASES_GOLDEN_DIR=str(tmp_path / "golden")),
        timeout=60,
    )

    assert proc.returncode == 0, proc.stderr
    body = json.loads(proc.stdout[proc.stdout.find("{") :])
    assert body["evalCase"]["case_id"] == "badcase-bc-cli"
    assert body["evalCase"]["lifecycle"] == "CANDIDATE"
    assert Path(body["candidatePath"]).exists()
