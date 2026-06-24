"""Add theme_id and accent_color columns to resume_branches (REQ-027).

Revision ID: 0017_resume_theme
Revises: 0016_interview_plan
Create Date: 2026-06-24
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0017_resume_theme"
down_revision = "0016_interview_plan"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "resume_branches",
        sa.Column("theme_id", sa.String(32), nullable=False, server_default="default"),
    )
    op.add_column(
        "resume_branches",
        sa.Column("accent_color", sa.String(7), nullable=False, server_default="#39393a"),
    )
    # CHECK constraints: theme_id must be one of the 4 registered themes;
    # accent_color must be a valid HEX (#RRGGBB).
    op.create_check_constraint(
        "ck_resume_branches_theme_id",
        "resume_branches",
        "theme_id IN ('default', 'blue', 'orange', 'pupple')",
    )
    op.create_check_constraint(
        "ck_resume_branches_accent_color",
        "resume_branches",
        "accent_color ~ '^#[0-9a-fA-F]{6}$'",
    )


def downgrade() -> None:
    op.drop_constraint("ck_resume_branches_accent_color", "resume_branches", type_="check")
    op.drop_constraint("ck_resume_branches_theme_id", "resume_branches", type_="check")
    op.drop_column("resume_branches", "accent_color")
    op.drop_column("resume_branches", "theme_id")
