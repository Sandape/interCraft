"""ResumeVersion repository."""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.versions.models import ResumeVersion


class ResumeVersionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_for_branch(
        self, branch_id: UUID, *, limit: int = 50
    ) -> list[ResumeVersion]:
        stmt = (
            select(ResumeVersion)
            .where(ResumeVersion.branch_id == branch_id)
            .order_by(ResumeVersion.version_no.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_no(
        self, branch_id: UUID, version_no: int
    ) -> ResumeVersion | None:
        stmt = select(ResumeVersion).where(
            ResumeVersion.branch_id == branch_id,
            ResumeVersion.version_no == version_no,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id(self, version_id: UUID) -> ResumeVersion | None:
        stmt = select(ResumeVersion).where(ResumeVersion.id == version_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def next_version_no(self, branch_id: UUID) -> int:
        stmt = select(func.coalesce(func.max(ResumeVersion.version_no), 0)).where(
            ResumeVersion.branch_id == branch_id
        )
        result = await self.session.execute(stmt)
        return int(result.scalar() or 0) + 1

    async def create_full_snapshot(
        self,
        *,
        user_id: UUID,
        branch_id: UUID,
        version_no: int,
        snapshot: dict,
        label: str | None = None,
        trigger: str = "manual",
        author_type: str = "user",
        actor_id: UUID | None = None,
    ) -> ResumeVersion:
        v = ResumeVersion(
            user_id=user_id,
            branch_id=branch_id,
            version_no=version_no,
            label=label,
            is_full_snapshot=True,
            snapshot_json=snapshot,
            trigger=trigger,
            author_type=author_type,
            actor_id=actor_id,
        )
        self.session.add(v)
        await self.session.flush()
        await self.session.refresh(v)
        return v


__all__ = ["ResumeVersionRepository"]
