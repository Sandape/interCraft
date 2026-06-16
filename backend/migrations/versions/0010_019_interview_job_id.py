"""Add interview_sessions.job_id column (Feature 019 — Job→Interview linking).

Revision ID: 0010_019_interview_job_id
Revises: 0009_019_job_fields
Create Date: 2026-06-17
"""
from __future__ import annotations

from alembic import op

revision = "0010_interview_job_id"
down_revision = "0009_job_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE interview_sessions "
        "ADD COLUMN IF NOT EXISTS job_id UUID REFERENCES jobs(id) ON DELETE SET NULL"
    )
    op.create_index(
        "ix_interview_sessions_job_id",
        "interview_sessions",
        ["job_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_interview_sessions_job_id", table_name="interview_sessions")
    op.execute("ALTER TABLE interview_sessions DROP COLUMN IF EXISTS job_id")
