"""Global interview mutex helpers (REQ-054)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

ACTIVE_STATUSES = frozenset({"pending", "in_progress"})


async def has_active_session(
    session: AsyncSession,
    user_id: UUID,
) -> Any | None:
    """Return one active pending/in_progress InterviewSession or None."""
    from app.modules.interviews.repository import InterviewSessionRepository

    repo = InterviewSessionRepository(session)
    for status in ("in_progress", "pending"):
        rows = await repo.list(user_id, status=status, limit=5)
        for row in rows:
            if row.status in ACTIVE_STATUSES:
                return row
    return None


__all__ = ["ACTIVE_STATUSES", "has_active_session"]
