"""REQ-053: Interview Intelligence Engine — interview_research_* tables + jobs.interview_time + interview_reports extension.

Adds:
- jobs.interview_time column (TIMESTAMPTZ, nullable) for interview-round states
- jobs.idx_jobs_interview_time partial index
- interview_research_tasks table (one row per scheduled research job)
- interview_research_results table (one row per search dimension executed)
- interview_reports extensions: report_type, job_id, interview_time, research_task_id, rating
- interview_reports.idx_report_job_id partial index

Status migration of existing job.status values is handled by the data migration
script (jobs.cli migrate-status) so that downgrade can rely on a note field
preserved in status_history.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID

revision = "0046_053_interview_research"
down_revision = "0045_llm_ops_eval_workflow"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. jobs.interview_time
    op.add_column(
        "jobs",
        sa.Column("interview_time", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "idx_jobs_interview_time",
        "jobs",
        ["interview_time"],
        postgresql_where=sa.text(
            "interview_time IS NOT NULL AND status IN ('test', 'interview_1', 'interview_2', 'interview_3')"
        ),
    )

    # 2. interview_research_tasks
    op.create_table(
        "interview_research_tasks",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True),
        sa.Column("job_id", PG_UUID(as_uuid=True), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", PG_UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("interview_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("search_dimensions", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("report_id", PG_UUID(as_uuid=True), nullable=True),
        sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'cancelled', 'failed', 'quality_failed')",
            name="ck_research_tasks_status",
        ),
        sa.UniqueConstraint("job_id", "interview_time", name="uq_research_tasks_job_interview"),
    )
    op.create_index("idx_research_tasks_status", "interview_research_tasks", ["status"])
    op.create_index("idx_research_tasks_user_id", "interview_research_tasks", ["user_id"])
    op.create_index("idx_research_tasks_interview_time", "interview_research_tasks", ["interview_time"])

    # 3. interview_research_results
    op.create_table(
        "interview_research_results",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True),
        sa.Column("task_id", PG_UUID(as_uuid=True), sa.ForeignKey("interview_research_tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("dimension", sa.String(length=30), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("results", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("result_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("company", sa.String(length=200), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("searched_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "dimension IN ('interview_experience', 'company_product', 'exam_points', 'user_weakness')",
            name="ck_research_results_dimension",
        ),
    )
    op.create_index("idx_research_results_task_id", "interview_research_results", ["task_id"])
    op.create_index(
        "idx_research_results_company_time",
        "interview_research_results",
        ["company", sa.text("searched_at DESC")],
        postgresql_where=sa.text("dimension IN ('interview_experience', 'company_product')"),
    )

    # 4. interview_reports extensions
    op.add_column(
        "interview_reports",
        sa.Column("report_type", sa.String(length=30), nullable=False, server_default="mock_interview"),
    )
    op.add_column(
        "interview_reports",
        sa.Column("job_id", PG_UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_report_job",
        "interview_reports",
        "jobs",
        ["job_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column(
        "interview_reports",
        sa.Column("interview_time", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "interview_reports",
        sa.Column("research_task_id", PG_UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_report_research_task",
        "interview_reports",
        "interview_research_tasks",
        ["research_task_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column(
        "interview_reports",
        sa.Column("rating", sa.SmallInteger(), nullable=True),
    )
    op.create_check_constraint(
        "ck_report_rating",
        "interview_reports",
        "rating IS NULL OR (rating >= 1 AND rating <= 5)",
    )
    op.add_column(
        "interview_reports",
        sa.Column("delivery_status", sa.String(length=20), nullable=True),
    )
    op.create_check_constraint(
        "ck_report_delivery_status",
        "interview_reports",
        "delivery_status IS NULL OR delivery_status IN ('pending', 'sent', 'failed', 'delayed', 'cancelled')",
    )
    op.add_column(
        "interview_reports",
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "interview_reports",
        sa.Column("quality_check_passed", sa.Boolean(), nullable=True),
    )
    op.create_index(
        "idx_report_job_id",
        "interview_reports",
        ["job_id"],
        postgresql_where=sa.text("report_type = 'pre_interview_research'"),
    )


def downgrade() -> None:
    op.drop_index("idx_report_job_id", table_name="interview_reports")
    op.drop_constraint("ck_report_delivery_status", "interview_reports", type_="check")
    op.drop_column("interview_reports", "quality_check_passed")
    op.drop_column("interview_reports", "delivered_at")
    op.drop_column("interview_reports", "delivery_status")
    op.drop_constraint("ck_report_rating", "interview_reports", type_="check")
    op.drop_column("interview_reports", "rating")
    op.drop_constraint("fk_report_research_task", "interview_reports", type_="foreignkey")
    op.drop_column("interview_reports", "research_task_id")
    op.drop_column("interview_reports", "interview_time")
    op.drop_constraint("fk_report_job", "interview_reports", type_="foreignkey")
    op.drop_column("interview_reports", "job_id")
    op.drop_column("interview_reports", "report_type")

    op.drop_index("idx_research_results_company_time", table_name="interview_research_results")
    op.drop_index("idx_research_results_task_id", table_name="interview_research_results")
    op.drop_table("interview_research_results")

    op.drop_index("idx_research_tasks_interview_time", table_name="interview_research_tasks")
    op.drop_index("idx_research_tasks_user_id", table_name="interview_research_tasks")
    op.drop_index("idx_research_tasks_status", table_name="interview_research_tasks")
    op.drop_table("interview_research_tasks")

    op.drop_index("idx_jobs_interview_time", table_name="jobs")
    op.drop_column("jobs", "interview_time")


__all__ = ["upgrade", "downgrade"]