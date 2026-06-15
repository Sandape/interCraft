"""ActivityService — cursor-based listing + logging."""
from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.activities.repository import ActivityRepository


class ActivityService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = ActivityRepository(session)

    async def list(
        self, user_id: UUID, *, cursor: str | None = None, limit: int = 20,
    ) -> tuple[list, str | None, bool]:
        return await self.repo.list(user_id, cursor=cursor, limit=limit)

    async def log(self, activity_data: dict) -> dict:
        from app.modules.activities.models import Activity
        activity = Activity(**activity_data)
        result = await self.repo.log(activity)
        return result


__all__ = ["ActivityService"]
