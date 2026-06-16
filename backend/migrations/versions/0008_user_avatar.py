"""Add user_avatars table and users.avatar_id FK (Feature 013).

Revision ID: 0008_user_avatar
Revises: 0007_ability_profile
Create Date: 2026-06-16
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0008_user_avatar"
down_revision = "0007_ability_profile"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_avatars",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("content_type", sa.Text(), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("storage_path", sa.Text(), nullable=False, unique=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "content_type IN ('image/jpeg', 'image/png')",
            name="ck_user_avatars_content_type",
        ),
        sa.CheckConstraint(
            "byte_size > 0 AND byte_size <= 2097152",
            name="ck_user_avatars_byte_size",
        ),
        sa.CheckConstraint(
            "width IS NULL OR (width > 0 AND width <= 2048)",
            name="ck_user_avatars_width",
        ),
        sa.CheckConstraint(
            "height IS NULL OR (height > 0 AND height <= 2048)",
            name="ck_user_avatars_height",
        ),
    )
    op.create_index(
        "ix_user_avatars_user_id_created_at",
        "user_avatars",
        ["user_id", sa.text("created_at DESC")],
    )

    op.add_column(
        "users",
        sa.Column(
            "avatar_id",
            UUID(as_uuid=True),
            sa.ForeignKey("user_avatars.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "avatar_id")
    op.drop_index("ix_user_avatars_user_id_created_at", table_name="user_avatars")
    op.drop_table("user_avatars")
