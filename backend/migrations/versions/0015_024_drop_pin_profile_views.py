"""Remove pin_hash column + profile_views table (Feature 024 US5).

Revision ID: 0015_drop_pin_and_profile_views
Revises: 0014_drop_archived_at
Create Date: 2026-06-22
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0015_drop_pin_and_profile_views"
down_revision = "0014_drop_archived_at"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("profile_share_links", "pin_hash")
    op.drop_table("profile_views")


def downgrade() -> None:
    op.create_table(
        "profile_views",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("share_link_id", sa.UUID(), nullable=False),
        sa.Column("ip_prefix", sa.Text(), nullable=False),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("pin_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("viewed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["share_link_id"], ["profile_share_links.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("length(ip_prefix) BETWEEN 3 AND 45", name="ck_profile_views_ip_prefix_length"),
    )
    op.create_index(
        "idx_profile_views_share_link", "profile_views", ["share_link_id"],
        postgresql_using="btree",
    )
    op.add_column(
        "profile_share_links",
        sa.Column("pin_hash", sa.Text(), nullable=True),
    )
