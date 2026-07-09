"""Add interview_plan and web_research JSONB columns to interview_sessions (REQ-02).

Revision ID: 0016_interview_plan
Revises: 0015_drop_pin_and_profile_views
Create Date: 2026-06-23
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0016_interview_plan"
down_revision = "0015_drop_pin_and_profile_views"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "interview_sessions",
        sa.Column("interview_plan", postgresql.JSONB(), nullable=True),
    )
    op.add_column(
        "interview_sessions",
        sa.Column("web_research", postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("interview_sessions", "web_research")
    op.drop_column("interview_sessions", "interview_plan")
