"""Publish the REQ-059 resume-intelligence schema (Issue #76).

Revision ID: 0055_059_ai_resume
Revises: 0054_account_notifications
Create Date: 2026-07-13
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

revision: str = "0055_059_ai_resume"
down_revision: str | None = "0054_account_notifications"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TENANT_TABLES = (
    "resume_derive_runs",
    "resume_fit_analyses",
    "resume_ai_suggestions",
    "resume_ai_change_sets",
    "resume_ai_feedback",
)


def _enable_tenant_rls(table: str) -> None:
    op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY;')
    op.execute(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY;')
    op.execute(
        f'CREATE POLICY "{table}_tenant_isolation" ON "{table}" '
        "USING (user_id = NULLIF(current_setting('app.user_id', true), '')::uuid) "
        "WITH CHECK (user_id = NULLIF(current_setting('app.user_id', true), '')::uuid);"
    )


def upgrade() -> None:
    """Extend derive runs and create the four tenant-scoped intelligence tables."""
    op.drop_constraint("resume_derive_runs_job_id_fkey", "resume_derive_runs", type_="foreignkey")
    op.alter_column(
        "resume_derive_runs",
        "job_id",
        existing_type=PG_UUID(as_uuid=True),
        existing_nullable=False,
        nullable=True,
    )
    op.create_foreign_key(
        "resume_derive_runs_job_id_fkey",
        "resume_derive_runs",
        "jobs",
        ["job_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.drop_constraint("ck_resume_derive_runs_status", "resume_derive_runs", type_="check")
    op.create_check_constraint(
        "ck_resume_derive_runs_status",
        "resume_derive_runs",
        "status IN ('pending','queued','running','succeeded','partial_success',"
        "'needs_guidance','canceling','cancelled','failed','canceled')",
    )

    for column in (
        sa.Column("root_hash", sa.Text(), nullable=True),
        sa.Column("jd_hash", sa.Text(), nullable=True),
        sa.Column(
            "root_snapshot",
            JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "job_snapshot",
            JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("idempotency_key", sa.Text(), nullable=True),
        sa.Column("request_hash", sa.Text(), nullable=True),
        sa.Column("input_fingerprint", sa.Text(), nullable=True),
        sa.Column(
            "component_status",
            JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("analysis_id", PG_UUID(as_uuid=True), nullable=True),
        sa.Column("prompt_version", sa.Text(), nullable=True),
        sa.Column("schema_version", sa.Text(), nullable=True),
        sa.Column("scoring_version", sa.Text(), nullable=True),
        sa.Column("cancel_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
    ):
        op.add_column("resume_derive_runs", column)

    op.create_unique_constraint("uq_jobs_user_id_id", "jobs", ["user_id", "id"])
    op.create_unique_constraint("uq_resumes_v2_user_id_id", "resumes_v2", ["user_id", "id"])
    op.create_unique_constraint(
        "uq_resume_derive_runs_user_id_id",
        "resume_derive_runs",
        ["user_id", "id"],
    )
    op.create_foreign_key(
        "fk_resume_derive_runs_job_tenant",
        "resume_derive_runs",
        "jobs",
        ["user_id", "job_id"],
        ["user_id", "id"],
    )
    op.create_foreign_key(
        "fk_resume_derive_runs_root_resume_tenant",
        "resume_derive_runs",
        "resumes_v2",
        ["user_id", "root_resume_id"],
        ["user_id", "id"],
    )
    op.create_foreign_key(
        "fk_resume_derive_runs_derived_resume_tenant",
        "resume_derive_runs",
        "resumes_v2",
        ["user_id", "derived_resume_id"],
        ["user_id", "id"],
    )

    op.create_index(
        "uq_resume_derive_runs_user_idempotency",
        "resume_derive_runs",
        ["user_id", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )
    op.create_index(
        "idx_resume_derive_runs_input_fingerprint",
        "resume_derive_runs",
        ["user_id", "input_fingerprint"],
    )

    op.create_table(
        "resume_fit_analyses",
        sa.Column("id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("resume_id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("resume_version", sa.Integer(), nullable=False),
        sa.Column("resume_hash", sa.Text(), nullable=False),
        sa.Column("mode", sa.Text(), nullable=False),
        sa.Column("job_id", PG_UUID(as_uuid=True), nullable=True),
        sa.Column("jd_hash", sa.Text(), nullable=True),
        sa.Column(
            "job_snapshot",
            JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("run_id", PG_UUID(as_uuid=True), nullable=True),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'queued'::text"),
        ),
        sa.Column("overall_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("confidence_score", sa.Numeric(4, 3), nullable=True),
        sa.Column("confidence_band", sa.Text(), nullable=True),
        sa.Column(
            "dimensions",
            JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "requirements",
            JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "summary",
            JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "hard_blockers",
            JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "source_manifest",
            JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "quality_flags",
            JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "scoring_version",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'scoring.v1'::text"),
        ),
        sa.Column(
            "prompt_version",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'resume-intelligence.v1'::text"),
        ),
        sa.Column(
            "schema_version",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'analysis.v1'::text"),
        ),
        sa.Column("input_fingerprint", sa.Text(), nullable=False),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column(
            "error_detail_safe",
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
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="resume_fit_analyses_pkey"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="resume_fit_analyses_user_id_fkey",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["resume_id"],
            ["resumes_v2.id"],
            name="resume_fit_analyses_resume_id_fkey",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["jobs.id"],
            name="resume_fit_analyses_job_id_fkey",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["resume_derive_runs.id"],
            name="resume_fit_analyses_run_id_fkey",
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint("user_id", "id", name="uq_resume_fit_analyses_user_id_id"),
        sa.ForeignKeyConstraint(
            ["user_id", "resume_id"],
            ["resumes_v2.user_id", "resumes_v2.id"],
            name="fk_resume_fit_analyses_resume_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["user_id", "job_id"],
            ["jobs.user_id", "jobs.id"],
            name="fk_resume_fit_analyses_job_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["user_id", "run_id"],
            ["resume_derive_runs.user_id", "resume_derive_runs.id"],
            name="fk_resume_fit_analyses_run_tenant",
        ),
        sa.CheckConstraint("mode IN ('general','job_fit')", name="ck_resume_fit_analyses_mode"),
        sa.CheckConstraint(
            "status IN ('queued','running','complete','partial','failed','cancelled')",
            name="ck_resume_fit_analyses_status",
        ),
        sa.CheckConstraint(
            "overall_score IS NULL OR (overall_score >= 0 AND overall_score <= 100)",
            name="ck_resume_fit_analyses_score",
        ),
        sa.CheckConstraint(
            "confidence_score IS NULL OR (confidence_score >= 0 AND confidence_score <= 1)",
            name="ck_resume_fit_analyses_confidence",
        ),
    )
    op.create_index(
        "idx_resume_fit_analyses_resume_history",
        "resume_fit_analyses",
        ["user_id", "resume_id", "created_at"],
    )
    op.create_index("idx_resume_fit_analyses_run", "resume_fit_analyses", ["run_id"])

    op.create_table(
        "resume_ai_suggestions",
        sa.Column("id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("analysis_id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("resume_id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("base_resume_version", sa.Integer(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("action_mode", sa.Text(), nullable=False),
        sa.Column("priority", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("anchor", JSONB(), nullable=False),
        sa.Column(
            "source_refs",
            JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "requirement_refs",
            JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "proposed_patch",
            JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "page_impact",
            JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'open'::text"),
        ),
        sa.Column("applied_change_set_id", PG_UUID(as_uuid=True), nullable=True),
        sa.Column("status_reason", sa.Text(), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name="resume_ai_suggestions_pkey"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="resume_ai_suggestions_user_id_fkey",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["analysis_id"],
            ["resume_fit_analyses.id"],
            name="resume_ai_suggestions_analysis_id_fkey",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["resume_id"],
            ["resumes_v2.id"],
            name="resume_ai_suggestions_resume_id_fkey",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("user_id", "id", name="uq_resume_ai_suggestions_user_id_id"),
        sa.ForeignKeyConstraint(
            ["user_id", "analysis_id"],
            ["resume_fit_analyses.user_id", "resume_fit_analyses.id"],
            name="fk_resume_ai_suggestions_analysis_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["user_id", "resume_id"],
            ["resumes_v2.user_id", "resumes_v2.id"],
            name="fk_resume_ai_suggestions_resume_tenant",
        ),
        sa.CheckConstraint(
            "status IN ('open','previewed','applied','ignored','deferred','stale',"
            "'conflict','withdrawn','undone')",
            name="ck_resume_ai_suggestions_status",
        ),
    )
    op.create_index(
        "idx_resume_ai_suggestions_analysis_status",
        "resume_ai_suggestions",
        ["analysis_id", "status"],
    )
    op.create_index(
        "idx_resume_ai_suggestions_resume",
        "resume_ai_suggestions",
        ["user_id", "resume_id"],
    )

    op.create_table(
        "resume_ai_change_sets",
        sa.Column("id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("resume_id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("analysis_id", PG_UUID(as_uuid=True), nullable=True),
        sa.Column("base_resume_version", sa.Integer(), nullable=False),
        sa.Column("result_resume_version", sa.Integer(), nullable=False),
        sa.Column(
            "suggestion_ids",
            JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "forward_patch",
            JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "inverse_patch",
            JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("before_hash", sa.Text(), nullable=False),
        sa.Column("after_hash", sa.Text(), nullable=False),
        sa.Column("preview_digest", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'applied'::text"),
        ),
        sa.Column("undo_of_change_set_id", PG_UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("undone_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="resume_ai_change_sets_pkey"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="resume_ai_change_sets_user_id_fkey",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["resume_id"],
            ["resumes_v2.id"],
            name="resume_ai_change_sets_resume_id_fkey",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["analysis_id"],
            ["resume_fit_analyses.id"],
            name="resume_ai_change_sets_analysis_id_fkey",
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint("user_id", "id", name="uq_resume_ai_change_sets_user_id_id"),
        sa.ForeignKeyConstraint(
            ["user_id", "resume_id"],
            ["resumes_v2.user_id", "resumes_v2.id"],
            name="fk_resume_ai_change_sets_resume_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["user_id", "analysis_id"],
            ["resume_fit_analyses.user_id", "resume_fit_analyses.id"],
            name="fk_resume_ai_change_sets_analysis_tenant",
        ),
        sa.UniqueConstraint(
            "resume_id",
            "result_resume_version",
            name="uq_resume_ai_change_sets_result_version",
        ),
        sa.UniqueConstraint(
            "user_id",
            "idempotency_key",
            name="uq_resume_ai_change_sets_idempotency",
        ),
        sa.CheckConstraint(
            "status IN ('applied','undone','superseded')",
            name="ck_resume_ai_change_sets_status",
        ),
    )
    op.create_index(
        "idx_resume_ai_change_sets_history",
        "resume_ai_change_sets",
        ["user_id", "resume_id", "created_at"],
    )

    op.create_table(
        "resume_ai_feedback",
        sa.Column("id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("analysis_id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("suggestion_id", PG_UUID(as_uuid=True), nullable=True),
        sa.Column("change_set_id", PG_UUID(as_uuid=True), nullable=True),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id", name="resume_ai_feedback_pkey"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="resume_ai_feedback_user_id_fkey",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["analysis_id"],
            ["resume_fit_analyses.id"],
            name="resume_ai_feedback_analysis_id_fkey",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["suggestion_id"],
            ["resume_ai_suggestions.id"],
            name="resume_ai_feedback_suggestion_id_fkey",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["change_set_id"],
            ["resume_ai_change_sets.id"],
            name="resume_ai_feedback_change_set_id_fkey",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id", "analysis_id"],
            ["resume_fit_analyses.user_id", "resume_fit_analyses.id"],
            name="fk_resume_ai_feedback_analysis_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["user_id", "suggestion_id"],
            ["resume_ai_suggestions.user_id", "resume_ai_suggestions.id"],
            name="fk_resume_ai_feedback_suggestion_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["user_id", "change_set_id"],
            ["resume_ai_change_sets.user_id", "resume_ai_change_sets.id"],
            name="fk_resume_ai_feedback_change_set_tenant",
        ),
        sa.CheckConstraint(
            "category IN ('helpful','not_applicable','repeated','poor_wording',"
            "'fact_error','other')",
            name="ck_resume_ai_feedback_category",
        ),
        sa.CheckConstraint(
            "comment IS NULL OR length(comment) <= 1000",
            name="ck_resume_ai_feedback_comment_length",
        ),
    )
    op.create_index(
        "idx_resume_ai_feedback_analysis",
        "resume_ai_feedback",
        ["user_id", "analysis_id", "created_at"],
    )

    op.create_foreign_key(
        "fk_resume_derive_runs_analysis_id",
        "resume_derive_runs",
        "resume_fit_analyses",
        ["analysis_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_resume_derive_runs_analysis_tenant",
        "resume_derive_runs",
        "resume_fit_analyses",
        ["user_id", "analysis_id"],
        ["user_id", "id"],
    )
    op.create_foreign_key(
        "fk_resume_ai_suggestions_change_set",
        "resume_ai_suggestions",
        "resume_ai_change_sets",
        ["applied_change_set_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_resume_ai_suggestions_change_set_tenant",
        "resume_ai_suggestions",
        "resume_ai_change_sets",
        ["user_id", "applied_change_set_id"],
        ["user_id", "id"],
    )
    op.create_foreign_key(
        "fk_resume_ai_change_sets_undo_of",
        "resume_ai_change_sets",
        "resume_ai_change_sets",
        ["undo_of_change_set_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_resume_ai_change_sets_undo_of_tenant",
        "resume_ai_change_sets",
        "resume_ai_change_sets",
        ["user_id", "undo_of_change_set_id"],
        ["user_id", "id"],
    )

    for table in TENANT_TABLES:
        _enable_tenant_rls(table)


def downgrade() -> None:
    """Restore the true 0054 derive schema without retaining REQ-059 RLS."""
    # Inspect every tenant row before narrowing the 0054 constraints. PostgreSQL
    # transactional DDL restores the RLS state automatically if this preflight
    # raises, so an incompatible downgrade fails without partially changing data.
    op.execute('ALTER TABLE "resume_derive_runs" NO FORCE ROW LEVEL SECURITY;')
    op.execute('ALTER TABLE "resume_derive_runs" DISABLE ROW LEVEL SECURITY;')
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM resume_derive_runs
                WHERE job_id IS NULL
                   OR status NOT IN (
                       'pending', 'running', 'succeeded', 'needs_guidance',
                       'failed', 'canceled'
                   )
            ) THEN
                RAISE EXCEPTION
                    'Cannot downgrade REQ-059: derive rows are incompatible with 0054';
            END IF;
        END
        $$;
        """
    )

    for table in reversed(TENANT_TABLES):
        op.execute(f'DROP POLICY IF EXISTS "{table}_tenant_isolation" ON "{table}";')

    op.drop_constraint(
        "fk_resume_ai_change_sets_undo_of_tenant",
        "resume_ai_change_sets",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_resume_ai_change_sets_undo_of",
        "resume_ai_change_sets",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_resume_ai_suggestions_change_set_tenant",
        "resume_ai_suggestions",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_resume_ai_suggestions_change_set",
        "resume_ai_suggestions",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_resume_derive_runs_analysis_tenant",
        "resume_derive_runs",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_resume_derive_runs_analysis_id",
        "resume_derive_runs",
        type_="foreignkey",
    )
    op.drop_table("resume_ai_feedback")
    op.drop_table("resume_ai_suggestions")
    op.drop_table("resume_ai_change_sets")
    op.drop_table("resume_fit_analyses")

    op.drop_constraint(
        "fk_resume_derive_runs_derived_resume_tenant",
        "resume_derive_runs",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_resume_derive_runs_root_resume_tenant",
        "resume_derive_runs",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_resume_derive_runs_job_tenant",
        "resume_derive_runs",
        type_="foreignkey",
    )
    op.drop_constraint(
        "uq_resume_derive_runs_user_id_id",
        "resume_derive_runs",
        type_="unique",
    )
    op.drop_constraint("uq_resumes_v2_user_id_id", "resumes_v2", type_="unique")
    op.drop_constraint("uq_jobs_user_id_id", "jobs", type_="unique")

    op.drop_index("idx_resume_derive_runs_input_fingerprint", table_name="resume_derive_runs")
    op.drop_index("uq_resume_derive_runs_user_idempotency", table_name="resume_derive_runs")
    for column in (
        "published_at",
        "cancel_requested_at",
        "scoring_version",
        "schema_version",
        "prompt_version",
        "analysis_id",
        "component_status",
        "input_fingerprint",
        "request_hash",
        "idempotency_key",
        "job_snapshot",
        "root_snapshot",
        "jd_hash",
        "root_hash",
    ):
        op.drop_column("resume_derive_runs", column)

    op.drop_constraint("ck_resume_derive_runs_status", "resume_derive_runs", type_="check")
    op.create_check_constraint(
        "ck_resume_derive_runs_status",
        "resume_derive_runs",
        "status IN ('pending', 'running', 'succeeded', 'needs_guidance', 'failed', 'canceled')",
    )
    op.drop_constraint("resume_derive_runs_job_id_fkey", "resume_derive_runs", type_="foreignkey")
    op.alter_column(
        "resume_derive_runs",
        "job_id",
        existing_type=PG_UUID(as_uuid=True),
        existing_nullable=True,
        nullable=False,
    )
    op.create_foreign_key(
        "resume_derive_runs_job_id_fkey",
        "resume_derive_runs",
        "jobs",
        ["job_id"],
        ["id"],
        ondelete="CASCADE",
    )
