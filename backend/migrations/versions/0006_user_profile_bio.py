"""Add bio to user profile.

Revision ID: 0006_user_profile_bio
Revises: 0005_phase6_global_capabilities
Create Date: 2026-06-15
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006_user_profile_bio"
down_revision = "0005_phase6_global_capabilities"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("bio", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "bio")
