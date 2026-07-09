from __future__ import annotations

import importlib.util
from pathlib import Path

from app.core.db import Base

_REPO_ROOT = Path(__file__).resolve().parents[3]
_MIGRATION = _REPO_ROOT / "backend" / "migrations" / "versions" / "0045_llm_ops_eval_workflow.py"


def _load_migration_module():
    spec = importlib.util.spec_from_file_location("migration_0045_llm_ops_eval_workflow", _MIGRATION)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_req045_migration_file_and_revision_contract() -> None:
    assert _MIGRATION.exists()
    module = _load_migration_module()
    assert module.revision == "0045_llm_ops_eval_workflow"
    assert module.down_revision == "0027_021_eq_arch"


def test_req045_migration_declares_required_tables() -> None:
    from app.modules.telemetry_contracts import models  # noqa: F401

    text = _MIGRATION.read_text(encoding="utf-8")
    for table in (
        "llm_ops_eval_runs",
        "llm_ops_eval_case_results",
        "llm_ops_trace_run_refs",
        "llm_ops_langsmith_refs",
        "llm_ops_judge_verdicts",
        "llm_ops_export_decisions",
        "llm_ops_badcase_candidates",
        "llm_ops_prompt_proposals",
    ):
        assert f'"{table}"' in text
        assert table in Base.metadata.tables


def test_req045_models_include_expected_indexes_and_json_columns() -> None:
    from app.modules.telemetry_contracts import models

    eval_run = models.LLMOpsEvalRun.__table__
    assert "run_id" in eval_run.c
    assert "local_artifacts" in eval_run.c
    assert "langsmith_export_status" in eval_run.c

    export_decision = models.LLMOpsExportDecision.__table__
    assert "destination" in export_decision.c
    assert "representation_level" in export_decision.c
    assert "allowed_content_classes" in export_decision.c


def test_req045_migration_downgrade_drops_tables_in_reverse_order() -> None:
    text = _MIGRATION.read_text(encoding="utf-8")
    downgrade_text = text[text.index("def downgrade") :]
    first_drop = downgrade_text.find('"llm_ops_prompt_proposals"')
    last_drop = downgrade_text.find('"llm_ops_eval_runs"')
    assert first_drop != -1
    assert last_drop != -1
    assert first_drop < last_drop
