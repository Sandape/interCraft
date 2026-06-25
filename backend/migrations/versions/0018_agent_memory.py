"""Create semantic_memories + memory_retrieval_logs tables (REQ-028 US1).

Revision ID: 0018_agent_memory
Revises: 0017_resume_theme
Create Date: 2026-06-24

US1 scope: semantic memory storage + retrieval observability. RLS enabled
per existing module pattern (migrations/versions/0001_initial.py::_enable_rls).
pgvector embedding column is deferred (US2/US3) — US1 uses exact-key match.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID

revision = "0018_agent_memory"
down_revision = "0017_resume_theme"
branch_labels = None
depends_on = None


def _enable_rls(table: str, policy_column: str = "user_id") -> None:
    """Mirror migrations/versions/0001_initial.py::_enable_rls."""
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;")
    op.execute(
        f"CREATE POLICY {table}_user_isolation ON {table} "
        f"USING ({policy_column} = current_setting('app.user_id', true)::uuid) "
        f"WITH CHECK ({policy_column} = current_setting('app.user_id', true)::uuid);"
    )


def upgrade() -> None:
    # ── semantic_memories ──────────────────────────────────────────────────
    op.create_table(
        "semantic_memories",
        sa.Column("id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("fact_key", sa.Text(), nullable=False),
        sa.Column("fact_value", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Numeric(3, 2), nullable=False, server_default="0.5"),
        sa.Column(
            "source",
            sa.Text(),
            nullable=False,
            server_default="'extracted_from_llm_output'",
        ),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.Text(), nullable=False, server_default="'active'"),
        sa.Column("schema_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("meta", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("superseded_by", PG_UUID(as_uuid=True), nullable=True),
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
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["superseded_by"], ["semantic_memories.id"], ondelete="SET NULL"
        ),
        sa.CheckConstraint(
            "status IN ('active', 'superseded')", name="ck_semantic_memories_status"
        ),
        sa.CheckConstraint(
            "source IN ('extracted_from_llm_output', 'user_asserted', 'system_inferred')",
            name="ck_semantic_memories_source",
        ),
        sa.CheckConstraint(
            "confidence >= 0.0 AND confidence <= 1.0",
            name="ck_semantic_memories_confidence",
        ),
        sa.CheckConstraint("version >= 1", name="ck_semantic_memories_version"),
        sa.CheckConstraint(
            "schema_version >= 1", name="ck_semantic_memories_schema_version"
        ),
    )
    op.create_index(
        "idx_semantic_memories_user_id", "semantic_memories", ["user_id"]
    )
    # One active fact per (user_id, fact_key). Partial unique index — superseded
    # rows keep their (user_id, fact_key) and are not constrained.
    op.create_index(
        "uq_semantic_memories_active_user_key",
        "semantic_memories",
        ["user_id", "fact_key"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )
    op.create_index(
        "idx_semantic_memories_user_active",
        "semantic_memories",
        ["user_id", "created_at"],
        postgresql_where=sa.text("status = 'active'"),
    )
    _enable_rls("semantic_memories")

    # ── memory_retrieval_logs ──────────────────────────────────────────────
    op.create_table(
        "memory_retrieval_logs",
        sa.Column("id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("graph", sa.Text(), nullable=False),
        sa.Column("node", sa.Text(), nullable=False),
        sa.Column("query", sa.Text(), nullable=True),
        sa.Column("retrieved_memory_ids", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("token_budget_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("retrieval_latency_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "idx_memory_retrieval_logs_user_id", "memory_retrieval_logs", ["user_id"]
    )
    op.create_index(
        "idx_memory_retrieval_logs_user_created",
        "memory_retrieval_logs",
        ["user_id", "created_at"],
    )
    _enable_rls("memory_retrieval_logs")


def downgrade() -> None:
    op.drop_table("memory_retrieval_logs")
    op.drop_table("semantic_memories")
