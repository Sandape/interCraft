"""REQ-055: Resume root/derive columns + resume_derive_runs.

Adds:
- resumes_v2.resume_kind / root_resume_id / job_id / root_version_at_derive /
  target_page_count / actual_page_count / derive_meta
- partial unique one-root-per-user
- resume_derive_runs async generation table
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID

revision = "0049_055_resume_root_derive"
down_revision = "0048_053_relax_interview_reports_for_research"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "resumes_v2",
        sa.Column(
            "resume_kind",
            sa.Text(),
            nullable=False,
            server_default="standard",
        ),
    )
    op.add_column(
        "resumes_v2",
        sa.Column("root_resume_id", PG_UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "resumes_v2",
        sa.Column("job_id", PG_UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "resumes_v2",
        sa.Column("root_version_at_derive", sa.Integer(), nullable=True),
    )
    op.add_column(
        "resumes_v2",
        sa.Column("target_page_count", sa.SmallInteger(), nullable=True),
    )
    op.add_column(
        "resumes_v2",
        sa.Column("actual_page_count", sa.SmallInteger(), nullable=True),
    )
    op.add_column(
        "resumes_v2",
        sa.Column(
            "derive_meta",
            JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )

    op.create_check_constraint(
        "ck_resumes_v2_resume_kind",
        "resumes_v2",
        "resume_kind IN ('root', 'derived', 'standard')",
    )
    op.create_check_constraint(
        "ck_resumes_v2_derived_fields",
        "resumes_v2",
        "resume_kind <> 'derived' OR ("
        "root_resume_id IS NOT NULL AND job_id IS NOT NULL "
        "AND target_page_count IN (1, 2, 3))",
    )
    op.create_check_constraint(
        "ck_resumes_v2_root_fields",
        "resumes_v2",
        "resume_kind <> 'root' OR ("
        "root_resume_id IS NULL AND job_id IS NULL AND target_page_count IS NULL)",
    )

    op.create_foreign_key(
        "fk_resumes_v2_root_resume_id",
        "resumes_v2",
        "resumes_v2",
        ["root_resume_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_resumes_v2_job_id",
        "resumes_v2",
        "jobs",
        ["job_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_index(
        "uq_resumes_v2_one_root_per_user",
        "resumes_v2",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("resume_kind = 'root'"),
    )
    op.create_index(
        "idx_resumes_v2_user_kind",
        "resumes_v2",
        ["user_id", "resume_kind"],
    )
    op.create_index(
        "idx_resumes_v2_job_derived",
        "resumes_v2",
        ["job_id"],
        postgresql_where=sa.text("resume_kind = 'derived'"),
    )

    op.create_table(
        "resume_derive_runs",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "job_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "root_resume_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("resumes_v2.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("root_version", sa.Integer(), nullable=False),
        sa.Column("target_page_count", sa.SmallInteger(), nullable=False),
        sa.Column("template_id", sa.Text(), nullable=False, server_default="pikachu"),
        sa.Column(
            "derived_resume_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("resumes_v2.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("phase", sa.Text(), nullable=False, server_default="parse_jd"),
        sa.Column("calibrate_round", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("progress_pct", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "artifacts",
            JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'succeeded', 'needs_guidance', 'failed', 'canceled')",
            name="ck_resume_derive_runs_status",
        ),
        sa.CheckConstraint(
            "target_page_count IN (1, 2, 3)",
            name="ck_resume_derive_runs_pages",
        ),
    )
    op.create_index(
        "idx_resume_derive_runs_user_status",
        "resume_derive_runs",
        ["user_id", "status"],
    )
    op.create_index(
        "idx_resume_derive_runs_job_id",
        "resume_derive_runs",
        ["job_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_resume_derive_runs_job_id", table_name="resume_derive_runs")
    op.drop_index("idx_resume_derive_runs_user_status", table_name="resume_derive_runs")
    op.drop_table("resume_derive_runs")

    op.drop_index("idx_resumes_v2_job_derived", table_name="resumes_v2")
    op.drop_index("idx_resumes_v2_user_kind", table_name="resumes_v2")
    op.drop_index("uq_resumes_v2_one_root_per_user", table_name="resumes_v2")
    op.drop_constraint("fk_resumes_v2_job_id", "resumes_v2", type_="foreignkey")
    op.drop_constraint("fk_resumes_v2_root_resume_id", "resumes_v2", type_="foreignkey")
    op.drop_constraint("ck_resumes_v2_root_fields", "resumes_v2", type_="check")
    op.drop_constraint("ck_resumes_v2_derived_fields", "resumes_v2", type_="check")
    op.drop_constraint("ck_resumes_v2_resume_kind", "resumes_v2", type_="check")
    op.drop_column("resumes_v2", "derive_meta")
    op.drop_column("resumes_v2", "actual_page_count")
    op.drop_column("resumes_v2", "target_page_count")
    op.drop_column("resumes_v2", "root_version_at_derive")
    op.drop_column("resumes_v2", "job_id")
    op.drop_column("resumes_v2", "root_resume_id")
    op.drop_column("resumes_v2", "resume_kind")
