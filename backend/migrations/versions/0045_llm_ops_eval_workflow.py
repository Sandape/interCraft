"""Create REQ-045 LLM Ops eval workflow tables."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0045_llm_ops_eval_workflow"
down_revision = "0027_021_eq_arch"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "llm_ops_eval_runs",
        sa.Column("run_id", sa.Text(), nullable=False),
        sa.Column("suite", sa.Text(), nullable=False),
        sa.Column("environment", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("source_revision", sa.Text(), nullable=False),
        sa.Column("branch", sa.Text(), nullable=True),
        sa.Column("dataset_version", sa.Text(), nullable=False),
        sa.Column("prompt_fingerprint", sa.Text(), nullable=False, server_default=sa.text("'unavailable'")),
        sa.Column("rubric_version", sa.Text(), nullable=False, server_default=sa.text("'unavailable'")),
        sa.Column("model_version", sa.Text(), nullable=False, server_default=sa.text("'unavailable'")),
        sa.Column("aggregate_pass_rate", sa.Numeric(5, 4), nullable=True),
        sa.Column("known_regression_recall", sa.Numeric(5, 4), nullable=True),
        sa.Column("token_usage", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("cost_usd", sa.Numeric(12, 6), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("local_artifacts", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("langsmith_export_status", sa.String(length=32), nullable=False, server_default=sa.text("'DISABLED'")),
        sa.Column("export_policy_decision_id", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("run_id"),
    )
    op.create_index("idx_llm_ops_eval_runs_suite_env", "llm_ops_eval_runs", ["suite", "environment"])
    op.create_index("idx_llm_ops_eval_runs_status", "llm_ops_eval_runs", ["status"])

    op.create_table(
        "llm_ops_eval_case_results",
        sa.Column("case_result_id", sa.Text(), nullable=False),
        sa.Column("case_id", sa.Text(), nullable=False),
        sa.Column("run_id", sa.Text(), nullable=False),
        sa.Column("lifecycle", sa.String(length=32), nullable=False),
        sa.Column("graph", sa.Text(), nullable=False),
        sa.Column("node", sa.Text(), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("failure_reasons", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("deterministic_metrics", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("artifact_ref", sa.Text(), nullable=False, server_default=sa.text("'unavailable'")),
        sa.Column("trace_run_ref_id", sa.Text(), nullable=True),
        sa.Column("langsmith_run_url", sa.Text(), nullable=False, server_default=sa.text("'unavailable'")),
        sa.Column("judge_verdict_ids", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("case_result_id"),
        sa.ForeignKeyConstraint(["run_id"], ["llm_ops_eval_runs.run_id"], ondelete="CASCADE"),
    )
    op.create_index("idx_llm_ops_eval_case_results_run", "llm_ops_eval_case_results", ["run_id"])
    op.create_index("idx_llm_ops_eval_case_results_case", "llm_ops_eval_case_results", ["case_id"])
    op.create_index("idx_llm_ops_eval_case_results_trace_ref", "llm_ops_eval_case_results", ["trace_run_ref_id"])

    op.create_table(
        "llm_ops_trace_run_refs",
        sa.Column("trace_run_ref_id", sa.Text(), nullable=False),
        sa.Column("run_id", sa.Text(), nullable=False),
        sa.Column("case_id", sa.Text(), nullable=True),
        sa.Column("trace_id", sa.Text(), nullable=True),
        sa.Column("span_id", sa.Text(), nullable=True),
        sa.Column("artifact_ref", sa.Text(), nullable=True),
        sa.Column("langsmith_url", sa.Text(), nullable=True),
        sa.Column("entrypoint", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("trace_run_ref_id"),
    )
    op.create_index("idx_llm_ops_trace_run_refs_run", "llm_ops_trace_run_refs", ["run_id"])
    op.create_index("idx_llm_ops_trace_run_refs_trace", "llm_ops_trace_run_refs", ["trace_id"])

    op.create_table(
        "llm_ops_langsmith_refs",
        sa.Column("langsmith_ref_id", sa.Text(), nullable=False),
        sa.Column("run_id", sa.Text(), nullable=False),
        sa.Column("project", sa.Text(), nullable=False),
        sa.Column("dataset_name", sa.Text(), nullable=False),
        sa.Column("dataset_version", sa.Text(), nullable=False),
        sa.Column("experiment_name", sa.Text(), nullable=False),
        sa.Column("experiment_url", sa.Text(), nullable=True),
        sa.Column("sync_status", sa.String(length=32), nullable=False),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("langsmith_ref_id"),
        sa.ForeignKeyConstraint(["run_id"], ["llm_ops_eval_runs.run_id"], ondelete="CASCADE"),
    )
    op.create_index("idx_llm_ops_langsmith_refs_run", "llm_ops_langsmith_refs", ["run_id"])
    op.create_index("idx_llm_ops_langsmith_refs_status", "llm_ops_langsmith_refs", ["sync_status"])

    op.create_table(
        "llm_ops_judge_verdicts",
        sa.Column("verdict_id", sa.Text(), nullable=False),
        sa.Column("run_id", sa.Text(), nullable=False),
        sa.Column("case_id", sa.Text(), nullable=False),
        sa.Column("rubric_id", sa.Text(), nullable=False),
        sa.Column("rubric_version", sa.Text(), nullable=False),
        sa.Column("judge_model", sa.Text(), nullable=False),
        sa.Column("score", sa.Numeric(6, 4), nullable=True),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column("rationale_summary", sa.Text(), nullable=True),
        sa.Column("disagreement_markers", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("is_blocking", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("verdict_id"),
        sa.ForeignKeyConstraint(["run_id"], ["llm_ops_eval_runs.run_id"], ondelete="CASCADE"),
    )
    op.create_index("idx_llm_ops_judge_verdicts_run", "llm_ops_judge_verdicts", ["run_id"])
    op.create_index("idx_llm_ops_judge_verdicts_case", "llm_ops_judge_verdicts", ["case_id"])

    op.create_table(
        "llm_ops_export_decisions",
        sa.Column("decision_id", sa.Text(), nullable=False),
        sa.Column("destination", sa.String(length=32), nullable=False),
        sa.Column("environment", sa.String(length=32), nullable=False),
        sa.Column("representation_level", sa.String(length=32), nullable=False),
        sa.Column("policy_version", sa.Text(), nullable=False),
        sa.Column("owner", sa.Text(), nullable=True),
        sa.Column("access_scope", sa.Text(), nullable=True),
        sa.Column("retention_days", sa.Integer(), nullable=True),
        sa.Column("allowed_content_classes", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("blocked_reason", sa.Text(), nullable=True),
        sa.Column("sample_rate", sa.Numeric(5, 4), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("decision_id"),
    )
    op.create_index("idx_llm_ops_export_decisions_dest_env", "llm_ops_export_decisions", ["destination", "environment"])

    op.create_table(
        "llm_ops_badcase_candidates",
        sa.Column("candidate_id", sa.Text(), nullable=False),
        sa.Column("source_badcase_id", sa.Text(), nullable=False),
        sa.Column("source_trace_run_ref_id", sa.Text(), nullable=True),
        sa.Column("case_id", sa.Text(), nullable=True),
        sa.Column("lifecycle", sa.String(length=32), nullable=False),
        sa.Column("owner", sa.Text(), nullable=False),
        sa.Column("review_status", sa.String(length=32), nullable=False, server_default=sa.text("'PENDING'")),
        sa.Column("export_policy_decision_id", sa.Text(), nullable=True),
        sa.Column("approval_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("candidate_id"),
    )
    op.create_index("idx_llm_ops_badcase_candidates_source", "llm_ops_badcase_candidates", ["source_badcase_id"])
    op.create_index("idx_llm_ops_badcase_candidates_case", "llm_ops_badcase_candidates", ["case_id"])

    op.create_table(
        "llm_ops_prompt_proposals",
        sa.Column("proposal_id", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("source_run_ids", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("source_case_ids", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("target_graph", sa.Text(), nullable=False),
        sa.Column("target_node", sa.Text(), nullable=False),
        sa.Column("proposal_type", sa.String(length=32), nullable=False),
        sa.Column("candidate_fingerprint", sa.Text(), nullable=False),
        sa.Column("expected_impact", sa.Text(), nullable=False),
        sa.Column("comparison_run_id", sa.Text(), nullable=True),
        sa.Column("approval_owner", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("proposal_id"),
    )
    op.create_index("idx_llm_ops_prompt_proposals_status", "llm_ops_prompt_proposals", ["status"])


def downgrade() -> None:
    for table in (
        "llm_ops_prompt_proposals",
        "llm_ops_badcase_candidates",
        "llm_ops_export_decisions",
        "llm_ops_judge_verdicts",
        "llm_ops_langsmith_refs",
        "llm_ops_trace_run_refs",
        "llm_ops_eval_case_results",
        "llm_ops_eval_runs",
    ):
        op.drop_table(table)
