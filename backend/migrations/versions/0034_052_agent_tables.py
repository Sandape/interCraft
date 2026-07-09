"""Create agent infrastructure tables (REQ-052, T001).

Six new tables for the Personal AI Agent + WeChat Channel feature:

  agents                 — 1:1 per user, agent lifecycle state
  wechat_credentials     — iLink bearer token, cursor, context_token (encrypted)
  wechat_bindings        — 1:1 WeChat UIN ↔ InterCraft user mapping
  agent_messages         — inbound/outbound message log (dual-storage: PG + Redis)
  agent_preferences      — per-user display_name, quiet_hours, notification_mode
  agent_status_history   — append-only audit log of status transitions

All user-data tables are RLS-enabled via the standard app.user_id GUC pattern.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0034_052_agent_tables"
down_revision = ("0033_interview_branch_v2", "0045_llm_ops_eval_workflow")
branch_labels = None
depends_on = None


def _enable_rls(table: str) -> None:
    """Per-user RLS using app.user_id GUC."""
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;")
    op.execute(
        f"CREATE POLICY {table}_user_isolation ON {table} "
        f"USING (user_id = current_setting('app.user_id', true)::uuid) "
        f"WITH CHECK (user_id = current_setting('app.user_id', true)::uuid);"
    )


def upgrade() -> None:
    # ── agents ──────────────────────────────────────────────────────
    op.create_table(
        "agents",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="dormant"),
        sa.Column("wechat_uin", sa.Text(), nullable=True),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status_changed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_agents_status", "agents", ["status"])
    _enable_rls("agents")

    # ── wechat_credentials ───────────────────────────────────────────
    op.create_table(
        "wechat_credentials",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("bot_token_encrypted", sa.LargeBinary(), nullable=True),
        sa.Column("base_url", sa.Text(), nullable=False, server_default="https://ilinkai.weixin.qq.com"),
        sa.Column("cursor", sa.Text(), nullable=True, server_default=""),
        sa.Column("context_token", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="inactive"),
        sa.Column("last_polled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "idx_wechat_credentials_active",
        "wechat_credentials",
        ["status"],
        postgresql_where=sa.text("status = 'active'"),
    )
    _enable_rls("wechat_credentials")

    # ── wechat_bindings ──────────────────────────────────────────────
    op.create_table(
        "wechat_bindings",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("wechat_uin", sa.Text(), nullable=False),
        sa.Column("bound_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("unbound_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_qrcode_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("user_id"),
        sa.UniqueConstraint("wechat_uin"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_wechat_bindings_wechat_uin", "wechat_bindings", ["wechat_uin"])
    _enable_rls("wechat_bindings")

    # ── agent_messages ───────────────────────────────────────────────
    op.create_table(
        "agent_messages",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("direction", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("message_type", sa.Text(), nullable=False, server_default="text"),
        sa.Column("status", sa.Text(), nullable=False, server_default="received"),
        sa.Column("wechat_msg_id", sa.Text(), nullable=True),
        sa.Column("context_token", sa.Text(), nullable=True),
        sa.Column("client_id", sa.Uuid(), nullable=True),
        sa.Column("segments_total", sa.Integer(), nullable=True),
        sa.Column("segment_index", sa.Integer(), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_agent_messages_user_time", "agent_messages", ["user_id", sa.text("created_at DESC")])
    op.create_index(
        "idx_agent_messages_pending",
        "agent_messages",
        ["user_id", "status"],
        postgresql_where=sa.text("status = 'pending'"),
    )
    _enable_rls("agent_messages")

    # ── agent_preferences ────────────────────────────────────────────
    op.create_table(
        "agent_preferences",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False, server_default="我的求职助手"),
        sa.Column("quiet_hours_start", sa.Time(), nullable=True),
        sa.Column("quiet_hours_end", sa.Time(), nullable=True),
        sa.Column("notification_mode", sa.Text(), nullable=False, server_default="realtime"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    _enable_rls("agent_preferences")

    # ── agent_status_history ─────────────────────────────────────────
    op.create_table(
        "agent_status_history",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("old_status", sa.Text(), nullable=False),
        sa.Column("new_status", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_agent_status_history_user", "agent_status_history", ["user_id", sa.text("changed_at DESC")])
    _enable_rls("agent_status_history")


def downgrade() -> None:
    op.drop_table("agent_status_history")
    op.drop_table("agent_preferences")
    op.drop_table("agent_messages")
    op.drop_table("wechat_bindings")
    op.drop_table("wechat_credentials")
    op.drop_table("agents")
