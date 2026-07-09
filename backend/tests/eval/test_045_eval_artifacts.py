from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from app.eval.report import write_req045_report_artifacts
from app.eval.runner import EvalReport


def test_write_req045_report_artifacts_keeps_json_markdown_parity(tmp_path: Path) -> None:
    run_id = uuid4()
    report = EvalReport(
        timestamp="2026-07-05T01:03:00+00:00",
        git_sha="abc123",
        model="mock-llm",
        total_cases=0,
        passed_cases=0,
        failed_cases=0,
        skipped_cases=0,
        run_id=run_id,
        source_revision="abc123",
        branch="codex/045",
        environment="CI",
    )

    json_path = tmp_path / "eval-report.json"
    markdown_path = tmp_path / "eval-report.md"
    payload = write_req045_report_artifacts(
        report,
        json_path=json_path,
        markdown_path=markdown_path,
        suite="golden",
        dataset_version="golden-v2",
        langsmith_export_status="DISABLED",
    )

    disk = json.loads(json_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")
    assert disk == payload
    assert disk["runId"] == str(run_id)
    assert f"Run ID: `{run_id}`" in markdown
    assert "LangSmith: `DISABLED`" in markdown
