"""Phase 4 — interview_reports / ai_messages tables + langgraph schema.

Revision ID: 0004_phase4_agent
Revises: 0003_phase3_lock_audit
Create Date: 2026-06-13

Creates: langgraph schema, interview_reports, ai_messages.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004_phase4_agent"
down_revision = "0003_phase3_lock_audit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. LangGraph checkpointer schema (langgraph-checkpoint-postgres manages tables)
    op.execute("CREATE SCHEMA IF NOT EXISTS langgraph")

    # 2. interview_reports
    op.create_table(
        "interview_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("interview_sessions.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("overall_score", sa.Numeric(4, 2), nullable=False),
        sa.Column("per_question_score", postgresql.JSONB(), nullable=False),
        sa.Column("dimension_scores", postgresql.JSONB(), nullable=False),
        sa.Column("strengths", postgresql.JSONB(), nullable=False),
        sa.Column("improvements", postgresql.JSONB(), nullable=False),
        sa.Column("summary_md", sa.Text(), nullable=False),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "overall_score >= 0 AND overall_score <= 10",
            name="interview_reports_score_chk",
        ),
    )
    op.create_index(
        "idx_report_session",
        "interview_reports",
        ["session_id"],
    )
    op.create_index(
        "idx_report_overall_score",
        "interview_reports",
        ["overall_score"],
        postgresql_using="btree",
    )

    # 3. ai_messages (append-only audit log for LLM calls)
    op.create_table(
        "ai_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("thread_id", sa.Text(), nullable=False),
        sa.Column("checkpoint_ns", sa.Text(), nullable=False, server_default=""),
        sa.Column("checkpoint_id", sa.Text(), nullable=True),
        sa.Column("node_name", sa.Text(), nullable=False),
        sa.Column(
            "role",
            sa.Text(),
            nullable=False,
        ),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False),
        sa.Column("completion_tokens", sa.Integer(), nullable=False),
        sa.Column("cache_hit", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint("prompt_tokens >= 0", name="ai_messages_prompt_tokens_chk"),
        sa.CheckConstraint("completion_tokens >= 0", name="ai_messages_completion_tokens_chk"),
        sa.CheckConstraint("duration_ms >= 0", name="ai_messages_duration_ms_chk"),
        sa.CheckConstraint(
            "role IN ('system','user','assistant','tool')",
            name="ai_messages_role_chk",
        ),
    )
    op.create_index(
        "idx_ai_msg_user_thread",
        "ai_messages",
        ["user_id", "thread_id", sa.text("occurred_at")],
    )
    op.create_index(
        "idx_ai_msg_checkpoint",
        "ai_messages",
        ["checkpoint_id"],
    )
    op.create_index(
        "idx_ai_msg_occurred",
        "ai_messages",
        [sa.text("occurred_at")],
    )

    # Enable RLS on ai_messages (user-scoped)
    op.execute("ALTER TABLE ai_messages ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY ai_messages_user_policy ON ai_messages
        FOR ALL
        USING (user_id = current_setting('app.user_id', true)::uuid)
        WITH CHECK (user_id = current_setting('app.user_id', true)::uuid)
        """
    )

    # 4. Update status constraint to include Phase 4 values
    op.execute("ALTER TABLE interview_sessions DROP CONSTRAINT IF EXISTS interview_sessions_status_chk")
    op.execute(
        "ALTER TABLE interview_sessions ADD CONSTRAINT interview_sessions_status_chk "
        "CHECK (status IN ('pending','in_progress','completed','aborted','expired'))"
    )

    # 5. interview_sessions.checkpoint_ns already exists (Phase 2), skip ALTER


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS ai_messages_user_policy ON ai_messages")
    op.execute("ALTER TABLE ai_messages DISABLE ROW LEVEL SECURITY")
    op.drop_index("idx_ai_msg_occurred", table_name="ai_messages")
    op.drop_index("idx_ai_msg_checkpoint", table_name="ai_messages")
    op.drop_index("idx_ai_msg_user_thread", table_name="ai_messages")
    op.drop_table("ai_messages")
    op.drop_index("idx_report_overall_score", table_name="interview_reports")
    op.drop_index("idx_report_session", table_name="interview_reports")
    op.drop_table("interview_reports")
    op.execute("DROP SCHEMA IF EXISTS langgraph CASCADE")
