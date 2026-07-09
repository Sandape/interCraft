"""Drop archived_at column from error_questions table (Feature 024 US4).

Revision ID: 0014_drop_archived_at
Revises: 0013_jobs_offer_fields
Create Date: 2026-06-22
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0014_drop_archived_at"
down_revision = "0013_jobs_offer_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("error_questions", "archived_at")


def downgrade() -> None:
    op.add_column(
        "error_questions",
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
    )
