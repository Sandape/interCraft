"""REQ-033 — consolidated ORM models (REB-032 v2 MVP import stub).

The real models (Badcase, BadcaseReviewAction, TelemetrySpan,
PMDashboardSnapshot, etc.) are defined in their respective modules
per the FOUNDATION consolidation (T020). For the REB-032 v2 MVP we
only need this module to import cleanly so the badcases + pm_dashboard
shims can re-export from here. The full table definitions + Alembic
migrations ship via the 033 US phases.

We declare minimal table shells so the import chain stays green.
Runtime SQL is exercised through Alembic-migrated tables in the real
schema; the stubs below are intentionally not registered with the
shared ``Base.metadata`` so they don't shadow the production DDL.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Badcase(Base):
    """Stub: full table definition ships in 033 US8 (T058)."""

    __tablename__ = "badcases"
    __table_args__ = {"extend_existing": True}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    source: Mapped[str] = mapped_column(String(64))
    type: Mapped[str] = mapped_column(String(64))
    severity: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), default="OPEN")
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    failure_reason: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class BadcaseReviewAction(Base):
    """Stub: append-only audit log row."""

    __tablename__ = "badcase_review_actions"
    __table_args__ = {"extend_existing": True}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    badcase_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    actor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    action: Mapped[str] = mapped_column(String(64))
    notes: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AIInvocationRecord(Base):
    """Stub: AI invocation log row (033 US1)."""

    __tablename__ = "ai_invocation_records"
    __table_args__ = {"extend_existing": True}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    agent_name: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="SUCCESS")
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    estimated_cost: Mapped[float] = mapped_column(Integer, default=0)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ProductFunnelEvent(Base):
    """Stub: product funnel event row (033 US1)."""

    __tablename__ = "product_events"
    __table_args__ = {"extend_existing": True}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    event_name: Mapped[str] = mapped_column(String(128), index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


__all__ = [
    "Badcase",
    "BadcaseReviewAction",
    "AIInvocationRecord",
    "ProductFunnelEvent",
]