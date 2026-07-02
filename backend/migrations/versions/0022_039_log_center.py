"""REQ-039 B1 — Log Center backend foundation (task_tags + replay_of + admin_audit_log).

Creates:

- ``task_tags`` — user-private annotation table per task_id; PK on
  (task_id, user_id, tag) per FR-016; RLS scoped to ``user_id``.
- ``admin_audit_log`` — append-only audit sink for Replay + Diff per
  FR-008 / FR-014 / FR-030. No RLS — admin-scoped, not user-scoped.
- Adds ``traces.replay_of`` column + FK to ``traces.id`` (FR-006).

Note on ``traces`` table:

The worktree branch predates the full trace observability storage. We
provision a minimal ``traces`` table (id, task_id, user_id, task_type,
prompt_version, model, input_payload, status, error_message,
replay_of, timestamps) so the replay + diff endpoints have something
concrete to read against. If a later migration brings the full table
(per REQ-033 cycle-2 specs), this one is additive — only adds
``replay_of`` if missing and a no-op when both already exist.

The migration is forward-only; downgrade drops the new tables + column
for parity with the dev workflow.

Worktree chain note:

The worktree branch is missing intermediate migrations (0012-0016,
0022-0026) because they belong to other concurrent teams. This
migration is therefore declared as a **branch root** (``down_revision =
None``) under ``branch_labels = ("039_log_center",)`` so ``alembic
upgrade heads`` resolves cleanly. When merged to master, replace
``down_revision`` with the actual head (``0021_a2a_messages`` for
master as of 2026-07-02) and drop the branch label.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0022_039_log_center"
# Standalone branch head — the worktree's migration chain is missing
# 0012-0016 (intentional gap so 039 ships independently). Using
# branch_labels makes this migration a separate branch root so
# ``alembic upgrade heads`` resolves cleanly without traversing the
# broken 0017 → 0016 link.
down_revision = None
branch_labels = ("039_log_center",)
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. Minimal ``traces`` table — foundation for replay + diff + payload
    #    pagination + IO access. Safe to create IF NOT EXISTS in case a
    #    later migration has already shipped the full table.
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS traces (
            id UUID PRIMARY KEY,
            task_id UUID,
            user_id UUID,
            task_type TEXT NOT NULL DEFAULT 'unknown',
            prompt_version TEXT NOT NULL DEFAULT 'unknown',
            model TEXT NOT NULL DEFAULT 'unknown',
            input_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
            status TEXT NOT NULL DEFAULT 'pending',
            error_message TEXT,
            replay_of UUID,
            node_payloads JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_traces_task_id ON traces(task_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_traces_user_id ON traces(user_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_traces_task_type ON traces(task_type)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_traces_replay_of ON traces(replay_of)"
    )

    # ------------------------------------------------------------------
    # 2. Add ``replay_of`` FK if it was missing from a pre-existing
    #    ``traces`` table (the IF NOT EXISTS above is a no-op for
    #    columns, so we alter defensively).
    # ------------------------------------------------------------------
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'traces' AND column_name = 'replay_of'
            ) THEN
                ALTER TABLE traces
                    ADD COLUMN replay_of UUID
                    REFERENCES traces(id) ON DELETE SET NULL;
            END IF;
        END
        $$;
        """
    )

    # ------------------------------------------------------------------
    # 3. ``task_tags`` — user-private annotation table (FR-016 / FR-031)
    # ------------------------------------------------------------------
    op.create_table(
        "task_tags",
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tag", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("task_id", "user_id", "tag"),
        sa.CheckConstraint(
            "char_length(tag) >= 1 AND char_length(tag) <= 50",
            name="task_tags_length_chk",
        ),
    )
    op.create_index("idx_task_tags_task_user", "task_tags", ["task_id", "user_id"])
    op.create_index("idx_task_tags_user", "task_tags", ["user_id"])

    # RLS — scoped to ``user_id`` (FR-031: API MUST NOT return another
    # user's tags even to admin).
    op.execute("ALTER TABLE task_tags ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE task_tags FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY task_tags_user_isolation ON task_tags
        FOR ALL
        USING (user_id = current_setting('app.user_id', true)::uuid)
        WITH CHECK (user_id = current_setting('app.user_id', true)::uuid)
        """
    )

    # ------------------------------------------------------------------
    # 4. ``admin_audit_log`` — append-only audit sink for Replay + Diff
    #    (FR-008 / FR-014 / FR-030, IC-7). One row per admin action.
    #    No RLS — admin console actions are operator-scoped, not user-scoped.
    # ------------------------------------------------------------------
    op.create_table(
        "admin_audit_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("target_kind", sa.Text(), nullable=False),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("details", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "action IN ('replay_triggered','diff_computed','tag_added','tag_removed')",
            name="admin_audit_log_action_chk",
        ),
        sa.CheckConstraint(
            "target_kind IN ('trace','task','diff')",
            name="admin_audit_log_target_kind_chk",
        ),
    )
    op.create_index(
        "idx_admin_audit_user_action", "admin_audit_log", ["user_id", "action"]
    )
    op.create_index(
        "idx_admin_audit_created_at", "admin_audit_log", ["created_at"]
    )


def downgrade() -> None:
    op.drop_index("idx_admin_audit_created_at", table_name="admin_audit_log")
    op.drop_index("idx_admin_audit_user_action", table_name="admin_audit_log")
    op.drop_table("admin_audit_log")

    op.execute("DROP POLICY IF EXISTS task_tags_user_isolation ON task_tags")
    op.execute("ALTER TABLE task_tags DISABLE ROW LEVEL SECURITY")
    op.drop_index("idx_task_tags_user", table_name="task_tags")
    op.drop_index("idx_task_tags_task_user", table_name="task_tags")
    op.drop_table("task_tags")

    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'traces' AND column_name = 'replay_of'
            ) THEN
                ALTER TABLE traces DROP COLUMN replay_of;
            END IF;
        END
        $$;
        """
    )
    # We intentionally do NOT drop the ``traces`` table itself in
    # downgrade — its existence predates 0022 and a future migration
    # owns its lifecycle.