"""Create REQ-033 PM dashboard + eval metadata + badcase + redaction tables.

Eleven tables backing the eval pipeline, PM Dashboard V1, badcase review,
and redaction audit (data-model.md §Core Entities, US1 / US5 / US6 / US8 /
US9 / US10):

1. ``eval_runs`` — one eval execution; aggregate verdicts, budget, version.
2. ``eval_case_results`` — per-case verdict + trace + artifact references.
3. ``langsmith_experiment_refs`` — optional LangSmith sync state by run_id.
4. ``trace_run_refs`` — trace → run join + sampling + retention metadata.
5. ``product_funnel_events`` — funnel + lifecycle event records.
6. ``ai_invocation_records`` — per-AI-call summary (tokens, latency, cost).
7. ``pm_metric_snapshots`` — dashboard-ready metric rows (denom / numer / dims).
8. ``badcases`` — human-reviewable quality issues.
9. ``badcase_review_actions`` — append-only audit log of badcase lifecycle.
10. ``redaction_policies`` — environment-specific export policy rows.
11. ``redaction_audits`` — redaction evidence rows (FR-035).

RLS
---
Per-user RLS (mirrors 0020_irt_item_bank / 0022_032_resumes_v2) is enabled
on every table that carries ``user_id`` so a non-owner session can never
read or write another user's rows. Tables WITHOUT ``user_id``
(``redaction_policies``, ``redaction_audits``) are intentionally global —
they are PM / admin records that must span users for cross-user audit
evidence (FR-035).

Indexes
-------
- B-tree on every FK + ``run_id`` + ``trace_id`` + ``event_name`` +
  ``occurred_at`` + ``metric_id`` (dominant query patterns).
- JSONB GIN on ``version_context`` / ``dimensions`` / ``metadata`` for
  PM-side dimension-key lookups (e.g. ``WHERE dimensions @> '{"env":"prod"}'``).

No new package dependencies. Migration is forward-only; downgrade drops
all tables in reverse creation order.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

revision = "0024_033_eval_pm_dashboard"
down_revision = "0023_032_resumes_v2_owner_lookup"
branch_labels = None
depends_on = None


def _enable_rls(table: str, policy_column: str = "user_id") -> None:
    """Per-user RLS using app.user_id GUC. Mirrors 0020_irt_item_bank."""
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;")
    op.execute(
        f"CREATE POLICY {table}_user_isolation ON {table} "
        f"USING ({policy_column} = current_setting('app.user_id', true)::uuid) "
        f"WITH CHECK ({policy_column} = current_setting('app.user_id', true)::uuid);"
    )


def upgrade() -> None:
    # ── 1. eval_runs ────────────────────────────────────────────────────────
    op.create_table(
        "eval_runs",
        sa.Column("run_id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("source_revision", sa.String(length=64), nullable=False),
        sa.Column("branch", sa.String(length=128), nullable=False),
        sa.Column("environment", sa.String(length=16), nullable=False),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'STARTED'"),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("aggregate_pass_rate", sa.Numeric(5, 4), nullable=True),
        sa.Column("known_regression_recall", sa.Numeric(5, 4), nullable=True),
        sa.Column("stale_case_count", sa.Integer(), nullable=True),
        sa.Column("budget_tokens", sa.Integer(), nullable=True),
        sa.Column("budget_cost", sa.Numeric(12, 4), nullable=True),
        sa.Column(
            "version_context",
            JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("run_id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "status IN ('STARTED','PASSED','FAILED','INCOMPLETE','SYNC_FAILED','SYNCED')",
            name="ck_eval_runs_status",
        ),
        sa.CheckConstraint(
            "environment IN ('LOCAL','CI','STAGING','PRODUCTION')",
            name="ck_eval_runs_environment",
        ),
    )
    op.create_index("idx_eval_runs_user_started", "eval_runs", ["user_id", "started_at"])
    op.create_index("idx_eval_runs_branch", "eval_runs", ["branch"])
    op.create_index(
        "idx_eval_runs_version_context_gin",
        "eval_runs",
        ["version_context"],
        postgresql_using="gin",
    )

    # ── 2. eval_case_results ────────────────────────────────────────────────
    op.create_table(
        "eval_case_results",
        sa.Column("id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", sa.String(length=128), nullable=False),
        sa.Column(
            "verdict",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'PENDING'"),
        ),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column(
            "metrics",
            JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("trace_id", sa.String(length=128), nullable=True),
        sa.Column("artifact_ref", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["run_id"], ["eval_runs.run_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "verdict IN ('PASS','FAIL','STALE','SKIPPED','ERROR','PENDING')",
            name="ck_eval_case_results_verdict",
        ),
    )
    op.create_index("idx_eval_case_results_run_id", "eval_case_results", ["run_id"])
    op.create_index("idx_eval_case_results_trace_id", "eval_case_results", ["trace_id"])
    op.create_index("idx_eval_case_results_case_id", "eval_case_results", ["case_id"])
    op.create_index("idx_eval_case_results_user_created", "eval_case_results", ["user_id", "created_at"])
    op.create_index(
        "idx_eval_case_results_metrics_gin",
        "eval_case_results",
        ["metrics"],
        postgresql_using="gin",
    )

    # ── 3. langsmith_experiment_refs ────────────────────────────────────────
    op.create_table(
        "langsmith_experiment_refs",
        sa.Column("id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("project", sa.String(length=128), nullable=False),
        sa.Column("dataset", sa.String(length=256), nullable=False),
        sa.Column("experiment_name", sa.String(length=256), nullable=False),
        sa.Column("external_id", sa.String(length=256), nullable=True),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column(
            "sync_status",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'PENDING'"),
        ),
        sa.Column("sync_error", sa.Text(), nullable=True),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["run_id"], ["eval_runs.run_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "sync_status IN ('DISABLED','PENDING','SYNCED','FAILED')",
            name="ck_langsmith_experiment_refs_status",
        ),
    )
    op.create_index("idx_lse_refs_run_id", "langsmith_experiment_refs", ["run_id"])
    op.create_index("idx_lse_refs_user_created", "langsmith_experiment_refs", ["user_id", "created_at"])
    op.create_index("idx_lse_refs_sync_status", "langsmith_experiment_refs", ["sync_status"])

    # ── 4. trace_run_refs ───────────────────────────────────────────────────
    op.create_table(
        "trace_run_refs",
        sa.Column("id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("trace_id", sa.String(length=128), nullable=False),
        sa.Column("run_id", PG_UUID(as_uuid=True), nullable=True),
        sa.Column("user_id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("environment", sa.String(length=16), nullable=False),
        sa.Column(
            "sampling_decision",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'NOT_ENABLED'"),
        ),
        sa.Column("privacy_class", sa.String(length=32), nullable=False),
        sa.Column(
            "redaction_status",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'NOT_REQUIRED'"),
        ),
        sa.Column("retention_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["run_id"], ["eval_runs.run_id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "sampling_decision IN ('ALWAYS_ERROR','SAMPLED','FORCED','DROPPED','NOT_ENABLED')",
            name="ck_trace_run_refs_sampling_decision",
        ),
        sa.CheckConstraint(
            "redaction_status IN ('NOT_REQUIRED','PENDING','PASSED','FAILED','NOT_EXPORTABLE')",
            name="ck_trace_run_refs_redaction_status",
        ),
        sa.UniqueConstraint("trace_id", name="uq_trace_run_refs_trace_id"),
    )
    op.create_index("idx_trace_run_refs_run_id", "trace_run_refs", ["run_id"])
    op.create_index("idx_trace_run_refs_user_created", "trace_run_refs", ["user_id", "created_at"])
    op.create_index("idx_trace_run_refs_retention", "trace_run_refs", ["retention_expires_at"])

    # ── 5. product_funnel_events ────────────────────────────────────────────
    op.create_table(
        "product_funnel_events",
        sa.Column("id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("event_name", sa.String(length=128), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor_hash", sa.String(length=64), nullable=True),
        sa.Column("user_hash", sa.String(length=64), nullable=True),
        sa.Column("session_hash", sa.String(length=64), nullable=True),
        sa.Column("thread_hash", sa.String(length=64), nullable=True),
        sa.Column("feature_area", sa.String(length=32), nullable=False),
        sa.Column(
            "version_context",
            JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("privacy_class", sa.String(length=32), nullable=False),
        sa.Column(
            "redaction_status",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'NOT_REQUIRED'"),
        ),
        sa.Column(
            "metadata",
            JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        # user_id NOT NULL but added after the foreign key so we can use it in RLS.
        sa.Column("user_id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "feature_area IN ('AUTH','RESUME','INTERVIEW','AI','FEEDBACK','BADCASE','EVAL')",
            name="ck_product_funnel_events_feature_area",
        ),
        sa.CheckConstraint(
            "redaction_status IN ('NOT_REQUIRED','PENDING','PASSED','FAILED','NOT_EXPORTABLE')",
            name="ck_product_funnel_events_redaction_status",
        ),
    )
    op.create_index(
        "idx_product_funnel_events_event_name",
        "product_funnel_events",
        ["event_name"],
    )
    op.create_index(
        "idx_product_funnel_events_occurred_at",
        "product_funnel_events",
        ["occurred_at"],
    )
    op.create_index(
        "idx_product_funnel_events_user_occurred",
        "product_funnel_events",
        ["user_id", "occurred_at"],
    )
    op.create_index(
        "idx_product_funnel_events_feature_area",
        "product_funnel_events",
        ["feature_area"],
    )
    op.create_index(
        "idx_product_funnel_events_version_context_gin",
        "product_funnel_events",
        ["version_context"],
        postgresql_using="gin",
    )
    op.create_index(
        "idx_product_funnel_events_metadata_gin",
        "product_funnel_events",
        ["metadata"],
        postgresql_using="gin",
    )

    # ── 6. ai_invocation_records ────────────────────────────────────────────
    op.create_table(
        "ai_invocation_records",
        sa.Column("id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column(
            "invocation_id",
            PG_UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("run_id", PG_UUID(as_uuid=True), nullable=True),
        sa.Column("trace_id", sa.String(length=128), nullable=True),
        sa.Column("graph", sa.String(length=128), nullable=False),
        sa.Column("node", sa.String(length=128), nullable=False),
        sa.Column("model", sa.String(length=64), nullable=False),
        sa.Column("prompt_fingerprint", sa.String(length=128), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("completion_tokens", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("estimated_cost", sa.Numeric(12, 6), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'SUCCESS'"),
        ),
        sa.Column("error_category", sa.String(length=64), nullable=True),
        sa.Column("user_id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("invocation_id", name="uq_ai_invocation_records_invocation_id"),
        sa.ForeignKeyConstraint(["run_id"], ["eval_runs.run_id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "status IN ('SUCCESS','FAILURE','TIMEOUT','CANCELLED')",
            name="ck_ai_invocation_records_status",
        ),
        sa.CheckConstraint(
            "prompt_tokens >= 0 AND completion_tokens >= 0",
            name="ck_ai_invocation_records_tokens_nonneg",
        ),
        sa.CheckConstraint("retry_count >= 0", name="ck_ai_invocation_records_retry_nonneg"),
    )
    op.create_index("idx_ai_invocations_run_id", "ai_invocation_records", ["run_id"])
    op.create_index("idx_ai_invocations_trace_id", "ai_invocation_records", ["trace_id"])
    op.create_index("idx_ai_invocations_user_created", "ai_invocation_records", ["user_id", "created_at"])
    op.create_index("idx_ai_invocations_graph_node", "ai_invocation_records", ["graph", "node"])
    op.create_index("idx_ai_invocations_model", "ai_invocation_records", ["model"])

    # ── 7. pm_metric_snapshots ──────────────────────────────────────────────
    op.create_table(
        "pm_metric_snapshots",
        sa.Column("id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("metric_id", sa.String(length=128), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "grain",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'DAY'"),
        ),
        sa.Column(
            "dimensions",
            JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("numerator", sa.Numeric(20, 4), nullable=True),
        sa.Column("denominator", sa.Numeric(20, 4), nullable=True),
        sa.Column("value", sa.Numeric(20, 6), nullable=False),
        sa.Column("unit", sa.String(length=16), nullable=False),
        sa.Column("source_of_truth", sa.String(length=256), nullable=False),
        sa.Column("freshness_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "quality_flags",
            JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("user_id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "grain IN ('DAY','WEEK','RELEASE','EVAL_RUN')",
            name="ck_pm_metric_snapshots_grain",
        ),
        sa.CheckConstraint(
            "unit IN ('COUNT','PERCENT','TOKENS','CURRENCY','MILLISECONDS','SCORE','DAYS')",
            name="ck_pm_metric_snapshots_unit",
        ),
        sa.CheckConstraint("period_end >= period_start", name="ck_pm_metric_snapshots_period"),
    )
    op.create_index("idx_pm_metric_snapshots_metric_id", "pm_metric_snapshots", ["metric_id"])
    op.create_index(
        "idx_pm_metric_snapshots_metric_period",
        "pm_metric_snapshots",
        ["metric_id", "period_start", "period_end"],
    )
    op.create_index(
        "idx_pm_metric_snapshots_user_created",
        "pm_metric_snapshots",
        ["user_id", "created_at"],
    )
    op.create_index(
        "idx_pm_metric_snapshots_dimensions_gin",
        "pm_metric_snapshots",
        ["dimensions"],
        postgresql_using="gin",
    )

    # ── 8. badcases ─────────────────────────────────────────────────────────
    op.create_table(
        "badcases",
        sa.Column("id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("badcase_id", sa.String(length=128), nullable=False),
        sa.Column(
            "type",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column(
            "severity",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'MEDIUM'"),
        ),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'OPEN'"),
        ),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("reviewer", sa.String(length=128), nullable=True),
        sa.Column("privacy_class", sa.String(length=32), nullable=False),
        sa.Column(
            "redaction_status",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'NOT_REQUIRED'"),
        ),
        sa.Column("run_id", PG_UUID(as_uuid=True), nullable=True),
        sa.Column("trace_id", sa.String(length=128), nullable=True),
        sa.Column("closure_reason", sa.Text(), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("user_id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("badcase_id", name="uq_badcases_badcase_id"),
        sa.ForeignKeyConstraint(["run_id"], ["eval_runs.run_id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "type IN ("
            "'RESUME_DIAGNOSIS_QUALITY','MOCK_INTERVIEW_QUALITY',"
            "'AI_RELIABILITY','AI_COST_LATENCY','PRODUCT_FUNNEL_UX',"
            "'DATA_QUALITY','PRIVACY_REDACTION','EVAL_REGRESSION'"
            ")",
            name="ck_badcases_type",
        ),
        sa.CheckConstraint(
            "severity IN ('LOW','MEDIUM','HIGH','CRITICAL')",
            name="ck_badcases_severity",
        ),
        sa.CheckConstraint(
            "status IN ('OPEN','TRIAGED','IN_PROGRESS','AWAITING_VALIDATION','CLOSED','REJECTED')",
            name="ck_badcases_status",
        ),
    )
    op.create_index("idx_badcases_run_id", "badcases", ["run_id"])
    op.create_index("idx_badcases_trace_id", "badcases", ["trace_id"])
    op.create_index("idx_badcases_status", "badcases", ["status"])
    op.create_index("idx_badcases_severity", "badcases", ["severity"])
    op.create_index("idx_badcases_user_status", "badcases", ["user_id", "status"])
    op.create_index("idx_badcases_user_created", "badcases", ["user_id", "created_at"])

    # ── 9. badcase_review_actions ───────────────────────────────────────────
    op.create_table(
        "badcase_review_actions",
        sa.Column("id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("badcase_id", sa.String(length=128), nullable=False),
        sa.Column(
            "action_type",
            sa.String(length=32),
            nullable=False,
        ),
        sa.Column("actor_role", sa.String(length=64), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("evidence_ref", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["badcase_id"], ["badcases.badcase_id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "action_type IN ("
            "'CREATE','CLASSIFY','PROMOTE_CANDIDATE','APPROVE_PROMOTION',"
            "'CLOSE','REJECT','OVERRIDE','BASELINE_REFRESH'"
            ")",
            name="ck_badcase_review_actions_action_type",
        ),
    )
    op.create_index(
        "idx_badcase_review_actions_badcase",
        "badcase_review_actions",
        ["badcase_id", "created_at"],
    )
    op.create_index(
        "idx_badcase_review_actions_action_type",
        "badcase_review_actions",
        ["action_type"],
    )

    # ── 10. redaction_policies (global — no user_id, no RLS) ─────────────────
    op.create_table(
        "redaction_policies",
        sa.Column("id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("policy_version", sa.String(length=32), nullable=False),
        sa.Column("environment", sa.String(length=16), nullable=False),
        sa.Column(
            "allowed_classes",
            JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "forbidden_classes",
            JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "summary_rules",
            JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("retention_days", sa.Integer(), nullable=False),
        sa.Column(
            "requires_human_review",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "environment IN ('LOCAL','CI','STAGING','PRODUCTION')",
            name="ck_redaction_policies_environment",
        ),
        sa.CheckConstraint(
            "retention_days >= 0",
            name="ck_redaction_policies_retention_nonneg",
        ),
    )
    op.create_index(
        "idx_redaction_policies_env_version",
        "redaction_policies",
        ["environment", "policy_version"],
    )

    # ── 11. redaction_audits (global — no user_id, no RLS) ──────────────────
    op.create_table(
        "redaction_audits",
        sa.Column("id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("audit_id", sa.String(length=128), nullable=False),
        sa.Column("policy_version", sa.String(length=32), nullable=False),
        sa.Column("environment", sa.String(length=16), nullable=False),
        sa.Column("sample_count", sa.Integer(), nullable=False),
        sa.Column("forbidden_content_failures", sa.Integer(), nullable=False),
        sa.Column(
            "result",
            sa.String(length=16),
            nullable=False,
        ),
        sa.Column("reviewer", sa.String(length=128), nullable=False),
        sa.Column("evidence_ref", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("audit_id", name="uq_redaction_audits_audit_id"),
        sa.CheckConstraint(
            "result IN ('PASSED','FAILED','INCOMPLETE')",
            name="ck_redaction_audits_result",
        ),
        sa.CheckConstraint(
            "environment IN ('LOCAL','CI','STAGING','PRODUCTION')",
            name="ck_redaction_audits_environment",
        ),
        sa.CheckConstraint(
            "sample_count >= 0 AND forbidden_content_failures >= 0",
            name="ck_redaction_audits_counts_nonneg",
        ),
    )
    op.create_index("idx_redaction_audits_environment", "redaction_audits", ["environment"])
    op.create_index("idx_redaction_audits_result", "redaction_audits", ["result"])
    op.create_index("idx_redaction_audits_created_at", "redaction_audits", ["created_at"])

    # ── RLS on user-scoped tables ───────────────────────────────────────────
    _enable_rls("eval_runs")
    _enable_rls("eval_case_results")
    _enable_rls("langsmith_experiment_refs")
    _enable_rls("trace_run_refs")
    _enable_rls("product_funnel_events")
    _enable_rls("ai_invocation_records")
    _enable_rls("pm_metric_snapshots")
    _enable_rls("badcases")
    # badcase_review_actions cascades from badcases; gate by user_id lookup
    # via the parent badcase. We deliberately do NOT add a direct user_id
    # column to keep the schema compact; RLS via current_setting will return
    # no rows because the action is only visible when its parent badcase is
    # visible (FK + ondelete CASCADE handles the lifetime). To make the
    # isolation explicit at the SQL layer, we use a sub-select policy.
    op.execute("ALTER TABLE badcase_review_actions ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE badcase_review_actions FORCE ROW LEVEL SECURITY;")
    op.execute(
        "CREATE POLICY badcase_review_actions_user_isolation "
        "ON badcase_review_actions "
        "USING ("
        "EXISTS (SELECT 1 FROM badcases b "
        "WHERE b.badcase_id = badcase_review_actions.badcase_id "
        "AND b.user_id = current_setting('app.user_id', true)::uuid)"
        ") WITH CHECK ("
        "EXISTS (SELECT 1 FROM badcases b "
        "WHERE b.badcase_id = badcase_review_actions.badcase_id "
        "AND b.user_id = current_setting('app.user_id', true)::uuid)"
        ");"
    )


def downgrade() -> None:
    # Drop RLS policies + tables in reverse order
    op.execute("DROP POLICY IF EXISTS badcase_review_actions_user_isolation ON badcase_review_actions;")
    op.execute("ALTER TABLE IF EXISTS badcase_review_actions DISABLE ROW LEVEL SECURITY;")
    for tbl in (
        "redaction_audits",
        "redaction_policies",
        "badcase_review_actions",
        "badcases",
        "pm_metric_snapshots",
        "ai_invocation_records",
        "product_funnel_events",
        "trace_run_refs",
        "langsmith_experiment_refs",
        "eval_case_results",
        "eval_runs",
    ):
        op.execute(f"DROP POLICY IF EXISTS {tbl}_user_isolation ON {tbl};")
        op.execute(f"ALTER TABLE IF EXISTS {tbl} DISABLE ROW LEVEL SECURITY;")
        op.drop_table(tbl)