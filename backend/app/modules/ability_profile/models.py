"""ProfileShareLink, ProfileView, ExportLog SQLAlchemy models.

Per data-model.md §1-3 for Feature 006 — Personal Ability Profile.
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Text, CheckConstraint, func, Index, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.ids import new_uuid_v7


class ProfileShareLink(Base):
    __tablename__ = "profile_share_links"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=new_uuid_v7
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    pin_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_accessed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    access_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint("length(token) = 36", name="ck_share_links_token_length"),
        CheckConstraint(
            "revoked_at IS NULL OR expires_at IS NULL OR revoked_at < expires_at",
            name="ck_share_links_revoked_before_expires",
        ),
        CheckConstraint("access_count >= 0", name="ck_share_links_access_count"),
        Index("idx_share_links_active", "user_id",
              postgresql_where=text("revoked_at IS NULL")),
    )


class ProfileView(Base):
    """Append-only access log for share link views."""
    __tablename__ = "profile_views"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=new_uuid_v7
    )
    share_link_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("profile_share_links.id", ondelete="CASCADE"), nullable=False
    )
    ip_prefix: Mapped[str] = mapped_column(Text, nullable=False)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    pin_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    viewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint("length(ip_prefix) BETWEEN 3 AND 45", name="ck_profile_views_ip_prefix_length"),
        Index("idx_profile_views_share_link", "share_link_id", postgresql_using="btree"),
    )


class ExportLog(Base):
    __tablename__ = "export_logs"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=new_uuid_v7
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending", server_default=text("'pending'"))
    file_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        server_default=text("now() + interval '24 hours'")
    )

    __table_args__ = (
        CheckConstraint("status IN ('pending','processing','completed','failed')", name="ck_export_logs_status"),
        CheckConstraint("file_size_bytes IS NULL OR file_size_bytes > 0", name="ck_export_logs_file_size"),
        CheckConstraint("completed_at IS NULL OR completed_at >= requested_at", name="ck_export_logs_completed_at"),
        CheckConstraint("status != 'completed' OR file_path IS NOT NULL", name="ck_export_logs_completed_has_file"),
        Index("idx_export_logs_expires", "expires_at", postgresql_where=text("status = 'completed'")),
    )


__all__ = ["ProfileShareLink", "ProfileView", "ExportLog"]
