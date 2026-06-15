"""ActivityRepository — append-only with cursor pagination (DEC-P2-1)."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.pagination import decode_activity_cursor, encode_activity_cursor
from app.modules.activities.models import Activity


class ActivityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list(
        self, user_id: UUID, *, cursor: str | None = None, limit: int = 20,
    ) -> tuple[list[Activity], str | None, bool]:
        stmt = select(Activity).where(Activity.user_id == user_id)

        if cursor:
            cursor_ts, cursor_id = decode_activity_cursor(cursor)
            stmt = stmt.where(
                and_(
                    Activity.occurred_at <= cursor_ts,
                    Activity.id < cursor_id,
                )
            )

        stmt = stmt.order_by(Activity.occurred_at.desc(), Activity.id.desc()).limit(limit + 1)
        result = await self.session.execute(stmt)
        rows = list(result.scalars().all())

        has_more = len(rows) > limit
        if has_more:
            rows = rows[:limit]

        next_cursor: str | None = None
        if has_more and rows:
            last = rows[-1]
            next_cursor = encode_activity_cursor(last.occurred_at, last.id)

        return rows, next_cursor, has_more

    async def log(self, activity: Activity) -> Activity:
        self.session.add(activity)
        await self.session.flush()
        await self.session.refresh(activity)
        return activity


__all__ = ["ActivityRepository"]
