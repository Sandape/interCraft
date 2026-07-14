"""REQ-060 durable WeChat Agent control plane.

Revision ID: 0056_060_wechat_agent_prod
Revises: 0055_059_ai_resume
Create Date: 2026-07-13

Foundational WeChat/Agent persistence layer. Linear successor to REQ-059's
``0055_059_ai_resume``. Tables, columns, defaults, foreign keys, RLS, and
SECURITY DEFINER contracts match the canonical frozen design verbatim; the
replacement ``uq_agent_tasks_resume_from`` unique index and the safe
``get_agent_task_recovery_candidates`` ACL intent are deliberately folded into
revision ``0057_060_agent_recovery_queue`` so the predecessor/downgrade of 0056
removes the queue/function/trigger/index contract together.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

revision: str = "0056_060_wechat_agent_prod"
down_revision: str | None = "0055_059_ai_resume"
branch_labels: str | list[str] | None = None
depends_on: str | list[str] | None = None


TENANT_TABLES: tuple[str, ...] = (
    "agent_tasks",
    "agent_task_events",
    "agent_tool_executions",
    "agent_confirmations",
    "agent_command_outbox",
)


def _enable_tenant_rls(table: str) -> None:
    """ENABLE + FORCE row-level security with the canonical app.user_id policy."""
    op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY;')
    op.execute(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY;')
    op.execute(
        f'CREATE POLICY "{table}_tenant_isolation" ON "{table}" '
        "USING (user_id = NULLIF(current_setting('app.user_id', true), '')::uuid) "
        "WITH CHECK (user_id = NULLIF(current_setting('app.user_id', true), '')::uuid);"
    )


def _add_parent_unique(table: str) -> None:
    """Stable UNIQUE(id, user_id) so composite child FKs can reference the parent."""
    op.create_unique_constraint(f"uq_{table}_id_user", table, ["id", "user_id"])


def _add_composite_fk(
    table: str,
    constraint_name: str,
    parent_table: str,
    local_cols: tuple[str, str],
    remote_cols: tuple[str, str],
    ondelete: str,
) -> None:
    """Composite (parent_id, user_id) -> parent(id, user_id) FK."""
    op.create_foreign_key(
        constraint_name,
        table,
        parent_table,
        list(local_cols),
        list(remote_cols),
        ondelete=ondelete,
    )


def upgrade() -> None:
    # ── consumer leases + registrations ─────────────────────────────────
    op.create_table(
        "wechat_consumer_leases",
        sa.Column("consumer_key", sa.Text(), primary_key=True),
        sa.Column("owner_id", PG_UUID(as_uuid=True), nullable=True),
        sa.Column(
            "fencing_token",
            sa.BigInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("acquired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "metadata_json",
            JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.CheckConstraint("fencing_token >= 0", name="ck_wechat_consumer_lease_fence"),
    )

    op.create_table(
        "wechat_consumer_registrations",
        sa.Column(
            "user_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "credential_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("wechat_credentials.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("cursor", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column(
            "active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    # Migration 0038 leaves wechat_credentials without FORCE RLS, so a single
    # one-time ownership-aware backfill is safe inside this migration's
    # privileged session.
    op.execute(
        """
        INSERT INTO wechat_consumer_registrations (
            user_id, credential_id, cursor, active
        )
        SELECT user_id, id, COALESCE(cursor, ''), true
        FROM wechat_credentials
        WHERE status = 'active' AND bot_token_encrypted IS NOT NULL
        ON CONFLICT (user_id) DO UPDATE
        SET credential_id = EXCLUDED.credential_id,
            cursor = EXCLUDED.cursor,
            active = true,
            updated_at = now()
        """
    )

    # ── poll batches + inbox ────────────────────────────────────────────
    op.create_table(
        "wechat_poll_batches",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "consumer_key",
            sa.Text(),
            sa.ForeignKey("wechat_consumer_leases.consumer_key", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "credential_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("wechat_credentials.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("cursor_before_hash", sa.Text(), nullable=True),
        sa.Column("cursor_after_hash", sa.Text(), nullable=True),
        sa.Column(
            "fencing_token",
            sa.BigInteger(),
            nullable=False,
        ),
        sa.Column("item_count", sa.Integer(), nullable=False),
        sa.Column(
            "persisted_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'received'"),
        ),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("persisted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "item_count >= 0 AND persisted_count >= 0",
            name="ck_wechat_poll_batch_counts",
        ),
        sa.CheckConstraint(
            "persisted_count <= item_count",
            name="ck_wechat_poll_batch_persisted",
        ),
        sa.CheckConstraint(
            "status IN ('received','persisted','quarantined','failed')",
            name="ck_wechat_poll_batch_status",
        ),
    )
    op.create_index(
        "idx_wechat_poll_batches_credential",
        "wechat_poll_batches",
        ["credential_id", "received_at"],
    )

    op.create_table(
        "wechat_inbox",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "batch_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("wechat_poll_batches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("external_message_id", sa.Text(), nullable=True),
        sa.Column("dedupe_key", sa.Text(), nullable=False),
        sa.Column("sender_ref_hash", sa.Text(), nullable=False),
        sa.Column(
            "credential_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("wechat_credentials.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "binding_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("wechat_bindings.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "user_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("binding_epoch", sa.BigInteger(), nullable=True),
        sa.Column("payload_encrypted", sa.LargeBinary(), nullable=True),
        sa.Column("parse_status", sa.Text(), nullable=False),
        sa.Column(
            "processing_status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'received'"),
        ),
        sa.Column("claim_owner", PG_UUID(as_uuid=True), nullable=True),
        sa.Column("claim_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "attempt_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_category", sa.Text(), nullable=True),
        sa.Column("error_detail_redacted", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "parse_status IN ('valid','malformed','unsupported','quarantined')",
            name="ck_wechat_inbox_parse_status",
        ),
        sa.CheckConstraint(
            "processing_status IN "
            "('received','claimed','processing','completed','retry_wait','failed','dead_letter')",
            name="ck_wechat_inbox_processing_status",
        ),
        sa.CheckConstraint("attempt_count >= 0", name="ck_wechat_inbox_attempts"),
    )
    op.create_index("uq_wechat_inbox_dedupe", "wechat_inbox", ["dedupe_key"], unique=True)
    op.create_index(
        "idx_wechat_inbox_claim",
        "wechat_inbox",
        ["processing_status", "next_attempt_at", "created_at"],
    )

    # Stable (id, user_id) uniqueness on every tenant-owned parent that supplies
    # the composite FK target. ``wechat_credentials`` and ``wechat_bindings``
    # already carry a single-column UNIQUE on user_id; (id, user_id) is still
    # satisfied because id is the primary key, but we add the explicit
    # constraint so the composite child FK has a stable, declarative target.
    _add_parent_unique("wechat_credentials")
    _add_parent_unique("wechat_bindings")
    _add_composite_fk(
        "wechat_consumer_registrations",
        "fk_wechat_consumer_registrations_credential_user",
        "wechat_credentials",
        ("credential_id", "user_id"),
        ("id", "user_id"),
        ondelete="CASCADE",
    )
    _add_composite_fk(
        "wechat_inbox",
        "fk_wechat_inbox_credential_user",
        "wechat_credentials",
        ("credential_id", "user_id"),
        ("id", "user_id"),
        ondelete="CASCADE",
    )
    _add_composite_fk(
        "wechat_inbox",
        "fk_wechat_inbox_binding_user",
        "wechat_bindings",
        ("binding_id", "user_id"),
        ("id", "user_id"),
        ondelete="SET NULL (binding_id)",
    )

    # ── agent_tasks + lineage ───────────────────────────────────────────
    op.create_table(
        "agent_tasks",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_message_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("agent_messages.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("thread_id", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'received'"),
        ),
        sa.Column(
            "stage",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'received'"),
        ),
        sa.Column("progress_percent", sa.SmallInteger(), nullable=True),
        sa.Column(
            "summary",
            sa.Text(),
            nullable=False,
            server_default=sa.text("''"),
        ),
        sa.Column(
            "context_json",
            JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("result_json", JSONB(), nullable=True),
        sa.Column("error_category", sa.Text(), nullable=True),
        sa.Column("error_detail_redacted", sa.Text(), nullable=True),
        sa.Column("cancel_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "resume_from_task_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("agent_tasks.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("prompt_version", sa.Text(), nullable=False),
        sa.Column("tool_registry_version", sa.Text(), nullable=False),
        sa.Column(
            "schema_version",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'agent-task.v1'"),
        ),
        sa.Column(
            "binding_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("wechat_bindings.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("binding_epoch", sa.BigInteger(), nullable=False),
        sa.Column("claim_owner", PG_UUID(as_uuid=True), nullable=True),
        sa.Column("claim_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "claim_generation",
            sa.BigInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "version",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
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
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "progress_percent IS NULL OR progress_percent BETWEEN 0 AND 100",
            name="ck_agent_task_progress",
        ),
        sa.CheckConstraint(
            "claim_generation >= 0 AND version >= 1",
            name="ck_agent_task_versions",
        ),
        sa.CheckConstraint(
            "status IN ("
            "'received','understanding','awaiting_input','awaiting_confirmation',"
            "'queued','running','waiting_external','retry_wait','cancel_requested',"
            "'cancelled','succeeded','failed','unknown_result','dead_letter'"
            ")",
            name="ck_agent_task_status",
        ),
    )
    op.create_index(
        "uq_agent_task_source_message",
        "agent_tasks",
        ["source_message_id"],
        unique=True,
        postgresql_where=sa.text("source_message_id IS NOT NULL"),
    )
    op.create_index(
        "idx_agent_tasks_claim",
        "agent_tasks",
        ["status", "claim_until", "created_at"],
    )
    op.create_index(
        "idx_agent_tasks_user_recent",
        "agent_tasks",
        ["user_id", sa.text("created_at DESC")],
    )
    _add_parent_unique("agent_tasks")
    # Composite cross-tenant FKs sit alongside the per-column FKs on
    # source_message_id/resume_from_task_id/binding_id. The single-column FKs
    # carry the per-column ON DELETE action (SET NULL on nullable parent_id,
    # RESTRICT on not-null bindings); the composite FKs use PG16 column-specific
    # ``SET NULL (col)`` so deleting the parent only nulls the FK column,
    # preserving the NOT NULL ``user_id`` tenant key.
    _add_composite_fk(
        "agent_tasks",
        "fk_agent_tasks_source_message_user",
        "agent_messages",
        ("source_message_id", "user_id"),
        ("id", "user_id"),
        ondelete="SET NULL (source_message_id)",
    )
    _add_composite_fk(
        "agent_tasks",
        "fk_agent_tasks_resume_from_user",
        "agent_tasks",
        ("resume_from_task_id", "user_id"),
        ("id", "user_id"),
        ondelete="SET NULL (resume_from_task_id)",
    )
    _add_composite_fk(
        "agent_tasks",
        "fk_agent_tasks_binding_user",
        "wechat_bindings",
        ("binding_id", "user_id"),
        ("id", "user_id"),
        ondelete="NO ACTION",
    )

    op.add_column(
        "wechat_bindings",
        sa.Column(
            "binding_epoch",
            sa.BigInteger(),
            nullable=False,
            server_default=sa.text("1"),
        ),
    )
    op.create_check_constraint("ck_wechat_bindings_epoch", "wechat_bindings", "binding_epoch >= 1")

    # ── agent_messages delivery contract ───────────────────────────────
    for _name, column in (
        (
            "channel",
            sa.Column(
                "channel",
                sa.Text(),
                nullable=False,
                server_default=sa.text("'wechat'"),
            ),
        ),
        ("external_message_id", sa.Column("external_message_id", sa.Text(), nullable=True)),
        ("dedupe_key", sa.Column("dedupe_key", sa.Text(), nullable=True)),
        ("processing_status", sa.Column("processing_status", sa.Text(), nullable=True)),
        (
            "task_id",
            sa.Column(
                "task_id",
                PG_UUID(as_uuid=True),
                nullable=True,
            ),
        ),
        ("trace_id", sa.Column("trace_id", sa.Text(), nullable=True)),
        ("claim_owner", sa.Column("claim_owner", PG_UUID(as_uuid=True), nullable=True)),
        (
            "claim_until",
            sa.Column("claim_until", sa.DateTime(timezone=True), nullable=True),
        ),
        (
            "attempt_count",
            sa.Column(
                "attempt_count",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("0"),
            ),
        ),
        (
            "next_attempt_at",
            sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        ),
        ("error_category", sa.Column("error_category", sa.Text(), nullable=True)),
        (
            "error_detail_redacted",
            sa.Column("error_detail_redacted", sa.Text(), nullable=True),
        ),
        (
            "fencing_token",
            sa.Column("fencing_token", sa.BigInteger(), nullable=True),
        ),
        (
            "delivered_at",
            sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        ),
        ("binding_epoch", sa.Column("binding_epoch", sa.BigInteger(), nullable=True)),
        ("delivery_status", sa.Column("delivery_status", sa.Text(), nullable=True)),
    ):
        op.add_column("agent_messages", column)
    op.create_foreign_key(
        "fk_agent_messages_task",
        "agent_messages",
        "agent_tasks",
        ["task_id"],
        ["id"],
        ondelete="SET NULL",
    )
    _add_parent_unique("agent_messages")
    # Composite (task_id, user_id) -> agent_tasks(id, user_id). task_id is
    # nullable, so the FK is matched only when the row has been bound to a task;
    # unbound rows keep SET NULL semantics via the single-column fk above.
    # The composite FK uses ``ON DELETE SET NULL (task_id)`` so deleting the
    # parent task only nulls task_id (the single-column FK also carries
    # SET NULL) and never tries to null user_id, which is NOT NULL.
    _add_composite_fk(
        "agent_messages",
        "fk_agent_messages_task_user",
        "agent_tasks",
        ("task_id", "user_id"),
        ("id", "user_id"),
        ondelete="SET NULL (task_id)",
    )
    op.create_check_constraint(
        "ck_agent_messages_attempt_count",
        "agent_messages",
        "attempt_count >= 0",
    )
    op.create_index(
        "uq_agent_message_inbound_dedupe",
        "agent_messages",
        ["channel", "user_id", "dedupe_key"],
        unique=True,
        postgresql_where=sa.text("direction = 'inbound' AND dedupe_key IS NOT NULL"),
    )
    op.create_index(
        "idx_agent_messages_delivery_claim",
        "agent_messages",
        ["direction", "delivery_status", "claim_until", "created_at"],
    )
    op.create_check_constraint(
        "ck_agent_messages_delivery_status",
        "agent_messages",
        "delivery_status IS NULL OR delivery_status IN "
        "('pending','claimed','retry_wait','sent','unknown_delivery','failed')",
    )
    op.execute(
        """
        UPDATE agent_messages
        SET delivery_status = CASE
            WHEN direction <> 'outbound' THEN NULL
            WHEN status = 'sent' THEN 'sent'
            WHEN status = 'failed' THEN 'failed'
            ELSE 'pending'
        END
        """
    )

    # ── agent_task_events ───────────────────────────────────────────────
    op.create_table(
        "agent_task_events",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "task_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("agent_tasks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("stage", sa.Text(), nullable=False),
        sa.Column("percent", sa.SmallInteger(), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column(
            "delivery_message_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("agent_messages.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint("sequence >= 1", name="ck_agent_task_event_sequence"),
        sa.CheckConstraint(
            "percent IS NULL OR percent BETWEEN 0 AND 100",
            name="ck_agent_task_event_percent",
        ),
    )
    op.create_index(
        "uq_agent_task_event_sequence",
        "agent_task_events",
        ["task_id", "sequence"],
        unique=True,
    )
    _add_composite_fk(
        "agent_task_events",
        "fk_agent_task_events_task_user",
        "agent_tasks",
        ("task_id", "user_id"),
        ("id", "user_id"),
        ondelete="CASCADE",
    )
    _add_composite_fk(
        "agent_task_events",
        "fk_agent_task_events_delivery_message_user",
        "agent_messages",
        ("delivery_message_id", "user_id"),
        ("id", "user_id"),
        ondelete="SET NULL (delivery_message_id)",
    )

    # ── agent_tool_executions ───────────────────────────────────────────
    op.create_table(
        "agent_tool_executions",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "task_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("agent_tasks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tool_call_id", sa.Text(), nullable=False),
        sa.Column("tool_name", sa.Text(), nullable=False),
        sa.Column("tool_version", sa.Text(), nullable=False),
        sa.Column("args_hash", sa.Text(), nullable=False),
        sa.Column(
            "args_json",
            JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("side_effect", sa.Text(), nullable=False),
        sa.Column("atomicity", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'proposed'"),
        ),
        sa.Column(
            "attempt_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("claim_owner", PG_UUID(as_uuid=True), nullable=True),
        sa.Column("claim_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "claim_generation",
            sa.BigInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "binding_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("wechat_bindings.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("binding_epoch", sa.BigInteger(), nullable=False),
        sa.Column("provider_operation_id", sa.Text(), nullable=True),
        sa.Column("result_json", JSONB(), nullable=True),
        sa.Column("resource_type", sa.Text(), nullable=True),
        sa.Column("resource_id", PG_UUID(as_uuid=True), nullable=True),
        sa.Column("error_category", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("committed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "attempt_count >= 0 AND claim_generation >= 0",
            name="ck_agent_tool_execution_attempts",
        ),
        sa.CheckConstraint(
            "side_effect IN ('none','read','write','external')",
            name="ck_agent_tool_execution_side_effect",
        ),
        sa.CheckConstraint(
            "atomicity IN "
            "('local_transaction','command_outbox','provider_idempotent','reconcile_required')",
            name="ck_agent_tool_execution_atomicity",
        ),
        sa.CheckConstraint(
            "status IN ("
            "'proposed','awaiting_confirmation','claimed','running','succeeded',"
            "'retry_wait','failed','cancelled','unknown_result','dead_letter'"
            ")",
            name="ck_agent_tool_execution_status",
        ),
    )
    op.create_index(
        "uq_agent_tool_execution_idempotency",
        "agent_tool_executions",
        ["user_id", "idempotency_key"],
        unique=True,
    )
    op.create_index(
        "uq_agent_tool_execution_call",
        "agent_tool_executions",
        ["task_id", "tool_call_id"],
        unique=True,
    )
    _add_parent_unique("agent_tool_executions")
    _add_composite_fk(
        "agent_tool_executions",
        "fk_agent_tool_executions_task_user",
        "agent_tasks",
        ("task_id", "user_id"),
        ("id", "user_id"),
        ondelete="CASCADE",
    )
    _add_composite_fk(
        "agent_tool_executions",
        "fk_agent_tool_executions_binding_user",
        "wechat_bindings",
        ("binding_id", "user_id"),
        ("id", "user_id"),
        ondelete="NO ACTION",
    )

    # ── agent_confirmations ─────────────────────────────────────────────
    op.create_table(
        "agent_confirmations",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "task_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("agent_tasks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tool_execution_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("agent_tool_executions.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("args_hash", sa.Text(), nullable=False),
        sa.Column("token_hash", sa.LargeBinary(), nullable=False),
        sa.Column("token_hint", sa.Text(), nullable=False),
        sa.Column(
            "binding_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("wechat_bindings.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("binding_epoch", sa.BigInteger(), nullable=False),
        sa.Column("decision", sa.Text(), nullable=True),
        sa.Column("edited_args_json", JSONB(), nullable=True),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "source_message_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("agent_messages.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "version",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.CheckConstraint(
            "length(token_hint) = 12",
            name="ck_agent_confirmation_token_hint",
        ),
        sa.CheckConstraint("version >= 1", name="ck_agent_confirmation_version"),
        sa.CheckConstraint(
            "decision IS NULL OR decision IN ('approve','edit','reject','cancel')",
            name="ck_agent_confirmation_decision",
        ),
        sa.CheckConstraint(
            "status IN ('pending','consumed','rejected','cancelled','expired','superseded')",
            name="ck_agent_confirmation_status",
        ),
    )
    op.create_index(
        "idx_agent_confirmations_pending",
        "agent_confirmations",
        ["user_id", "status", "expires_at"],
    )
    op.create_index(
        "uq_agent_confirmation_token",
        "agent_confirmations",
        ["user_id", "token_hash"],
        unique=True,
    )
    _add_composite_fk(
        "agent_confirmations",
        "fk_agent_confirmations_task_user",
        "agent_tasks",
        ("task_id", "user_id"),
        ("id", "user_id"),
        ondelete="CASCADE",
    )
    _add_composite_fk(
        "agent_confirmations",
        "fk_agent_confirmations_tool_user",
        "agent_tool_executions",
        ("tool_execution_id", "user_id"),
        ("id", "user_id"),
        ondelete="CASCADE",
    )
    _add_composite_fk(
        "agent_confirmations",
        "fk_agent_confirmations_binding_user",
        "wechat_bindings",
        ("binding_id", "user_id"),
        ("id", "user_id"),
        ondelete="NO ACTION",
    )
    _add_composite_fk(
        "agent_confirmations",
        "fk_agent_confirmations_source_message_user",
        "agent_messages",
        ("source_message_id", "user_id"),
        ("id", "user_id"),
        ondelete="SET NULL (source_message_id)",
    )

    # ── agent_command_outbox + dispatch queue ───────────────────────────
    op.create_table(
        "agent_command_outbox",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("command_type", sa.Text(), nullable=False),
        sa.Column("aggregate_id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("payload_json", JSONB(), nullable=False),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column(
            "attempt_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("claim_owner", PG_UUID(as_uuid=True), nullable=True),
        sa.Column("claim_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_category", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("attempt_count >= 0", name="ck_agent_command_outbox_attempts"),
        sa.CheckConstraint(
            "status IN ('pending','claimed','retry_wait','dispatched','failed','dead_letter')",
            name="ck_agent_command_outbox_status",
        ),
    )
    op.create_index(
        "uq_agent_command_outbox_idempotency",
        "agent_command_outbox",
        ["user_id", "idempotency_key"],
        unique=True,
    )
    op.create_index(
        "idx_agent_command_outbox_claim",
        "agent_command_outbox",
        ["status", "next_attempt_at", "claim_until", "created_at"],
    )
    _add_parent_unique("agent_command_outbox")
    op.create_table(
        "agent_command_dispatch_queue",
        sa.Column(
            "outbox_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("agent_command_outbox.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "user_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "available_at",
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
    )
    op.create_index(
        "idx_agent_command_dispatch_available",
        "agent_command_dispatch_queue",
        ["available_at", "created_at"],
    )
    _add_composite_fk(
        "agent_command_dispatch_queue",
        "fk_agent_command_dispatch_queue_outbox_user",
        "agent_command_outbox",
        ("outbox_id", "user_id"),
        ("id", "user_id"),
        ondelete="CASCADE",
    )

    for table in TENANT_TABLES:
        _enable_tenant_rls(table)

    # wechat_credentials must remain accessible to the privileged
    # SECURITY DEFINER discovery helpers; secrets are Fernet-encrypted at rest.
    op.execute("ALTER TABLE wechat_credentials FORCE ROW LEVEL SECURITY")
    op.execute("DROP FUNCTION IF EXISTS get_active_credentials()")
    op.execute("DROP FUNCTION IF EXISTS get_outbound_drain_candidates(int)")


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS get_outbound_drain_candidates(int)")
    op.execute(
        """
        CREATE OR REPLACE FUNCTION get_outbound_drain_candidates(max_age_hours int)
        RETURNS TABLE (
            id uuid, user_id uuid, direction text, status text, content text,
            client_id uuid, context_token text, wechat_msg_id text,
            created_at timestamptz
        )
        LANGUAGE sql STABLE SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $$
            SELECT am.id, am.user_id, am.direction, am.status, am.content,
                   am.client_id, am.context_token, am.wechat_msg_id, am.created_at
            FROM public.agent_messages AS am
            WHERE am.direction = 'outbound' AND am.status = 'pending'
              AND am.created_at > NOW() - (max_age_hours || ' hours')::interval
            ORDER BY am.created_at ASC
        $$
        """
    )
    op.execute("GRANT SELECT ON TABLE public.agent_messages TO postgres")
    op.execute("ALTER FUNCTION public.get_outbound_drain_candidates(integer) OWNER TO postgres")
    op.execute("REVOKE ALL ON FUNCTION public.get_outbound_drain_candidates(integer) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION public.get_outbound_drain_candidates(integer) TO appuser")
    op.execute("ALTER TABLE wechat_credentials NO FORCE ROW LEVEL SECURITY")
    op.execute("DROP FUNCTION IF EXISTS public.get_active_credentials()")
    op.execute(
        """
        CREATE OR REPLACE FUNCTION get_active_credentials()
        RETURNS TABLE (user_id uuid, cursor text)
        LANGUAGE sql STABLE SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $$
            SELECT wc.user_id, wc.cursor
            FROM public.wechat_credentials AS wc
            WHERE wc.status = 'active'
              AND wc.bot_token_encrypted IS NOT NULL
        $$
        """
    )
    op.execute("GRANT SELECT ON TABLE public.wechat_credentials TO postgres")
    op.execute("ALTER FUNCTION public.get_active_credentials() OWNER TO postgres")
    op.execute("REVOKE ALL ON FUNCTION public.get_active_credentials() FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION public.get_active_credentials() TO appuser")

    for table in reversed(TENANT_TABLES):
        op.execute(
            f"""DO $$ BEGIN
                IF to_regclass('public.{table}') IS NOT NULL THEN
                    EXECUTE 'DROP POLICY IF EXISTS {table}_tenant_isolation ON {table}';
                    EXECUTE 'ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY';
                END IF;
            END $$"""
        )

    op.drop_table("agent_command_dispatch_queue")
    op.drop_table("agent_command_outbox")
    op.drop_table("agent_confirmations")
    op.drop_table("agent_tool_executions")
    op.drop_table("agent_task_events")

    # Drop composite cross-tenant FKs on agent_tasks before touching any
    # parent-table unique constraint they reference.
    # - fk_agent_tasks_source_message_user references agent_messages(id, user_id)
    #   backed by uq_agent_messages_id_user.
    # - fk_agent_tasks_resume_from_user references agent_tasks(id, user_id)
    #   backed by uq_agent_tasks_id_user (dropped implicitly with the table).
    # - fk_agent_tasks_binding_user references wechat_bindings(id, user_id)
    #   backed by uq_wechat_bindings_id_user.
    op.drop_constraint("fk_agent_tasks_binding_user", "agent_tasks", type_="foreignkey")
    op.drop_constraint("fk_agent_tasks_resume_from_user", "agent_tasks", type_="foreignkey")
    op.drop_constraint("fk_agent_tasks_source_message_user", "agent_tasks", type_="foreignkey")

    op.drop_index("idx_agent_messages_delivery_claim", table_name="agent_messages")
    op.execute(
        "ALTER TABLE agent_messages DROP CONSTRAINT IF EXISTS ck_agent_messages_delivery_status"
    )
    op.drop_index("uq_agent_message_inbound_dedupe", table_name="agent_messages")
    op.drop_constraint(
        "ck_agent_messages_attempt_count",
        "agent_messages",
        type_="check",
    )
    op.drop_constraint("fk_agent_messages_task", "agent_messages", type_="foreignkey")
    op.drop_constraint("fk_agent_messages_task_user", "agent_messages", type_="foreignkey")
    op.drop_constraint("uq_agent_messages_id_user", "agent_messages", type_="unique")
    for column in (
        "delivery_status",
        "binding_epoch",
        "delivered_at",
        "fencing_token",
        "error_detail_redacted",
        "error_category",
        "next_attempt_at",
        "attempt_count",
        "claim_until",
        "claim_owner",
        "trace_id",
        "task_id",
        "processing_status",
        "dedupe_key",
        "external_message_id",
        "channel",
    ):
        op.drop_column("agent_messages", column)

    op.drop_constraint("ck_wechat_bindings_epoch", "wechat_bindings", type_="check")
    op.drop_column("wechat_bindings", "binding_epoch")
    op.drop_table("agent_tasks")
    op.drop_table("wechat_inbox")
    op.drop_table("wechat_poll_batches")
    op.drop_table("wechat_consumer_registrations")
    op.drop_table("wechat_consumer_leases")
    op.drop_constraint("uq_wechat_credentials_id_user", "wechat_credentials", type_="unique")
    op.drop_constraint("uq_wechat_bindings_id_user", "wechat_bindings", type_="unique")
