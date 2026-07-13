"""Create account notifications table with tenant RLS (Issue #72).

Revision ID: 0054_account_notifications
Revises: 0053_jobs_branch_v2
Create Date: 2026-07-13
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

revision: str = "0054_account_notifications"
down_revision: str | None = "0053_jobs_branch_v2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the ORM-backed notification store and enforce tenant isolation."""
    op.create_table(
        "notifications",
        sa.Column(
            "id",
            PG_UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("related_task_id", PG_UUID(as_uuid=True), nullable=True),
        sa.Column(
            "is_read",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id", name="notifications_pkey"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="notifications_user_id_fkey",
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    op.execute(
        "CREATE INDEX ix_notifications_user_unread_recent "
        "ON notifications (user_id, created_at DESC) WHERE is_read = FALSE;"
    )

    op.execute("ALTER TABLE notifications ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE notifications FORCE ROW LEVEL SECURITY;")
    op.execute(
        "CREATE POLICY notifications_user_isolation ON notifications "
        "USING (user_id = NULLIF(current_setting('app.user_id', true), '')::uuid) "
        "WITH CHECK (user_id = NULLIF(current_setting('app.user_id', true), '')::uuid);"
    )


def downgrade() -> None:
    """Remove the notification store without leaving a FORCE-RLS shell."""
    op.execute("DROP POLICY IF EXISTS notifications_user_isolation ON notifications;")
    op.execute("DROP INDEX IF EXISTS ix_notifications_user_unread_recent;")
    op.drop_index("ix_notifications_user_id", table_name="notifications")
    op.drop_table("notifications")
