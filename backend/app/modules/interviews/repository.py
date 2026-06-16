"""InterviewSessionRepository — Phase 4 full CRUD."""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.interviews.models import InterviewSession


class InterviewSessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list(self, user_id: UUID, *, status: str | None = None, limit: int = 50) -> list[InterviewSession]:
        stmt = select(InterviewSession).where(
            InterviewSession.user_id == user_id, InterviewSession.deleted_at.is_(None)
        )
        if status:
            stmt = stmt.where(InterviewSession.status == status)
        stmt = stmt.order_by(InterviewSession.started_at.desc().nulls_last()).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get(self, id: UUID, user_id: UUID) -> InterviewSession | None:
        stmt = select(InterviewSession).where(
            InterviewSession.id == id,
            InterviewSession.user_id == user_id,
            InterviewSession.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(
        self,
        user_id: UUID,
        position: str,
        company: str,
        branch_id: UUID | None = None,
        mode: str = "text",
        job_id: UUID | None = None,
    ) -> InterviewSession:
        session = InterviewSession(
            id=uuid4(),
            user_id=user_id,
            position=position,
            company=company,
            branch_id=branch_id,
            mode=mode,
            job_id=job_id,
            status="pending",
        )
        self.session.add(session)
        await self.session.flush()
        return session

    async def update_status(
        self,
        id: UUID,
        status: str,
        *,
        thread_id: str | None = None,
        started_at: datetime | None = None,
        ended_at: datetime | None = None,
        duration_sec: int | None = None,
        overall_score: float | None = None,
    ) -> None:
        values = {"status": status, "updated_at": datetime.now(UTC)}
        if thread_id is not None:
            values["thread_id"] = thread_id
        if started_at is not None:
            values["started_at"] = started_at
        if ended_at is not None:
            values["ended_at"] = ended_at
        if duration_sec is not None:
            values["duration_sec"] = duration_sec
        if overall_score is not None:
            values["overall_score"] = overall_score

        await self.session.execute(
            update(InterviewSession).where(InterviewSession.id == id).values(**values)
        )
        await self.session.flush()

    async def soft_delete(self, id: UUID, user_id: UUID) -> bool:
        now = datetime.now(UTC)
        result = await self.session.execute(
            update(InterviewSession)
            .where(
                InterviewSession.id == id,
                InterviewSession.user_id == user_id,
                InterviewSession.deleted_at.is_(None),
            )
            .values(deleted_at=now, updated_at=now)
        )
        await self.session.flush()
        return result.rowcount > 0


__all__ = ["InterviewSessionRepository"]
