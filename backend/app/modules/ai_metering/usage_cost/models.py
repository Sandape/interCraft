"""REQ-061 usage/cost fact ORM entities (T015).

Per-attempt usage and cost are append-only. Adjustments link to base facts;
allocations must conserve confirmed source cost.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import (
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


class CostRateVersion(Base):
    __tablename__ = "ai_cost_rate_versions"
    __table_args__ = (
        Index("idx_ai_cost_rate_versions_key", "provider_internal_key", "status"),
        {"extend_existing": True},
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=new_uuid_v7
    )
    version: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    provider_internal_key: Mapped[str] = mapped_column(Text, nullable=False)
    model_or_tool_key: Mapped[str] = mapped_column(Text, nullable=False)
    unit: Mapped[str] = mapped_column(Text, nullable=False, default="token")
    input_per_1k: Mapped[Decimal | None] = mapped_column(Numeric(20, 10), nullable=True)
    output_per_1k: Mapped[Decimal | None] = mapped_column(Numeric(20, 10), nullable=True)
    cache_dimensions: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    currency: Mapped[str] = mapped_column(Text, nullable=False, default="USD")
    source: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="draft")
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    activation_audit: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class FxRateVersion(Base):
    __tablename__ = "ai_fx_rate_versions"
    __table_args__ = {"extend_existing": True}

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=new_uuid_v7
    )
    version: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    base_currency: Mapped[str] = mapped_column(Text, nullable=False)
    quote_currency: Mapped[str] = mapped_column(Text, nullable=False, default="CNY")
    rate: Mapped[Decimal] = mapped_column(Numeric(20, 10), nullable=False)
    source: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="draft")
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class UsageCostEvent(Base):
    __tablename__ = "ai_usage_cost_events"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_ai_usage_cost_events_idem"),
        Index("idx_ai_usage_cost_events_attempt", "external_attempt_id"),
        Index("idx_ai_usage_cost_events_task", "task_id"),
        {"extend_existing": True},
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=new_uuid_v7
    )
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)
    external_attempt_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    platform_cost_category: Mapped[str | None] = mapped_column(Text, nullable=True)
    task_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    root_task_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    execution_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    user_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True, index=True)
    subject_id: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    provider_request_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    event_status: Mapped[str] = mapped_column(Text, nullable=False, default="recorded")
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cache_creation_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cache_read_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reasoning_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    embedding_units: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    rerank_units: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    searches: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tool_units: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    storage_units: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    bandwidth_units: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    custom_unit_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    custom_unit_quantity: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    original_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 10), nullable=True)
    original_currency: Mapped[str | None] = mapped_column(Text, nullable=True)
    rate_version_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("ai_cost_rate_versions.id"), nullable=True
    )
    fx_version_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("ai_fx_rate_versions.id"), nullable=True
    )
    locked_rate: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    locked_fx: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    rmb_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 10), nullable=True)
    evidence_source: Mapped[str | None] = mapped_column(Text, nullable=True)
    cost_status: Mapped[str] = mapped_column(Text, nullable=False, default="estimated")
    attribution: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )


class CostAdjustment(Base):
    __tablename__ = "ai_cost_adjustments"
    __table_args__ = (
        Index("idx_ai_cost_adjustments_base", "base_event_id"),
        {"extend_existing": True},
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=new_uuid_v7
    )
    base_event_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("ai_usage_cost_events.id", ondelete="CASCADE"),
        nullable=False,
    )
    prior_adjustment_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("ai_cost_adjustments.id"), nullable=True
    )
    old_evidence_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_evidence_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    delta_original: Mapped[Decimal] = mapped_column(Numeric(20, 10), nullable=False)
    delta_rmb: Mapped[Decimal | None] = mapped_column(Numeric(20, 10), nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    actor_type: Mapped[str] = mapped_column(Text, nullable=False, default="system")
    actor_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    reversed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class CostAllocation(Base):
    __tablename__ = "ai_cost_allocations"
    __table_args__ = (
        UniqueConstraint(
            "source_event_id",
            "task_id",
            "rule_version",
            name="uq_ai_cost_allocations_source_task_rule",
        ),
        {"extend_existing": True},
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=new_uuid_v7
    )
    source_event_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("ai_usage_cost_events.id", ondelete="CASCADE"),
        nullable=False,
    )
    task_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    execution_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    rule_version: Mapped[str] = mapped_column(Text, nullable=False)
    numerator: Mapped[Decimal] = mapped_column(Numeric(20, 10), nullable=False)
    denominator: Mapped[Decimal] = mapped_column(Numeric(20, 10), nullable=False)
    allocated_original: Mapped[Decimal] = mapped_column(Numeric(20, 10), nullable=False)
    allocated_rmb: Mapped[Decimal | None] = mapped_column(Numeric(20, 10), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ReconciliationRun(Base):
    __tablename__ = "ai_reconciliation_runs"
    __table_args__ = (
        Index("idx_ai_reconciliation_runs_type", "run_type", "started_at"),
        {"extend_existing": True},
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=new_uuid_v7
    )
    run_type: Mapped[str] = mapped_column(Text, nullable=False)
    scope: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    expected_total: Mapped[Decimal | None] = mapped_column(Numeric(20, 10), nullable=True)
    actual_total: Mapped[Decimal | None] = mapped_column(Numeric(20, 10), nullable=True)
    difference: Mapped[Decimal | None] = mapped_column(Numeric(20, 10), nullable=True)
    difference_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="running")
    evidence_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ReconciliationIssue(Base):
    __tablename__ = "ai_reconciliation_issues"
    __table_args__ = (
        Index("idx_ai_reconciliation_issues_run", "run_id", "status"),
        {"extend_existing": True},
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=new_uuid_v7
    )
    run_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("ai_reconciliation_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    issue_class: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(Text, nullable=False, default="P2")
    affected_identities: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    owner: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="open")
    correction_event_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


__all__ = [
    "CostRateVersion",
    "FxRateVersion",
    "UsageCostEvent",
    "CostAdjustment",
    "CostAllocation",
    "ReconciliationRun",
    "ReconciliationIssue",
]
