"""Create profile_share_links, profile_views, export_logs tables.

Revision ID: 0007_ability_profile
Revises: 0006_user_profile_bio
Create Date: 2026-06-16
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0007_ability_profile"
down_revision = "0006_user_profile_bio"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # profile_share_links
    op.create_table(
        "profile_share_links",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("token", sa.Text(), nullable=False),
        sa.Column("pin_hash", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_accessed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("access_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("token", name="uq_profile_share_links_token"),
    )
    op.create_check_constraint(
        "ck_share_links_token_length",
        "profile_share_links",
        sa.text("length(token) = 36"),
    )
    op.create_check_constraint(
        "ck_share_links_revoked_before_expires",
        "profile_share_links",
        sa.text("revoked_at IS NULL OR expires_at IS NULL OR revoked_at < expires_at"),
    )
    op.create_check_constraint(
        "ck_share_links_access_count",
        "profile_share_links",
        sa.text("access_count >= 0"),
    )
    op.create_index("idx_share_links_token", "profile_share_links", ["token"], unique=True)
    op.create_index("idx_share_links_user_id", "profile_share_links", ["user_id"])
    op.create_index(
        "idx_share_links_active",
        "profile_share_links",
        ["user_id"],
        postgresql_where=sa.text("revoked_at IS NULL"),
    )

    # profile_views (append-only access log)
    op.create_table(
        "profile_views",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("share_link_id", sa.UUID(), nullable=False),
        sa.Column("ip_prefix", sa.Text(), nullable=False),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("pin_verified", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("viewed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["share_link_id"], ["profile_share_links.id"], ondelete="CASCADE"),
    )
    op.create_check_constraint(
        "ck_profile_views_ip_prefix_length",
        "profile_views",
        sa.text("length(ip_prefix) BETWEEN 3 AND 45"),
    )
    op.create_index(
        "idx_profile_views_share_link",
        "profile_views",
        ["share_link_id", sa.text("viewed_at DESC")],
    )

    # export_logs
    op.create_table(
        "export_logs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("file_path", sa.Text(), nullable=True),
        sa.Column("file_size_bytes", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now() + sa.text("interval '24 hours'")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_check_constraint(
        "ck_export_logs_status",
        "export_logs",
        sa.text("status IN ('pending','processing','completed','failed')"),
    )
    op.create_check_constraint(
        "ck_export_logs_file_size",
        "export_logs",
        sa.text("file_size_bytes IS NULL OR file_size_bytes > 0"),
    )
    op.create_check_constraint(
        "ck_export_logs_completed_at",
        "export_logs",
        sa.text("completed_at IS NULL OR completed_at >= requested_at"),
    )
    op.create_check_constraint(
        "ck_export_logs_completed_has_file",
        "export_logs",
        sa.text("status != 'completed' OR file_path IS NOT NULL"),
    )
    op.create_index("idx_export_logs_user", "export_logs", ["user_id", sa.text("requested_at DESC")])
    op.create_index(
        "idx_export_logs_expires",
        "export_logs",
        ["expires_at"],
        postgresql_where=sa.text("status = 'completed'"),
    )


def downgrade() -> None:
    op.drop_table("export_logs")
    op.drop_table("profile_views")
    op.drop_table("profile_share_links")
