"""M06 — ResumeBranch + ResumeBlock ORM models."""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.domain.mixins import (
    SoftDeletableMixin,
    TenantScopedMixin,
    TimestampedMixin,
    UUIDv7PrimaryKeyMixin,
)


class ResumeBranch(
    Base,
    UUIDv7PrimaryKeyMixin,
    TimestampedMixin,
    SoftDeletableMixin,
    TenantScopedMixin,
):
    """A single resume tree node (the "core" or a derived branch)."""

    __tablename__ = "resume_branches"

    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    parent_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("resume_branches.id", ondelete="SET NULL"),
        nullable=True,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    company: Mapped[str | None] = mapped_column(Text, nullable=True)
    position: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="draft")
    match_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    is_main: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_pinned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_edited_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    style_preference: Mapped[str] = mapped_column(
        String(64), nullable=False, default="compact-one-page"
    )

    blocks: Mapped[list[ResumeBlock]] = relationship(
        "ResumeBlock",
        primaryjoin="ResumeBranch.id == foreign(ResumeBlock.branch_id)",
        viewonly=True,
    )
    versions: Mapped[list[ResumeVersion]] = relationship(
        "ResumeVersion",
        primaryjoin="ResumeBranch.id == foreign(ResumeVersion.branch_id)",
        viewonly=True,
    )

    __table_args__ = (
        Index(
            "resume_branches_user_pinned_main_edited_idx",
            "user_id",
            "is_pinned",
            "is_main",
            "last_edited_at",
        ),
        Index("resume_branches_user_deleted_idx", "user_id", "deleted_at"),
        Index("resume_branches_parent_idx", "parent_id"),
        CheckConstraint(
            "is_main = FALSE OR parent_id IS NULL",
            name="resume_branches_main_no_parent_chk",
        ),
        CheckConstraint(
            "status IN ('draft','optimizing','ready','submitted','archived')",
            name="resume_branches_status_chk",
        ),
        CheckConstraint(
            "match_score IS NULL OR (match_score >= 0 AND match_score <= 100)",
            name="resume_branches_match_score_chk",
        ),
    )


class ResumeBlock(
    Base,
    UUIDv7PrimaryKeyMixin,
    TimestampedMixin,
    SoftDeletableMixin,
    TenantScopedMixin,
):
    """A single Notion-style block (heading / summary / experience / etc.)."""

    __tablename__ = "resume_blocks"

    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    branch_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        # Intentionally NO foreign key to allow COW semantics.
        nullable=False,
    )
    type: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_md: Mapped[str] = mapped_column(Text, nullable=False, default="")
    content_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    order_index: Mapped[str] = mapped_column(String(64), nullable=False)
    collapsed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    branch: Mapped[ResumeBranch] = relationship(
        "ResumeBranch", primaryjoin="ResumeBlock.branch_id == foreign(ResumeBranch.id)", viewonly=True
    )

    __table_args__ = (
        Index(
            "resume_blocks_branch_order_idx",
            "branch_id",
            "order_index",
            postgresql_where=Text("deleted_at IS NULL"),
        ),
        Index("resume_blocks_user_deleted_idx", "user_id", "deleted_at"),
        Index("resume_blocks_user_type_idx", "user_id", "type", "deleted_at"),
        CheckConstraint(
            "type IN ('heading','summary','experience','project','skill','education','custom')",
            name="resume_blocks_type_chk",
        ),
        CheckConstraint(
            "length(order_index) > 0 AND length(order_index) < 64",
            name="resume_blocks_order_index_chk",
        ),
    )


# To avoid circular imports at module load:
from app.modules.versions.models import ResumeVersion  # noqa: E402

__all__ = ["ResumeBlock", "ResumeBranch"]
