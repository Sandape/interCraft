"""Phase 3 — lock_audit_logs append-only audit table.

Revision ID: 0003_phase3_lock_audit
Revises: 0002_phase2_entities
Create Date: 2026-06-13

Creates: lock_audit_logs (no RLS — Phase 3 Complexity Tracking)
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003_phase3_lock_audit"
down_revision = "0002_phase2_entities"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lock_audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("resource_type", sa.String(64), nullable=False),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("device_id", sa.String(128), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.String(16), nullable=False),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "action IN ('acquired','released','expired','heartbeat')",
            name="lock_audit_logs_action_chk",
        ),
    )
    op.create_index(
        "idx_lock_audit_resource",
        "lock_audit_logs",
        ["resource_type", "resource_id", sa.text("occurred_at DESC")],
    )
    op.create_index(
        "idx_lock_audit_user",
        "lock_audit_logs",
        ["user_id", sa.text("occurred_at DESC")],
    )
    # No RLS for lock_audit_logs — see phase-3.md Complexity Tracking


def downgrade() -> None:
    op.drop_index("idx_lock_audit_user", table_name="lock_audit_logs")
    op.drop_index("idx_lock_audit_resource", table_name="lock_audit_logs")
    op.drop_table("lock_audit_logs")
