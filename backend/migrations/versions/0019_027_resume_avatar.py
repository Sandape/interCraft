"""Add avatar fields to resume_branches (REQ-027 US9).

Revision ID: 0019_resume_avatar
Revises: 0018_agent_memory
Create Date: 2026-06-24

Adds 4 nullable columns + CHECK constraints for size/position/shape
enumeration. avatar_updated_at is auto-set on row update.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0019_resume_avatar"
down_revision = "0018_agent_memory"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "resume_branches",
        sa.Column("avatar_url", sa.Text(), nullable=True),
    )
    # Size: pixel value for both width and height; range 50-200.
    op.add_column(
        "resume_branches",
        sa.Column("avatar_size", sa.SmallInteger(), nullable=True),
    )
    # Position: where to inject the avatar in the rendered preview.
    op.add_column(
        "resume_branches",
        sa.Column("avatar_position", sa.String(16), nullable=True),
    )
    # Shape: visual treatment for the img.
    op.add_column(
        "resume_branches",
        sa.Column("avatar_shape", sa.String(16), nullable=True),
    )
    op.add_column(
        "resume_branches",
        sa.Column(
            "avatar_updated_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    op.create_check_constraint(
        "ck_resume_branches_avatar_size",
        "resume_branches",
        "avatar_size IS NULL OR (avatar_size >= 50 AND avatar_size <= 200)",
    )
    op.create_check_constraint(
        "ck_resume_branches_avatar_position",
        "resume_branches",
        "avatar_position IS NULL OR avatar_position IN "
        "('left', 'right', 'top', 'center', 'bottom')",
    )
    op.create_check_constraint(
        "ck_resume_branches_avatar_shape",
        "resume_branches",
        "avatar_shape IS NULL OR avatar_shape IN ('circle', 'rounded', 'square')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_resume_branches_avatar_shape", "resume_branches", type_="check")
    op.drop_constraint("ck_resume_branches_avatar_position", "resume_branches", type_="check")
    op.drop_constraint("ck_resume_branches_avatar_size", "resume_branches", type_="check")
    op.drop_column("resume_branches", "avatar_updated_at")
    op.drop_column("resume_branches", "avatar_shape")
    op.drop_column("resume_branches", "avatar_position")
    op.drop_column("resume_branches", "avatar_size")
    op.drop_column("resume_branches", "avatar_url")
