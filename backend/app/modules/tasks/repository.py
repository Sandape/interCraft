"""TaskRepository — CRUD for tasks with find_or_create."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.tasks.models import Task


class TaskRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list(self, user_id: UUID, *, status: str | None = None, limit: int = 50) -> list[Task]:
        stmt = select(Task).where(Task.user_id == user_id, Task.deleted_at.is_(None))
        if status:
            stmt = stmt.where(Task.status == status)
        stmt = stmt.order_by(Task.status.asc(), Task.due_at.asc().nulls_last()).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get(self, id: UUID, user_id: UUID) -> Task | None:
        stmt = select(Task).where(Task.id == id, Task.user_id == user_id, Task.deleted_at.is_(None))
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, task: Task) -> Task:
        self.session.add(task)
        await self.session.flush()
        await self.session.refresh(task)
        return task

    async def patch(self, id: UUID, user_id: UUID, data: dict) -> Task | None:
        task = await self.get(id, user_id)
        if task is None:
            return None
        for k, v in data.items():
            if hasattr(task, k) and v is not None:
                setattr(task, k, v)
        if "status" in data and data["status"] == "done":
            task.completed_at = datetime.now(timezone.utc)
        await self.session.flush()
        await self.session.refresh(task)
        return task

    async def soft_delete(self, id: UUID, user_id: UUID) -> bool:
        task = await self.get(id, user_id)
        if task is None:
            return False
        task.deleted_at = datetime.now(timezone.utc)
        await self.session.flush()
        return True

    async def find_by_entity(
        self, user_id: UUID, type: str, related_entity_id: UUID
    ) -> Task | None:
        stmt = select(Task).where(
            Task.user_id == user_id,
            Task.type == type,
            Task.related_entity_id == related_entity_id,
            Task.deleted_at.is_(None),
        ).limit(1)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def find_or_create(
        self, user_id: UUID, type: str, title: str,
        related_entity_type: str | None = None,
        related_entity_id: UUID | None = None,
    ) -> Task:
        """Idempotent find-or-create (DEC-P2-3)."""
        if related_entity_id:
            existing = await self.find_by_entity(user_id, type, related_entity_id)
            if existing:
                return existing
        task = Task(
            user_id=user_id, type=type, title=title,
            related_entity_type=related_entity_type,
            related_entity_id=related_entity_id,
            auto_generated=True,
        )
        try:
            return await self.create(task)
        except IntegrityError:
            await self.session.rollback()
            if related_entity_id:
                existing = await self.find_by_entity(user_id, type, related_entity_id)
                if existing:
                    return existing
            raise


__all__ = ["TaskRepository"]
