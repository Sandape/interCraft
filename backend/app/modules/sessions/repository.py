"""AuthSession repository — 10-device limit aware, expires_at filtered.

FR-003: list_active and count_active filter by expires_at > NOW() so
expired sessions do not consume the max_active_sessions quota.
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import AuthSession
from app.repositories.base import BaseRepository


class SessionRepository(BaseRepository[AuthSession]):
    model = AuthSession

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def list_active(self, user_id: UUID) -> list[AuthSession]:
        now = datetime.now(timezone.utc)
        stmt = (
            select(AuthSession)
            .where(
                AuthSession.user_id == user_id,
                AuthSession.deleted_at.is_(None),
                AuthSession.expires_at > now,
            )
            .order_by(AuthSession.last_seen_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_active(self, user_id: UUID) -> int:
        from sqlalchemy import func as sa_func

        now = datetime.now(timezone.utc)
        stmt = select(sa_func.count()).select_from(AuthSession).where(
            AuthSession.user_id == user_id,
            AuthSession.deleted_at.is_(None),
            AuthSession.expires_at > now,
        )
        result = await self.session.execute(stmt)
        return int(result.scalar() or 0)

    async def get_by_refresh_hash(self, refresh_hash: str) -> AuthSession | None:
        stmt = select(AuthSession).where(
            AuthSession.refresh_token_hash == refresh_hash,
            AuthSession.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id(self, session_id: UUID) -> AuthSession | None:
        return await self.get(session_id)

    async def oldest_active(self, user_id: UUID) -> AuthSession | None:
        now = datetime.now(timezone.utc)
        stmt = (
            select(AuthSession)
            .where(
                AuthSession.user_id == user_id,
                AuthSession.deleted_at.is_(None),
                AuthSession.expires_at > now,
            )
            .order_by(AuthSession.last_seen_at.asc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def soft_delete(self, id: UUID) -> bool:  # type: ignore[override]
        return await super().soft_delete(id)

    async def mark_seen(self, session_id: UUID, *, ip: str | None = None, ua: str | None = None) -> None:
        sess = await self.get(session_id)
        if sess is None:
            return
        sess.last_seen_at = datetime.utcnow()
        if ip:
            sess.last_seen_ip = ip
        if ua:
            sess.last_seen_ua = ua
        await self.session.flush()


__all__ = ["SessionRepository"]
