"""SQLAlchemy models for the IRT item bank (REQ-030 US1).

Three tables, per specs/030-irt-adaptive-diagnosis/plan.md §"Data Model":

  - `irt_items` — global item bank, NOT RLS-scoped (shared across users).
  - `irt_item_responses` — per-user response history, RLS-scoped.
  - `irt_ability_thetas` — per-user θ estimates, RLS-scoped.

Why no RLS on `irt_items`?
    The item bank is a global psychometric resource. Calibration requires
    aggregating responses from many users onto each item; per-user item
    tables would fragment the data and prevent batch calibration. The
    responses and thetas tables ARE RLS-scoped because they contain
    per-user information that should never leak across users.

CHECK constraints enforce the same bounds as the Pydantic schemas
(`backend/app/modules/irt/schemas.py`); the ORM is the second line of
defense, not the first.
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.ids import new_uuid_v7


class Item(Base):
    """A single interview question with calibrated IRT parameters.

    US1 seeds items with hardcoded (a, b) parameters; US3 will recalibrate
    from production response data. `question_text_hash` is SHA-256 of the
    canonical question text — full text is intentionally not stored in the
    bank (avoids duplication with interview_sessions.questions).
    """

    __tablename__ = "irt_items"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=new_uuid_v7
    )
    dimension: Mapped[str] = mapped_column(Text, nullable=False)
    question_text_hash: Mapped[str] = mapped_column(Text, nullable=False)
    # b ∈ [-6, +6] logit; a ∈ [0, 5] logit slope. Bounds match the DB CHECK
    # and Pydantic ItemCreate. Decimal storage preserves sub-millilogit
    # precision in b — important when items are clustered.
    difficulty_b: Mapped[float] = mapped_column(
        Numeric(6, 3), nullable=False
    )
    discrimination_a: Mapped[float] = mapped_column(
        Numeric(6, 3), nullable=False
    )
    # 2pl | 3pl. US1 only exercises 2pl; the column is forward-compat
    # for US2/3 work that adds 3-PL guessing (c) parameter.
    model: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'2pl'")
    )
    # uncalibrated | calibrated | retired | flagged. New items land
    # "uncalibrated"; US3 promotes them to "calibrated" after 30+
    # responses + MML convergence. "retired" excludes from selection
    # but preserves history. "flagged" is for review (extreme a, drift).
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'uncalibrated'")
    )
    response_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    # SE at last calibration. 0 for uncalibrated items.
    standard_error: Mapped[float] = mapped_column(
        Numeric(6, 3), nullable=False, server_default=text("0")
    )
    last_calibrated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('uncalibrated','calibrated','retired','flagged')",
            name="ck_irt_items_status",
        ),
        CheckConstraint(
            "model IN ('2pl','3pl')",
            name="ck_irt_items_model",
        ),
        CheckConstraint(
            "difficulty_b BETWEEN -6 AND 6",
            name="ck_irt_items_difficulty_range",
        ),
        CheckConstraint(
            "discrimination_a >= 0 AND discrimination_a <= 5",
            name="ck_irt_items_discrimination_range",
        ),
        CheckConstraint(
            "response_count >= 0",
            name="ck_irt_items_response_count",
        ),
        CheckConstraint(
            "standard_error >= 0",
            name="ck_irt_items_se",
        ),
        # Partial unique index: a non-retired item is unique by
        # (dimension, question_text_hash). Retired items are excluded so
        # the same question can be re-introduced after retirement.
        Index(
            "uq_irt_items_active_dim_hash",
            "dimension",
            "question_text_hash",
            unique=True,
            postgresql_where=text("status != 'retired'"),
        ),
        Index(
            "idx_irt_items_dimension_status",
            "dimension",
            "status",
        ),
    )


class ItemResponse(Base):
    """A single user response to an item, used for calibration + θ estimation.

    `item_id` is ON DELETE SET NULL so item retirement preserves response
    history (spec FR-015). `response` is binary in US1 ('correct' /
    'incorrect'); 3-PL partial-credit work would extend this.
    """

    __tablename__ = "irt_item_responses"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=new_uuid_v7
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    item_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("irt_items.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    response: Mapped[str] = mapped_column(Text, nullable=False)
    score: Mapped[float] = mapped_column(
        Numeric(4, 2), nullable=False
    )
    source_interview_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "response IN ('correct','incorrect')",
            name="ck_irt_responses_label",
        ),
        CheckConstraint(
            "score >= 0 AND score <= 10",
            name="ck_irt_responses_score_range",
        ),
        Index(
            "idx_irt_responses_user_dim",
            "user_id",
            "created_at",
        ),
    )


class AbilityTheta(Base):
    """A per-(user, dimension) θ estimate produced by the IRT engine.

    Multiple rows per (user, dimension) are expected over time — one per
    completed interview. The latest row is "current"; history is retained
    for the θ-evolution view (US2's per-dimension timeline).
    """

    __tablename__ = "irt_ability_thetas"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=new_uuid_v7
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    dimension: Mapped[str] = mapped_column(Text, nullable=False)
    theta: Mapped[float] = mapped_column(Numeric(6, 3), nullable=False)
    standard_error: Mapped[float] = mapped_column(
        Numeric(6, 3), nullable=False
    )
    n_items: Mapped[int] = mapped_column(Integer, nullable=False)
    source_interview_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    model: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'2pl'")
    )
    converged: Mapped[bool] = mapped_column(
        # BOOLEAN NOT NULL with no default — caller must decide.
        nullable=False,
        server_default=text("true"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "model IN ('2pl','3pl')",
            name="ck_irt_thetas_model",
        ),
        CheckConstraint(
            "theta BETWEEN -6 AND 6",
            name="ck_irt_thetas_theta_range",
        ),
        CheckConstraint(
            "standard_error > 0",
            name="ck_irt_thetas_se_positive",
        ),
        CheckConstraint(
            "n_items >= 1",
            name="ck_irt_thetas_n_items",
        ),
        Index(
            "idx_irt_thetas_user_dim",
            "user_id",
            "dimension",
            "created_at",
        ),
    )


__all__ = ["AbilityTheta", "Item", "ItemResponse"]
