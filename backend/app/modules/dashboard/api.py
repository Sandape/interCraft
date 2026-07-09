"""Dashboard summary API — GET /me/dashboard-summary (REQ-057)."""
from __future__ import annotations

from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import db_session_user_dep, get_current_user_id
from app.modules.dashboard.schemas import DashboardSummaryEnvelope
from app.modules.dashboard.service import DEFAULT_TZ, DashboardService

router = APIRouter(tags=["dashboard"])


def _validate_tz(tz: str) -> str:
    try:
        ZoneInfo(tz)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=f"invalid tz: {tz}") from exc
    return tz


@router.get("/me/dashboard-summary", response_model=DashboardSummaryEnvelope)
async def get_dashboard_summary(
    tz: str = Query(default=DEFAULT_TZ),
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(db_session_user_dep),
) -> dict:
    tz = _validate_tz(tz)
    summary = await DashboardService(db).get_summary(user_id, tz=tz)
    return {"data": summary}


__all__ = ["router"]
