"""AbilityDimension + AbilityDimensionHistory SQLAlchemy models.

Per data-model-phase-2.md §3-4.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.core.ids import new_uuid_v7


class AbilityDimension(Base):
    __tablename__ = "ability_dimensions"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=new_uuid_v7
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    dimension_key: Mapped[str] = mapped_column(Text, nullable=False)
    actual_score: Mapped[Decimal] = mapped_column(
        Numeric(4, 2), nullable=False, default=Decimal("0.00")
    )
    ideal_score: Mapped[Decimal] = mapped_column(
        Numeric(4, 2), nullable=False, default=Decimal("10.00")
    )
    # User self-assessment; preserved across interview UPSERTs (Feature 006 dual-track).
    self_assessed_score: Mapped[Decimal | None] = mapped_column(
        Numeric(4, 2), nullable=True, default=None
    )
    sub_scores: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    source: Mapped[str] = mapped_column(Text, nullable=False, default="manual")
    last_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("user_id", "dimension_key", name="ability_dimensions_user_key_unique"),
    )


class AbilityDimensionHistory(Base):
    __tablename__ = "ability_dimensions_history"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=new_uuid_v7
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    dimension_key: Mapped[str] = mapped_column(Text, nullable=False)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    aggregate: Mapped[str] = mapped_column(Text, nullable=False)
    actual_score: Mapped[Decimal] = mapped_column(Numeric(4, 2), nullable=False)
    ideal_score: Mapped[Decimal] = mapped_column(Numeric(4, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint(
            "user_id", "dimension_key", "aggregate", "snapshot_date",
            name="ability_history_user_dim_agg_date_unique",
        ),
    )


__all__ = ["AbilityDimension", "AbilityDimensionHistory"]
