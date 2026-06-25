"""Create a2a_messages table (REQ-031 US1, T005).

The ``a2a_messages`` table is the standardized inter-agent message
audit log (spec FR-016, FR-017). It is the persistence surface for
:class:`app.agents.a2a.A2AMessage`.

Why no RLS?
    The audit log is scoped by ``trace_id`` + ``thread_id``, not by
    user. Debug queries (FR-018) must span users within one trace to
    reconstruct a multi-agent invocation. This mirrors the 025
    ``interview_sessions.interview_plan`` JSONB precedent (no RLS).
    The application layer is responsible for sanitizing any
    user-derived text before insertion.

Why ``retry_count`` cap at 5?
    US1 ships retry-once + log-on-failure. The CHECK cap at 5 leaves
    headroom for US3 / US4 to grow the retry policy without a schema
    change; the framework's ``DelegationRunner`` enforces 1 in US1.

No new package dependencies. Migration is forward-only; downgrade drops
the table.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID

revision = "0021_a2a_messages"
down_revision = "0020_irt_item_bank"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "a2a_messages",
        sa.Column("id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("trace_id", sa.Text(), nullable=False),
        sa.Column("thread_id", sa.Text(), nullable=False),
        sa.Column("parent_agent", sa.String(length=128), nullable=False),
        sa.Column("child_agent", sa.String(length=128), nullable=False),
        sa.Column("task", sa.String(length=512), nullable=False),
        sa.Column("context_jsonb", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column(
            "expected_output_jsonb",
            JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("result_jsonb", JSONB(), nullable=True),
        sa.Column("error_reason", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
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
        sa.CheckConstraint(
            "status IN ('pending','success','failed','timeout')",
            name="ck_a2a_messages_status",
        ),
        sa.CheckConstraint(
            "retry_count >= 0 AND retry_count <= 5",
            name="ck_a2a_messages_retry_range",
        ),
        sa.CheckConstraint(
            "duration_ms IS NULL OR duration_ms >= 0",
            name="ck_a2a_messages_duration_nonneg",
        ),
    )

    # Indexes for the two dominant query patterns:
    # 1. List messages for a trace (debug cross-user — FR-018).
    # 2. List messages for a thread (debug per-session).
    # 3. List pending messages for supervisor health dashboards.
    op.create_index("idx_a2a_messages_trace_id", "a2a_messages", ["trace_id"])
    op.create_index("idx_a2a_messages_thread_id", "a2a_messages", ["thread_id"])
    op.create_index(
        "idx_a2a_messages_status_created_at",
        "a2a_messages",
        ["status", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("a2a_messages")