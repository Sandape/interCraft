"""Agent module SQLAlchemy models — REQ-052 data-model.md.

Six tables:
  agents                 — 1:1 per user, agent lifecycle state
  wechat_credentials     — iLink bearer token, cursor, context_token
  wechat_bindings        — 1:1 WeChat UIN ↔ InterCraft user mapping
  agent_messages         — inbound/outbound message log
  agent_preferences      — per-user display_name, quiet_hours, notification_mode
  agent_status_history   — append-only audit log of status transitions
"""

from __future__ import annotations

from datetime import datetime, time
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    LargeBinary,
    SmallInteger,
    Text,
    Time,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.ids import new_uuid_v7

# Resume-lineage partial unique index must mirror migration 0057 so the ORM
# stays statically aligned with the live catalog. The predicate is identical
# to the migration's ``postgresql_where`` so autogen-style parity checks hold.
_AGENT_TASKS_RESUME_FROM_PARTIAL_INDEX = Index(
    "uq_agent_tasks_resume_from",
    "resume_from_task_id",
    unique=True,
    postgresql_where=sa.text("resume_from_task_id IS NOT NULL"),
)


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=new_uuid_v7)
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    status: Mapped[str] = mapped_column(
        Text, nullable=False, default="dormant", server_default="dormant"
    )
    wechat_uin: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status_changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class WeChatCredential(Base):
    __tablename__ = "wechat_credentials"
    __table_args__ = (UniqueConstraint("id", "user_id", name="uq_wechat_credentials_id_user"),)

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=new_uuid_v7)
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    bot_token_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    base_url: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="https://ilinkai.weixin.qq.com",
        server_default="https://ilinkai.weixin.qq.com",
    )
    cursor: Mapped[str] = mapped_column(Text, nullable=True, default="", server_default="")
    context_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, default="inactive", server_default="inactive"
    )
    last_polled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class WeChatBinding(Base):
    __tablename__ = "wechat_bindings"
    __table_args__ = (UniqueConstraint("id", "user_id", name="uq_wechat_bindings_id_user"),)

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=new_uuid_v7)
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    wechat_uin: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    bound_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    unbound_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_qrcode_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    binding_epoch: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=1, server_default="1"
    )


class AgentMessage(Base):
    __tablename__ = "agent_messages"
    __table_args__ = (
        UniqueConstraint("id", "user_id", name="uq_agent_messages_id_user"),
        # PG16 column-specific ``ON DELETE SET NULL (task_id)`` so deleting the
        # parent task only nulls ``task_id``; ``user_id`` (NOT NULL) survives.
        ForeignKeyConstraint(
            ["task_id", "user_id"],
            ["agent_tasks.id", "agent_tasks.user_id"],
            name="fk_agent_messages_task_user",
            ondelete="SET NULL (task_id)",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=new_uuid_v7)
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    direction: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    message_type: Mapped[str] = mapped_column(
        Text, nullable=False, default="text", server_default="text"
    )
    status: Mapped[str] = mapped_column(
        Text, nullable=False, default="received", server_default="received"
    )
    wechat_msg_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    context_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    client_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    segments_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    segment_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    channel: Mapped[str] = mapped_column(
        Text, nullable=False, default="wechat", server_default="wechat"
    )
    external_message_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    dedupe_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    processing_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    task_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("agent_tasks.id", ondelete="SET NULL"), nullable=True
    )
    trace_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    claim_owner: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    claim_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempt_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_category: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_detail_redacted: Mapped[str | None] = mapped_column(Text, nullable=True)
    fencing_token: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    binding_epoch: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    delivery_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class AgentPreference(Base):
    __tablename__ = "agent_preferences"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=new_uuid_v7)
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    display_name: Mapped[str] = mapped_column(
        Text, nullable=False, default="我的求职助手", server_default="我的求职助手"
    )
    quiet_hours_start: Mapped[time | None] = mapped_column(Time, nullable=True)
    quiet_hours_end: Mapped[time | None] = mapped_column(Time, nullable=True)
    notification_mode: Mapped[str] = mapped_column(
        Text, nullable=False, default="realtime", server_default="realtime"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class AgentStatusHistory(Base):
    __tablename__ = "agent_status_history"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=new_uuid_v7)
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    old_status: Mapped[str] = mapped_column(Text, nullable=False)
    new_status: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class WeChatConsumerLease(Base):
    __tablename__ = "wechat_consumer_leases"

    consumer_key: Mapped[str] = mapped_column(Text, primary_key=True)
    owner_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    fencing_token: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default="0"
    )
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    acquired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )


class WeChatPollBatch(Base):
    __tablename__ = "wechat_poll_batches"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=new_uuid_v7)
    consumer_key: Mapped[str] = mapped_column(
        Text, ForeignKey("wechat_consumer_leases.consumer_key", ondelete="RESTRICT"), nullable=False
    )
    credential_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("wechat_credentials.id", ondelete="CASCADE"),
        nullable=False,
    )
    cursor_before_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    cursor_after_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    fencing_token: Mapped[int] = mapped_column(BigInteger, nullable=False)
    item_count: Mapped[int] = mapped_column(Integer, nullable=False)
    persisted_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    status: Mapped[str] = mapped_column(
        Text, nullable=False, default="received", server_default="received"
    )
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    persisted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class WeChatInbox(Base):
    __tablename__ = "wechat_inbox"
    __table_args__ = (
        ForeignKeyConstraint(
            ["credential_id", "user_id"],
            ["wechat_credentials.id", "wechat_credentials.user_id"],
            name="fk_wechat_inbox_credential_user",
            ondelete="CASCADE",
        ),
        # Column-specific ``SET NULL (binding_id)`` — deleting the binding only
        # nulls binding_id; user_id (nullable on inbox but preserves the reference)
        # stays intact.
        ForeignKeyConstraint(
            ["binding_id", "user_id"],
            ["wechat_bindings.id", "wechat_bindings.user_id"],
            name="fk_wechat_inbox_binding_user",
            ondelete="SET NULL (binding_id)",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=new_uuid_v7)
    batch_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("wechat_poll_batches.id", ondelete="CASCADE"),
        nullable=False,
    )
    external_message_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    dedupe_key: Mapped[str] = mapped_column(Text, nullable=False)
    sender_ref_hash: Mapped[str] = mapped_column(Text, nullable=False)
    credential_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("wechat_credentials.id", ondelete="CASCADE"),
        nullable=False,
    )
    binding_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("wechat_bindings.id", ondelete="SET NULL"), nullable=True
    )
    user_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    binding_epoch: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    payload_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    parse_status: Mapped[str] = mapped_column(Text, nullable=False)
    processing_status: Mapped[str] = mapped_column(
        Text, nullable=False, default="received", server_default="received"
    )
    claim_owner: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    claim_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempt_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_category: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_detail_redacted: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class WeChatConsumerRegistration(Base):
    __tablename__ = "wechat_consumer_registrations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["credential_id", "user_id"],
            ["wechat_credentials.id", "wechat_credentials.user_id"],
            name="fk_wechat_consumer_registrations_credential_user",
            ondelete="CASCADE",
        ),
    )

    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    credential_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("wechat_credentials.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    cursor: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=sa.true()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class AgentTask(Base):
    __tablename__ = "agent_tasks"
    __table_args__ = (
        UniqueConstraint("id", "user_id", name="uq_agent_tasks_id_user"),
        # Composite cross-tenant FKs sit alongside the single-column FKs on
        # each parent_id column so:
        #   * the single-column FK carries the per-column ON DELETE action
        #     (SET NULL on nullable parents, RESTRICT on not-null bindings);
        #   * the composite FK uses PG16 column-specific ``SET NULL (col)``
        #     so deleting the parent only nulls the FK column, preserving
        #     the NOT NULL ``user_id`` tenant key;
        #   * user_id already cascades with the canonical users FK.
        # Column-specific ``SET NULL (source_message_id)`` so deleting the
        # referencing agent_message only nulls source_message_id; user_id stays.
        ForeignKeyConstraint(
            ["source_message_id", "user_id"],
            ["agent_messages.id", "agent_messages.user_id"],
            name="fk_agent_tasks_source_message_user",
            ondelete="SET NULL (source_message_id)",
        ),
        # Column-specific ``SET NULL (resume_from_task_id)`` — same invariant.
        ForeignKeyConstraint(
            ["resume_from_task_id", "user_id"],
            ["agent_tasks.id", "agent_tasks.user_id"],
            name="fk_agent_tasks_resume_from_user",
            ondelete="SET NULL (resume_from_task_id)",
        ),
        # binding_id is NOT NULL, so NO ACTION is correct here.
        ForeignKeyConstraint(
            ["binding_id", "user_id"],
            ["wechat_bindings.id", "wechat_bindings.user_id"],
            name="fk_agent_tasks_binding_user",
            ondelete="NO ACTION",
        ),
        _AGENT_TASKS_RESUME_FROM_PARTIAL_INDEX,
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=new_uuid_v7)
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    source_message_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("agent_messages.id", ondelete="SET NULL"), nullable=True
    )
    thread_id: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, default="received", server_default="received"
    )
    stage: Mapped[str] = mapped_column(
        Text, nullable=False, default="received", server_default="received"
    )
    progress_percent: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    context_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )
    result_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    error_category: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_detail_redacted: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancel_requested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resume_from_task_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("agent_tasks.id", ondelete="SET NULL"), nullable=True
    )
    prompt_version: Mapped[str] = mapped_column(Text, nullable=False)
    tool_registry_version: Mapped[str] = mapped_column(Text, nullable=False)
    schema_version: Mapped[str] = mapped_column(
        Text, nullable=False, default="agent-task.v1", server_default="agent-task.v1"
    )
    binding_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("wechat_bindings.id", ondelete="RESTRICT"), nullable=False
    )
    binding_epoch: Mapped[int] = mapped_column(BigInteger, nullable=False)
    claim_owner: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    claim_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    claim_generation: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default="0"
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AgentTaskEvent(Base):
    __tablename__ = "agent_task_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["task_id", "user_id"],
            ["agent_tasks.id", "agent_tasks.user_id"],
            name="fk_agent_task_events_task_user",
            ondelete="CASCADE",
        ),
        # Column-specific ``SET NULL (delivery_message_id)`` — deleting the
        # agent_message only nulls delivery_message_id; user_id stays NOT NULL.
        ForeignKeyConstraint(
            ["delivery_message_id", "user_id"],
            ["agent_messages.id", "agent_messages.user_id"],
            name="fk_agent_task_events_delivery_message_user",
            ondelete="SET NULL (delivery_message_id)",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=new_uuid_v7)
    task_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("agent_tasks.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    stage: Mapped[str] = mapped_column(Text, nullable=False)
    percent: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    delivery_message_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("agent_messages.id", ondelete="SET NULL"), nullable=True
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class AgentToolExecution(Base):
    __tablename__ = "agent_tool_executions"
    __table_args__ = (
        UniqueConstraint("id", "user_id", name="uq_agent_tool_executions_id_user"),
        ForeignKeyConstraint(
            ["task_id", "user_id"],
            ["agent_tasks.id", "agent_tasks.user_id"],
            name="fk_agent_tool_executions_task_user",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["binding_id", "user_id"],
            ["wechat_bindings.id", "wechat_bindings.user_id"],
            name="fk_agent_tool_executions_binding_user",
            ondelete="NO ACTION",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=new_uuid_v7)
    task_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("agent_tasks.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    tool_call_id: Mapped[str] = mapped_column(Text, nullable=False)
    tool_name: Mapped[str] = mapped_column(Text, nullable=False)
    tool_version: Mapped[str] = mapped_column(Text, nullable=False)
    args_hash: Mapped[str] = mapped_column(Text, nullable=False)
    args_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)
    side_effect: Mapped[str] = mapped_column(Text, nullable=False)
    atomicity: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, default="proposed", server_default="proposed"
    )
    attempt_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    claim_owner: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    claim_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    claim_generation: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default="0"
    )
    binding_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("wechat_bindings.id", ondelete="RESTRICT"), nullable=False
    )
    binding_epoch: Mapped[int] = mapped_column(BigInteger, nullable=False)
    provider_operation_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    resource_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    resource_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    error_category: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    committed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AgentConfirmation(Base):
    __tablename__ = "agent_confirmations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["task_id", "user_id"],
            ["agent_tasks.id", "agent_tasks.user_id"],
            name="fk_agent_confirmations_task_user",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tool_execution_id", "user_id"],
            ["agent_tool_executions.id", "agent_tool_executions.user_id"],
            name="fk_agent_confirmations_tool_user",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["binding_id", "user_id"],
            ["wechat_bindings.id", "wechat_bindings.user_id"],
            name="fk_agent_confirmations_binding_user",
            ondelete="NO ACTION",
        ),
        # Column-specific ``SET NULL (source_message_id)`` — deleting the
        # agent_message only nulls source_message_id; user_id stays NOT NULL.
        ForeignKeyConstraint(
            ["source_message_id", "user_id"],
            ["agent_messages.id", "agent_messages.user_id"],
            name="fk_agent_confirmations_source_message_user",
            ondelete="SET NULL (source_message_id)",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=new_uuid_v7)
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    task_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("agent_tasks.id", ondelete="CASCADE"), nullable=False
    )
    tool_execution_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("agent_tool_executions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    args_hash: Mapped[str] = mapped_column(Text, nullable=False)
    token_hash: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    token_hint: Mapped[str] = mapped_column(Text, nullable=False)
    binding_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("wechat_bindings.id", ondelete="RESTRICT"), nullable=False
    )
    binding_epoch: Mapped[int] = mapped_column(BigInteger, nullable=False)
    decision: Mapped[str | None] = mapped_column(Text, nullable=True)
    edited_args_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, default="pending", server_default="pending"
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source_message_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("agent_messages.id", ondelete="SET NULL"), nullable=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")


class AgentCommandOutbox(Base):
    __tablename__ = "agent_command_outbox"
    __table_args__ = (UniqueConstraint("id", "user_id", name="uq_agent_command_outbox_id_user"),)

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=new_uuid_v7)
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    command_type: Mapped[str] = mapped_column(Text, nullable=False)
    aggregate_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, default="pending", server_default="pending"
    )
    attempt_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    claim_owner: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    claim_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_category: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AgentCommandDispatchQueue(Base):
    __tablename__ = "agent_command_dispatch_queue"
    __table_args__ = (
        ForeignKeyConstraint(
            ["outbox_id", "user_id"],
            ["agent_command_outbox.id", "agent_command_outbox.user_id"],
            name="fk_agent_command_dispatch_queue_outbox_user",
            ondelete="CASCADE",
        ),
    )

    outbox_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("agent_command_outbox.id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class AgentTaskRecoveryQueue(Base):
    __tablename__ = "agent_task_recovery_queue"
    __table_args__ = (
        ForeignKeyConstraint(
            ["task_id", "user_id"],
            ["agent_tasks.id", "agent_tasks.user_id"],
            name="fk_agent_task_recovery_queue_task_user",
            ondelete="CASCADE",
        ),
    )

    task_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("agent_tasks.id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    next_check_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


__all__ = [
    "Agent",
    "AgentCommandDispatchQueue",
    "AgentCommandOutbox",
    "AgentConfirmation",
    "AgentMessage",
    "AgentPreference",
    "AgentStatusHistory",
    "AgentTask",
    "AgentTaskEvent",
    "AgentTaskRecoveryQueue",
    "AgentToolExecution",
    "WeChatBinding",
    "WeChatConsumerLease",
    "WeChatConsumerRegistration",
    "WeChatCredential",
    "WeChatInbox",
    "WeChatPollBatch",
]
