"""Phase 6 — Content module ORM models: resources, help_faq, subscription_plans."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, DateTime, Integer, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.domain.mixins import TimestampedMixin, UUIDv7PrimaryKeyMixin


class Resource(Base, UUIDv7PrimaryKeyMixin, TimestampedMixin):
    """resources table — educational content for users."""

    __tablename__ = "resources"

    title: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    tags: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str] = mapped_column(Text, nullable=False, default="article")
    read_time_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    video_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        CheckConstraint(
            "category IN ('interview_tips','resume_guide','tech_prep')",
            name="resources_category_chk",
        ),
        CheckConstraint(
            "content_type IN ('article','video','template')",
            name="resources_content_type_chk",
        ),
    )


class HelpFAQ(Base, UUIDv7PrimaryKeyMixin, TimestampedMixin):
    """help_faq table — frequently asked questions."""

    __tablename__ = "help_faq"

    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        CheckConstraint(
            "category IN ('account','interview','resume','subscription','technical')",
            name="help_faq_category_chk",
        ),
    )


class SubscriptionPlan(Base):
    """subscription_plans table — config-driven plan definitions."""

    __tablename__ = "subscription_plans"

    plan: Mapped[str] = mapped_column(Text, primary_key=True)
    monthly_token_quota: Mapped[int] = mapped_column(Integer, nullable=False)
    features: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "plan IN ('free','pro','enterprise')",
            name="subscription_plans_plan_chk",
        ),
    )


__all__ = ["HelpFAQ", "Resource", "SubscriptionPlan"]
