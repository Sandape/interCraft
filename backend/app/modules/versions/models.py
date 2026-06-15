"""M07 — ResumeVersion ORM model."""
from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.domain.mixins import TenantScopedMixin, TimestampedMixin, UUIDv7PrimaryKeyMixin


class ResumeVersion(
    Base,
    UUIDv7PrimaryKeyMixin,
    TimestampedMixin,
    TenantScopedMixin,
):
    """A point-in-time version of a branch. Immutable once written.

    Phase 1 only writes full snapshots (manual / auto-init). Diff
    snapshots are written by the ARQ auto_snapshot task starting
    Phase 2.
    """

    __tablename__ = "resume_versions"

    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    branch_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    label: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_full_snapshot: Mapped[bool] = mapped_column(nullable=False, default=True)
    snapshot_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    base_version_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("resume_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    diff_patch: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)
    author_type: Mapped[str] = mapped_column(Text, nullable=False, default="user")
    actor_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    trigger: Mapped[str] = mapped_column(Text, nullable=False, default="manual")

    branch = relationship(
        "ResumeBranch", primaryjoin="ResumeVersion.branch_id == foreign(ResumeBranch.id)", viewonly=True
    )

    __table_args__ = (
        UniqueConstraint("branch_id", "version_no", name="resume_versions_branch_no_unique"),
        Index(
            "resume_versions_branch_snapshot_idx",
            "branch_id",
            "is_full_snapshot",
            "version_no",
        ),
        Index("resume_versions_user_created_idx", "user_id", "created_at"),
        CheckConstraint(
            "author_type IN ('user','ai')", name="resume_versions_author_chk"
        ),
        CheckConstraint(
            "trigger IN ('manual','auto','ai')", name="resume_versions_trigger_chk"
        ),
        CheckConstraint(
            "is_full_snapshot = TRUE OR (diff_patch IS NOT NULL AND base_version_id IS NOT NULL AND snapshot_json IS NULL)",
            name="resume_versions_diff_chk",
        ),
        CheckConstraint(
            "is_full_snapshot = FALSE OR (snapshot_json IS NOT NULL AND diff_patch IS NULL)",
            name="resume_versions_full_chk",
        ),
    )


__all__ = ["ResumeVersion"]
