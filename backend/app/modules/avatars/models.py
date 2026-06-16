"""UserAvatar ORM model — Feature 013."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Text, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class UserAvatar(
    Base,
):
    """An uploaded avatar image owned by a single user."""

    __tablename__ = "user_avatars"
    __table_args__ = (
        CheckConstraint(
            "content_type IN ('image/jpeg', 'image/png')",
            name="ck_user_avatars_content_type",
        ),
        CheckConstraint(
            "byte_size > 0 AND byte_size <= 2097152",
            name="ck_user_avatars_byte_size",
        ),
        CheckConstraint(
            "width IS NULL OR (width > 0 AND width <= 2048)",
            name="ck_user_avatars_width",
        ),
        CheckConstraint(
            "height IS NULL OR (height > 0 AND height <= 2048)",
            name="ck_user_avatars_height",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    content_type: Mapped[str] = mapped_column(Text, nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Lazy back-reference; not always loaded.
    owner = relationship(
        "User",
        back_populates="avatars",
        primaryjoin="UserAvatar.user_id == User.id",
        foreign_keys=[user_id],
        lazy="noload",
    )


__all__ = ["UserAvatar"]
