"""REQ-061 AI Metering point ledger ORM entities (T014).

Point facts are append-only. Account/bucket balances are rebuildable
projections updated atomically with ledger events.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
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


class PointAccount(Base):
    __tablename__ = "ai_point_accounts"
    __table_args__ = {"extend_existing": True}

    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    subject_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    available_points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reserved_points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    projection_sequence: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    daily_budget_points: Mapped[int | None] = mapped_column(Integer, nullable=True)
    risk_consumption_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class DailyGrantConfigVersion(Base):
    __tablename__ = "ai_daily_grant_config_versions"
    __table_args__ = {"extend_existing": True}

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=new_uuid_v7
    )
    version: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    points_amount: Mapped[int] = mapped_column(Integer, nullable=False, default=2000)
    timezone: Mapped[str] = mapped_column(
        Text, nullable=False, default="Asia/Shanghai", server_default="Asia/Shanghai"
    )
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="active")
    actor_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class PointPriceTableVersion(Base):
    __tablename__ = "ai_point_price_table_versions"
    __table_args__ = {"extend_existing": True}

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=new_uuid_v7
    )
    version: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    entries: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    owner: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    approval_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="draft")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class PointBucket(Base):
    __tablename__ = "ai_point_buckets"
    __table_args__ = (
        Index("idx_ai_point_buckets_expiry", "expires_at", "status"),
        Index("idx_ai_point_buckets_user_date", "user_id", "business_date", "bucket_type"),
        {"extend_existing": True},
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=new_uuid_v7
    )
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    subject_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    bucket_type: Mapped[str] = mapped_column(Text, nullable=False)
    business_date: Mapped[date] = mapped_column(Date, nullable=False)
    grant_config_version_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("ai_daily_grant_config_versions.id"),
        nullable=True,
    )
    granted_points: Mapped[int] = mapped_column(Integer, nullable=False)
    available_points: Mapped[int] = mapped_column(Integer, nullable=False)
    reserved_points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    consumed_points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    expired_points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source_event_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class PointQuote(Base):
    __tablename__ = "ai_point_quotes"
    __table_args__ = {"extend_existing": True}

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=new_uuid_v7
    )
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    capability_code: Mapped[str] = mapped_column(Text, nullable=False)
    action_code: Mapped[str] = mapped_column(Text, nullable=False)
    service_tier: Mapped[str] = mapped_column(Text, nullable=False, default="standard")
    input_snapshot_hash: Mapped[str] = mapped_column(Text, nullable=False)
    price_table_version_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("ai_point_price_table_versions.id"),
        nullable=False,
    )
    milestones: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    max_points: Mapped[int] = mapped_column(Integer, nullable=False)
    displayed_balance: Mapped[int] = mapped_column(Integer, nullable=False)
    degradation_authorized: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="quoted")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class PointReservation(Base):
    __tablename__ = "ai_point_reservations"
    __table_args__ = (
        Index("idx_ai_point_reservations_task", "task_id"),
        {"extend_existing": True},
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=new_uuid_v7
    )
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    subject_id: Mapped[str] = mapped_column(Text, nullable=False)
    task_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    quote_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("ai_point_quotes.id"),
        nullable=False,
    )
    reserved_points: Mapped[int] = mapped_column(Integer, nullable=False)
    remaining_points: Mapped[int] = mapped_column(Integer, nullable=False)
    source_bucket_ids: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, default="reserved")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reconciliation_marker: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class PointLedgerEvent(Base):
    __tablename__ = "ai_point_ledger_events"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_ai_point_ledger_events_idem"),
        Index("idx_ai_point_ledger_events_user", "user_id", "recorded_at"),
        Index("idx_ai_point_ledger_events_task", "task_id"),
        {"extend_existing": True},
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=new_uuid_v7
    )
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    event_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    subject_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    account_user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    bucket_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    reservation_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    task_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    execution_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    milestone_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    available_delta: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reserved_delta: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    business_date: Mapped[date] = mapped_column(Date, nullable=False)
    expiry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source_event_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    corrects_event_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("ai_point_ledger_events.id"), nullable=True
    )
    actor_type: Mapped[str] = mapped_column(Text, nullable=False, default="system")
    actor_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    config_version_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    price_version_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    account_sequence: Mapped[int] = mapped_column(BigInteger, nullable=False)
    before_available: Mapped[int] = mapped_column(Integer, nullable=False)
    after_available: Mapped[int] = mapped_column(Integer, nullable=False)
    before_reserved: Mapped[int] = mapped_column(Integer, nullable=False)
    after_reserved: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )


class PointLedgerPosting(Base):
    __tablename__ = "ai_point_ledger_postings"
    __table_args__ = (
        UniqueConstraint(
            "event_id",
            "compartment",
            "sequence",
            name="uq_ai_point_ledger_postings_event_seq",
        ),
        Index("idx_ai_point_ledger_postings_event", "event_id"),
        {"extend_existing": True},
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=new_uuid_v7
    )
    event_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("ai_point_ledger_events.id", ondelete="CASCADE"),
        nullable=False,
    )
    subject_id: Mapped[str] = mapped_column(Text, nullable=False)
    compartment: Mapped[str] = mapped_column(Text, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    bucket_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    task_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    execution_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    milestone_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)


__all__ = [
    "PointAccount",
    "DailyGrantConfigVersion",
    "PointPriceTableVersion",
    "PointBucket",
    "PointQuote",
    "PointReservation",
    "PointLedgerEvent",
    "PointLedgerPosting",
]
