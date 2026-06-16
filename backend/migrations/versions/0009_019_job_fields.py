"""Add 5 fields to jobs table (Feature 019 — base_location / requirements_md / employment_type / salary_range_text / headcount).

Revision ID: 0009_019_job_fields
Revises: 0008_user_avatar
Create Date: 2026-06-17
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0009_job_fields"
down_revision = "0008_user_avatar"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "jobs",
        sa.Column("base_location", sa.Text(), nullable=False, server_default=""),
    )
    op.add_column(
        "jobs",
        sa.Column("requirements_md", sa.Text(), nullable=True),
    )
    op.add_column(
        "jobs",
        sa.Column(
            "employment_type",
            sa.Text(),
            nullable=False,
            server_default="unspecified",
        ),
    )
    op.add_column(
        "jobs",
        sa.Column("salary_range_text", sa.Text(), nullable=True),
    )
    op.add_column(
        "jobs",
        sa.Column("headcount", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("jobs", "headcount")
    op.drop_column("jobs", "salary_range_text")
    op.drop_column("jobs", "employment_type")
    op.drop_column("jobs", "requirements_md")
    op.drop_column("jobs", "base_location")
