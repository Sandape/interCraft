from __future__ import annotations

import json
from pathlib import Path

from app.eval.golden_loader import load_golden_cases


def test_loader_preserves_candidate_and_report_only_lifecycles(tmp_path: Path) -> None:
    golden = tmp_path / "golden"
    golden.mkdir()
    (golden / "candidate.json").write_text(
        json.dumps(
            {
                "case_id": "candidate-1",
                "node": "interview.score",
                "label": "candidate badcase",
                "source": "promoted",
                "input_state": {},
                "llm_response": "{}",
                "lifecycle": "CANDIDATE",
                "dataset_version": "candidate-v1",
            }
        ),
        encoding="utf-8",
    )
    (golden / "report-only.json").write_text(
        json.dumps(
            {
                "case_id": "report-only-1",
                "node": "interview.score",
                "label": "report only badcase",
                "source": "promoted",
                "input_state": {},
                "llm_response": "{}",
                "lifecycle": "REPORT_ONLY",
                "dataset_version": "report-only-v1",
            }
        ),
        encoding="utf-8",
    )

    cases = load_golden_cases(tmp_path)

    by_id = {case.case_id: case for case in cases}
    assert by_id["candidate-1"].lifecycle == "CANDIDATE"
    assert by_id["candidate-1"].dataset_version == "candidate-v1"
    assert by_id["report-only-1"].lifecycle == "REPORT_ONLY"
    assert by_id["report-only-1"].dataset_version == "report-only-v1"
