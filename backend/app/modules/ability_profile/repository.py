"""AbilityProfileRepository — CRUD for profile_share_links + export_logs."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ability_profile.models import ProfileShareLink, ExportLog


class AbilityProfileRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ── Share Links ──────────────────────────────────────────────────────────

    async def create_share_link(self, link: ProfileShareLink) -> ProfileShareLink:
        self.session.add(link)
        await self.session.flush()
        await self.session.refresh(link)
        return link

    async def get_share_link_by_id(self, link_id: UUID, user_id: UUID) -> ProfileShareLink | None:
        stmt = select(ProfileShareLink).where(
            ProfileShareLink.id == link_id,
            ProfileShareLink.user_id == user_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_share_link_by_token(self, token: str) -> ProfileShareLink | None:
        stmt = select(ProfileShareLink).where(ProfileShareLink.token == token)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_share_links(self, user_id: UUID) -> list[ProfileShareLink]:
        stmt = select(ProfileShareLink).where(
            ProfileShareLink.user_id == user_id
        ).order_by(ProfileShareLink.created_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_active_share_links(self, user_id: UUID) -> int:
        now = datetime.now(timezone.utc)
        stmt = select(func.count()).select_from(ProfileShareLink).where(
            ProfileShareLink.user_id == user_id,
            ProfileShareLink.revoked_at.is_(None),
            (ProfileShareLink.expires_at.is_(None)) | (ProfileShareLink.expires_at > now),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def revoke_share_link(self, link_id: UUID, user_id: UUID) -> ProfileShareLink | None:
        link = await self.get_share_link_by_id(link_id, user_id)
        if link is None:
            return None
        link.revoked_at = datetime.now(timezone.utc)
        await self.session.flush()
        await self.session.refresh(link)
        return link

    async def record_share_link_access(self, token: str) -> None:
        now = datetime.now(timezone.utc)
        stmt = (
            update(ProfileShareLink)
            .where(ProfileShareLink.token == token)
            .values(
                last_accessed_at=now,
                access_count=ProfileShareLink.access_count + 1,
            )
        )
        await self.session.execute(stmt)

    # ── Export Logs ──────────────────────────────────────────────────────────

    async def create_export_log(self, log: ExportLog) -> ExportLog:
        self.session.add(log)
        await self.session.flush()
        await self.session.refresh(log)
        return log

    async def get_export_log(self, export_id: UUID, user_id: UUID) -> ExportLog | None:
        stmt = select(ExportLog).where(
            ExportLog.id == export_id,
            ExportLog.user_id == user_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_export_logs(
        self, user_id: UUID, limit: int = 10
    ) -> list[ExportLog]:
        stmt = (
            select(ExportLog)
            .where(ExportLog.user_id == user_id)
            .order_by(ExportLog.requested_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update_export_status(
        self, export_id: UUID, status: str, **kwargs
    ) -> ExportLog | None:
        stmt = select(ExportLog).where(ExportLog.id == export_id)
        result = await self.session.execute(stmt)
        log = result.scalar_one_or_none()
        if log is None:
            return None
        log.status = status
        for k, v in kwargs.items():
            if hasattr(log, k):
                setattr(log, k, v)
        await self.session.flush()
        await self.session.refresh(log)
        return log

    async def count_exports_last_hour(self, user_id: UUID) -> int:
        from sqlalchemy import text as sa_text

        stmt = select(func.count()).select_from(ExportLog).where(
            ExportLog.user_id == user_id,
            ExportLog.requested_at >= func.now() - sa_text("interval '1 hour'"),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()


__all__ = ["AbilityProfileRepository"]
