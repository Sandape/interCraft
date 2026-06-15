"""JobRepository — CRUD for jobs."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.jobs.models import Job


class JobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list(
        self, user_id: UUID, *, status: str | None = None,
        branch_id: UUID | None = None, limit: int = 20,
    ) -> list[Job]:
        stmt = select(Job).where(Job.user_id == user_id, Job.deleted_at.is_(None))
        if status:
            stmt = stmt.where(Job.status == status)
        if branch_id:
            stmt = stmt.where(Job.branch_id == branch_id)
        stmt = stmt.order_by(Job.status.asc(), Job.last_status_changed_at.desc()).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get(self, id: UUID, user_id: UUID) -> Job | None:
        stmt = select(Job).where(Job.id == id, Job.user_id == user_id, Job.deleted_at.is_(None))
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, job: Job) -> Job:
        self.session.add(job)
        await self.session.flush()
        await self.session.refresh(job)
        return job

    async def patch(self, id: UUID, user_id: UUID, data: dict) -> Job | None:
        job = await self.get(id, user_id)
        if job is None:
            return None
        for k, v in data.items():
            if hasattr(job, k) and v is not None:
                setattr(job, k, v)
        await self.session.flush()
        await self.session.refresh(job)
        return job

    async def soft_delete(self, id: UUID, user_id: UUID) -> bool:
        job = await self.get(id, user_id)
        if job is None:
            return False
        job.deleted_at = datetime.now(timezone.utc)
        await self.session.flush()
        return True

    async def stats(self, user_id: UUID) -> dict:
        stmt = (
            select(Job.status, func.count(Job.id))
            .where(Job.user_id == user_id, Job.deleted_at.is_(None))
            .group_by(Job.status)
        )
        result = await self.session.execute(stmt)
        rows = result.all()
        counts: dict[str, int] = {
            "applied": 0, "test": 0, "oa": 0, "hr": 0, "offer": 0,
            "rejected": 0, "withdrawn": 0,
        }
        total = 0
        for status, cnt in rows:
            counts[status] = cnt
            total += cnt
        return {"counts": counts, "total": total}


__all__ = ["JobRepository"]
