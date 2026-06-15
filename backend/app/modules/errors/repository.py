"""ErrorQuestionRepository — CRUD for error_questions."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.errors.models import ErrorQuestion


class ErrorQuestionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list(
        self,
        user_id: UUID,
        *,
        dimension: str | None = None,
        status: str | None = None,
        frequency_min: int = 0,
        limit: int = 20,
        order_by: str = "-created_at",
    ) -> list[ErrorQuestion]:
        stmt = select(ErrorQuestion).where(
            ErrorQuestion.user_id == user_id,
            ErrorQuestion.deleted_at.is_(None),
        )
        if dimension:
            stmt = stmt.where(ErrorQuestion.dimension == dimension)
        if status:
            stmt = stmt.where(ErrorQuestion.status == status)
        if frequency_min > 0:
            stmt = stmt.where(ErrorQuestion.frequency >= frequency_min)

        # Default sort: status ASC, frequency DESC, created_at DESC
        stmt = stmt.order_by(
            ErrorQuestion.status.asc(),
            ErrorQuestion.frequency.desc(),
            ErrorQuestion.created_at.desc(),
        ).limit(limit)

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get(self, id: UUID, user_id: UUID) -> ErrorQuestion | None:
        stmt = select(ErrorQuestion).where(
            ErrorQuestion.id == id,
            ErrorQuestion.user_id == user_id,
            ErrorQuestion.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, instance: ErrorQuestion) -> ErrorQuestion:
        self.session.add(instance)
        await self.session.flush()
        await self.session.refresh(instance)
        return instance

    async def patch(self, id: UUID, user_id: UUID, patch_data: dict) -> ErrorQuestion | None:
        instance = await self.get(id, user_id)
        if instance is None:
            return None
        for k, v in patch_data.items():
            if hasattr(instance, k) and v is not None:
                setattr(instance, k, v)
        await self.session.flush()
        await self.session.refresh(instance)
        return instance

    async def soft_delete(self, id: UUID, user_id: UUID) -> bool:
        instance = await self.get(id, user_id)
        if instance is None:
            return False
        instance.deleted_at = datetime.now(timezone.utc)
        await self.session.flush()
        return True

    async def reset(self, id: UUID, user_id: UUID) -> ErrorQuestion | None:
        instance = await self.get(id, user_id)
        if instance is None:
            return None
        instance.status = "fresh"
        instance.frequency = 3
        await self.session.flush()
        await self.session.refresh(instance)
        return instance


__all__ = ["ErrorQuestionRepository"]
