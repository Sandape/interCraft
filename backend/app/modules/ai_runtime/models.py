"""REQ-061 AI Runtime ORM entities (T013).

PostgreSQL is authoritative for task lifecycle, fencing, and evidence.
Raw user content is never stored here — only hashes, versions, and summaries.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.ids import new_uuid_v7


class AITask(Base):
    __tablename__ = "ai_tasks"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "capability_code",
            "action_code",
            "idempotency_key",
            name="uq_ai_tasks_scoped_idempotency",
        ),
        Index("idx_ai_tasks_user_accepted", "user_id", "accepted_at"),
        Index("idx_ai_tasks_status", "status"),
        {"extend_existing": True},
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=new_uuid_v7
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    capability_code: Mapped[str] = mapped_column(Text, nullable=False)
    action_code: Mapped[str] = mapped_column(Text, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)
    acceptance_request_hash: Mapped[str] = mapped_column(Text, nullable=False)
    service_tier: Mapped[str] = mapped_column(Text, nullable=False, default="standard")
    status: Mapped[str] = mapped_column(Text, nullable=False, default="accepted")
    stage_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    stage_label: Mapped[str | None] = mapped_column(Text, nullable=True)
    progress_percent: Mapped[int | None] = mapped_column(Integer, nullable=True)
    input_snapshot_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("ai_input_snapshots.id"), nullable=True
    )
    quote_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    reservation_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    current_execution_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    task_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    accepted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    terminal_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    user_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    failure_category: Mapped[str | None] = mapped_column(Text, nullable=True)
    support_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    available_actions: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
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


class AIInputSnapshot(Base):
    __tablename__ = "ai_input_snapshots"
    __table_args__ = {"extend_existing": True}

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=new_uuid_v7
    )
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    capability_code: Mapped[str] = mapped_column(Text, nullable=False)
    canonical_hash: Mapped[str] = mapped_column(Text, nullable=False)
    schema_version: Mapped[str] = mapped_column(Text, nullable=False)
    business_object_refs: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    safe_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class AIPolicySnapshot(Base):
    __tablename__ = "ai_policy_snapshots"
    __table_args__ = {"extend_existing": True}

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=new_uuid_v7
    )
    model_policy_version_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    prompt_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_schema_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    rubric_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    tool_catalog_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    capability_adapter_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    point_table_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    cost_rate_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    release_batch_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    locked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )


class AIExecution(Base):
    __tablename__ = "ai_executions"
    __table_args__ = (
        UniqueConstraint("task_id", "execution_no", name="uq_ai_executions_task_no"),
        Index("idx_ai_executions_claim", "claim_owner", "claim_expires_at"),
        {"extend_existing": True},
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=new_uuid_v7
    )
    task_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("ai_tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    root_task_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    execution_no: Mapped[int] = mapped_column(Integer, nullable=False)
    trigger_kind: Mapped[str] = mapped_column(Text, nullable=False, default="initial")
    source_execution_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("ai_executions.id"), nullable=True
    )
    input_mode: Mapped[str] = mapped_column(Text, nullable=False, default="original_snapshot")
    behavior_mode: Mapped[str] = mapped_column(Text, nullable=False, default="current_stable")
    status: Mapped[str] = mapped_column(Text, nullable=False, default="accepted")
    stage_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    checkpoint_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    policy_snapshot_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("ai_policy_snapshots.id"), nullable=True
    )
    claim_owner: Mapped[str | None] = mapped_column(Text, nullable=True)
    claim_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    claim_generation: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    retry_attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    external_retry_cost_estimate: Mapped[Decimal | None] = mapped_column(
        Numeric(20, 8), nullable=True
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class AIDispatchIntent(Base):
    __tablename__ = "ai_dispatch_intents"
    __table_args__ = (
        UniqueConstraint(
            "execution_id",
            "dispatch_kind",
            "idempotency_key",
            name="uq_ai_dispatch_intents_scope",
        ),
        Index("idx_ai_dispatch_intents_status", "status", "next_attempt_at"),
        {"extend_existing": True},
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=new_uuid_v7
    )
    task_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    execution_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("ai_executions.id", ondelete="CASCADE"),
        nullable=False,
    )
    root_task_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    dispatch_kind: Mapped[str] = mapped_column(Text, nullable=False)
    payload_schema_version: Mapped[str] = mapped_column(Text, nullable=False)
    behavior_version: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)
    claim_owner: Mapped[str | None] = mapped_column(Text, nullable=True)
    claim_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    claim_generation: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error_category: Mapped[str | None] = mapped_column(Text, nullable=True)
    transport_job_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class AIAuthorizationReceipt(Base):
    """Immutable authorization evidence — append-only at the DB layer."""

    __tablename__ = "ai_authorization_receipts"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_ai_authorization_receipts_idem"),
        Index("idx_ai_authorization_receipts_actor", "actor_id", "issued_at"),
        {"extend_existing": True},
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=new_uuid_v7
    )
    root_task_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    task_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    execution_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    user_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True, index=True)
    actor_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    actor_auth_epoch: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk_class: Mapped[str] = mapped_column(Text, nullable=False, default="R0")
    authorization_mode: Mapped[str] = mapped_column(Text, nullable=False, default="direct")
    action: Mapped[str] = mapped_column(Text, nullable=False)
    target_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_id: Mapped[str] = mapped_column(Text, nullable=False)
    target_version: Mapped[int] = mapped_column(Integer, nullable=False)
    canonical_arguments_hash: Mapped[str] = mapped_column(Text, nullable=False)
    tool_schema_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    policy_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    budget_unit: Mapped[str | None] = mapped_column(Text, nullable=True)
    budget_limit: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    approvals: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    standing_scope_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    consumed_effect_intent_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )


class AITaskEvent(Base):
    __tablename__ = "ai_task_events"
    __table_args__ = (
        UniqueConstraint("task_id", "sequence", name="uq_ai_task_events_sequence"),
        UniqueConstraint(
            "task_id", "idempotency_key", name="uq_ai_task_events_scoped_idempotency"
        ),
        Index("idx_ai_task_events_root", "root_task_id", "sequence"),
        {"extend_existing": True},
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=new_uuid_v7
    )
    task_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("ai_tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    root_task_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    execution_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    actor_type: Mapped[str] = mapped_column(Text, nullable=False, default="system")
    actor_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    from_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    to_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason_category: Mapped[str | None] = mapped_column(Text, nullable=True)
    safe_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload_schema_version: Mapped[str] = mapped_column(
        Text, nullable=False, default="1", server_default="1"
    )
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    payload_summary: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    corrects_event_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("ai_task_events.id"), nullable=True
    )


class AIStageAttempt(Base):
    __tablename__ = "ai_stage_attempts"
    __table_args__ = (
        UniqueConstraint(
            "execution_id",
            "stage_code",
            "attempt_no",
            name="uq_ai_stage_attempts_scope",
        ),
        {"extend_existing": True},
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=new_uuid_v7
    )
    task_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    execution_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("ai_executions.id", ondelete="CASCADE"),
        nullable=False,
    )
    root_task_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    stage_code: Mapped[str] = mapped_column(Text, nullable=False)
    attempt_no: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="running")
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    timeout_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_category: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_decision: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    input_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_structure_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    quality_gate_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    milestone_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)


class AIExternalEffectIntent(Base):
    __tablename__ = "ai_external_effect_intents"
    __table_args__ = (
        Index("idx_ai_external_effect_intents_status", "status", "claim_generation"),
        {"extend_existing": True},
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=new_uuid_v7
    )
    root_task_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    task_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    execution_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("ai_executions.id", ondelete="CASCADE"),
        nullable=False,
    )
    stage_attempt_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("ai_stage_attempts.id"), nullable=True
    )
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    authorization_receipt_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("ai_authorization_receipts.id"),
        nullable=True,
    )
    operation_name: Mapped[str] = mapped_column(Text, nullable=False)
    risk_class: Mapped[str] = mapped_column(Text, nullable=False, default="R0")
    provider_route_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    canonical_request_hash: Mapped[str] = mapped_column(Text, nullable=False)
    provider_idempotency_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    claim_generation: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="prepared")
    attempt_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    provider_request_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_evidence_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reconciled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    adopted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AIExternalAttempt(Base):
    __tablename__ = "ai_external_attempts"
    __table_args__ = (
        Index("idx_ai_external_attempts_execution", "execution_id", "attempt_no"),
        {"extend_existing": True},
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=new_uuid_v7
    )
    task_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    execution_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("ai_executions.id", ondelete="CASCADE"),
        nullable=False,
    )
    root_task_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    stage_attempt_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("ai_stage_attempts.id"), nullable=True
    )
    external_effect_intent_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("ai_external_effect_intents.id"),
        nullable=True,
    )
    authorization_receipt_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    claim_generation_at_send: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    claim_generation_at_adoption: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    attempt_kind: Mapped[str] = mapped_column(Text, nullable=False)
    provider_internal_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    route_internal_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider_request_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    operation_name: Mapped[str] = mapped_column(Text, nullable=False)
    attempt_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="created")
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    failure_category: Mapped[str | None] = mapped_column(Text, nullable=True)
    side_effect_class: Mapped[str | None] = mapped_column(Text, nullable=True)
    side_effect_evidence_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    request_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_structure_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    usage_cost_event_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    trace_id: Mapped[str | None] = mapped_column(Text, nullable=True)


class AIMilestone(Base):
    __tablename__ = "ai_milestones"
    __table_args__ = (
        UniqueConstraint(
            "execution_id", "milestone_code", name="uq_ai_milestones_execution_code"
        ),
        {"extend_existing": True},
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=new_uuid_v7
    )
    task_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    execution_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("ai_executions.id", ondelete="CASCADE"),
        nullable=False,
    )
    root_task_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    milestone_code: Mapped[str] = mapped_column(Text, nullable=False)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    weight_basis_points: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    result_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    quality_gate_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    settle_eligible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    settled_point_event_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )


class ModelPolicyVersion(Base):
    __tablename__ = "ai_model_policy_versions"
    __table_args__ = (
        Index("idx_ai_model_policy_versions_key", "capability_code", "status"),
        {"extend_existing": True},
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=new_uuid_v7
    )
    capability_code: Mapped[str] = mapped_column(Text, nullable=False)
    subscenario: Mapped[str | None] = mapped_column(Text, nullable=True)
    service_tier: Mapped[str] = mapped_column(Text, nullable=False, default="standard")
    primary_route: Mapped[str] = mapped_column(Text, nullable=False)
    permitted_fallbacks: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    quality_gates: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    latency_target_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_ceiling: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    rollout_allocation: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    evaluation_evidence_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    rollback_target_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    owner: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="draft")
    effective_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class CapabilityAdapterVersion(Base):
    __tablename__ = "ai_capability_adapter_versions"
    __table_args__ = (
        UniqueConstraint(
            "capability_code",
            "action_code",
            "adapter_version",
            name="uq_ai_capability_adapter_versions",
        ),
        {"extend_existing": True},
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=new_uuid_v7
    )
    capability_code: Mapped[str] = mapped_column(Text, nullable=False)
    action_code: Mapped[str] = mapped_column(Text, nullable=False)
    adapter_version: Mapped[str] = mapped_column(Text, nullable=False)
    domain_aggregate_type: Mapped[str] = mapped_column(Text, nullable=False)
    state_mapping: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    milestone_catalog: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    cancel_resume_semantics: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    quote_policy: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    minimum_quality_gates: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    owner: Mapped[str] = mapped_column(Text, nullable=False)
    runbook: Mapped[str | None] = mapped_column(Text, nullable=True)
    rollout_status: Mapped[str] = mapped_column(Text, nullable=False, default="draft")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class AIEvidenceSnapshot(Base):
    __tablename__ = "ai_evidence_snapshots"
    __table_args__ = {"extend_existing": True}

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=new_uuid_v7
    )
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    task_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    encrypted_object_ref: Mapped[str] = mapped_column(Text, nullable=False)
    content_classes: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    fields_included: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    consent_source: Mapped[str | None] = mapped_column(Text, nullable=True)
    purpose: Mapped[str] = mapped_column(Text, nullable=False)
    badcase_ticket_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    privacy_class: Mapped[str] = mapped_column(Text, nullable=False, default="restricted")
    retention_expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class AIEvidenceAccess(Base):
    __tablename__ = "ai_evidence_access"
    __table_args__ = {"extend_existing": True}

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=new_uuid_v7
    )
    evidence_snapshot_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("ai_evidence_snapshots.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    actor_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    fields: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    action: Mapped[str] = mapped_column(Text, nullable=False)
    export_destination: Mapped[str | None] = mapped_column(Text, nullable=True)
    accessed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class TelemetryProjectionDelivery(Base):
    __tablename__ = "ai_telemetry_projection_deliveries"
    __table_args__ = (
        UniqueConstraint(
            "source_event_id",
            "destination",
            "destination_policy_version",
            name="uq_ai_telemetry_projection_deliveries",
        ),
        Index("idx_ai_telemetry_projection_status", "status", "next_attempt_at"),
        {"extend_existing": True},
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=new_uuid_v7
    )
    source_event_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    user_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True, index=True)
    destination: Mapped[str] = mapped_column(Text, nullable=False)
    representation: Mapped[str] = mapped_column(Text, nullable=False, default="metadata")
    destination_policy_version: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error_category: Mapped[str | None] = mapped_column(Text, nullable=True)
    destination_record_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    confirmed_position: Mapped[str | None] = mapped_column(Text, nullable=True)
    first_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_success_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class AIDataDeletionDelivery(Base):
    __tablename__ = "ai_data_deletion_deliveries"
    __table_args__ = (
        Index("idx_ai_data_deletion_deliveries_status", "status", "next_attempt_at"),
        {"extend_existing": True},
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=new_uuid_v7
    )
    provenance_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    root_task_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    subject_user_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True, index=True
    )
    store_code: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    evidence_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_error_category: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class OperationalTaskProjection(Base):
    __tablename__ = "ai_operational_task_projections"
    __table_args__ = {"extend_existing": True}

    task_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    root_task_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    capability_code: Mapped[str] = mapped_column(Text, nullable=False)
    action_code: Mapped[str] = mapped_column(Text, nullable=False)
    denormalized: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    source_event_sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    coverage: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    unknown_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fresh_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


__all__ = [
    "AITask",
    "AIInputSnapshot",
    "AIPolicySnapshot",
    "AIExecution",
    "AIDispatchIntent",
    "AIAuthorizationReceipt",
    "AITaskEvent",
    "AIStageAttempt",
    "AIExternalEffectIntent",
    "AIExternalAttempt",
    "AIMilestone",
    "ModelPolicyVersion",
    "CapabilityAdapterVersion",
    "AIEvidenceSnapshot",
    "AIEvidenceAccess",
    "TelemetryProjectionDelivery",
    "AIDataDeletionDelivery",
    "OperationalTaskProjection",
]
