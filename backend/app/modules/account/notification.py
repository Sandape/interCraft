"""Phase 6 — Notification service (站内通知 CRUD)."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Text, Boolean, func, select, update
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.domain.mixins import UUIDv7PrimaryKeyMixin


class Notification(Base, UUIDv7PrimaryKeyMixin):
    """Internal notification (站内通知)."""

    __tablename__ = "notifications"

    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    type: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    related_task_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class NotificationService:
    """CRUD for in-app notifications."""

    def __init__(self, db: AsyncSession, user_id: UUID) -> None:
        self.db = db
        self.user_id = user_id

    async def create(
        self,
        type_: str,
        title: str,
        message: str,
        related_task_id: UUID | None = None,
    ) -> Notification:
        n = Notification(
            user_id=self.user_id,
            type=type_,
            title=title,
            message=message,
            related_task_id=related_task_id,
        )
        self.db.add(n)
        await self.db.flush()
        return n

    async def list_notifications(self, limit: int = 50, offset: int = 0) -> list[Notification]:
        result = await self.db.execute(
            select(Notification)
            .where(Notification.user_id == self.user_id)
            .order_by(Notification.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def get_unread_count(self) -> int:
        result = await self.db.execute(
            select(func.count()).where(
                Notification.user_id == self.user_id,
                Notification.is_read == False,  # noqa: E712
            )
        )
        return result.scalar() or 0

    async def mark_as_read(self, notification_id: UUID) -> None:
        await self.db.execute(
            update(Notification)
            .where(Notification.id == notification_id, Notification.user_id == self.user_id)
            .values(is_read=True)
        )
