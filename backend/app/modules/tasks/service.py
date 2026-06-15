"""TaskService — CRUD + idempotent find_or_create."""
from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.activities.repository import ActivityRepository
from app.modules.tasks.repository import TaskRepository


class TaskService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = TaskRepository(session)
        self.activity_repo = ActivityRepository(session)

    async def list(self, user_id: UUID, **filters) -> list:
        return await self.repo.list(user_id, **filters)

    async def get(self, id: UUID, user_id: UUID) -> dict:
        task = await self.repo.get(id, user_id)
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")
        return task

    async def create(self, user_id: UUID, data: dict) -> dict:
        from app.modules.tasks.models import Task

        task = Task(
            user_id=user_id,
            type=data.get("type", "manual"),
            title=data["title"],
            description_md=data.get("description_md"),
            related_entity_type=data.get("related_entity_type"),
            related_entity_id=data.get("related_entity_id"),
            due_at=data.get("due_at"),
            auto_generated=data.get("auto_generated", False),
        )
        task = await self.repo.create(task)
        await self._log(user_id, "task_created", {"task_id": str(task.id), "title": task.title})
        return task

    async def patch(self, id: UUID, user_id: UUID, data: dict) -> dict:
        task = await self.get(id, user_id)
        result = await self.repo.patch(id, user_id, data)
        if result is None:
            raise HTTPException(status_code=404, detail="Task not found")
        if data.get("status") == "done":
            await self._log(user_id, "task_completed", {"task_id": str(id), "title": result.title})
        return result

    async def delete(self, id: UUID, user_id: UUID) -> None:
        ok = await self.repo.soft_delete(id, user_id)
        if not ok:
            raise HTTPException(status_code=404, detail="Task not found")

    async def find_or_create(
        self, user_id: UUID, type: str, title: str,
        related_entity_type: str | None = None,
        related_entity_id: UUID | None = None,
    ) -> dict:
        task = await self.repo.find_or_create(
            user_id, type, title,
            related_entity_type=related_entity_type,
            related_entity_id=related_entity_id,
        )
        return task

    async def _log(self, user_id: UUID, type: str, payload: dict) -> None:
        from app.modules.activities.models import Activity
        activity = Activity(user_id=user_id, type=type, actor_type="system", payload_json=payload)
        await self.activity_repo.log(activity)


__all__ = ["TaskService"]
