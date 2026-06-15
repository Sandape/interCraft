"""Activities API (M10) — 1 public endpoint (cursor-paginated)."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_id, db_session_user_dep
from app.core.db import get_db_session
from app.modules.activities.schemas import ActivityListOut
from app.modules.activities.service import ActivityService

router = APIRouter(prefix="/activities", tags=["activities"])


async def _get_service(session: AsyncSession = Depends(db_session_user_dep)) -> ActivityService:
    return ActivityService(session)


@router.get("", response_model=ActivityListOut)
async def list_activities(
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=50),
    user_id: UUID = Depends(get_current_user_id),
    svc: ActivityService = Depends(_get_service),
) -> dict:
    try:
        items, next_cursor, has_more = await svc.list(user_id, cursor=cursor, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"items": items, "next_cursor": next_cursor, "has_more": has_more}


__all__ = ["router"]
