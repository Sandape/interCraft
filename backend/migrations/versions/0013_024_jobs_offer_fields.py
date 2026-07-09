"""Add 4 offer fields to jobs table (Feature 024 — offer_salary_text / offer_contact_name / offer_contact_info / offer_deadline_at).

Revision ID: 0013_jobs_offer_fields
Revises: 0012_error_questions_idx
Create Date: 2026-06-22
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0013_jobs_offer_fields"
down_revision = "0012_error_questions_idx"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "jobs",
        sa.Column("offer_salary_text", sa.Text(), nullable=True),
    )
    op.add_column(
        "jobs",
        sa.Column("offer_contact_name", sa.Text(), nullable=True),
    )
    op.add_column(
        "jobs",
        sa.Column("offer_contact_info", sa.Text(), nullable=True),
    )
    op.add_column(
        "jobs",
        sa.Column("offer_deadline_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("jobs", "offer_deadline_at")
    op.drop_column("jobs", "offer_contact_info")
    op.drop_column("jobs", "offer_contact_name")
    op.drop_column("jobs", "offer_salary_text")
