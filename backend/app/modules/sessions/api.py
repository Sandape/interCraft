"""M05 — sessions API."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import db_session_user_dep, get_current_user_id
from app.core.exceptions import AppError
from app.modules.sessions.schemas import DeviceSession, SessionsListResponse
from app.modules.sessions.service import SessionService

router = APIRouter()


@router.get("", response_model=SessionsListResponse)
async def list_sessions(
    request: Request,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(db_session_user_dep),
):
    svc = SessionService(db)
    current_sid = getattr(request.state, "session_id", None)
    rows = await svc.repo.list_active(user_id)
    return SessionsListResponse(
        sessions=[
            DeviceSession(
                id=str(s.id),
                device_id=s.device_id,
                device_name=s.device_name,
                device_fingerprint=s.device_fingerprint,
                last_seen_at=s.last_seen_at,
                last_seen_ip=str(s.last_seen_ip) if s.last_seen_ip else None,
                last_seen_ua=s.last_seen_ua,
                trusted_at=s.trusted_at,
                created_at=s.created_at,
                is_current=(current_sid is not None and str(s.id) == str(current_sid)),
            )
            for s in rows
        ]
    )


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_session(
    session_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(db_session_user_dep),
):
    svc = SessionService(db)
    await svc.revoke_session(session_id, user_id=user_id)
    return None


@router.post("/{session_id}/trust", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def trust_session(session_id: UUID):
    """Phase 1 placeholder — `trusted_at` field exists; v1.1 wires this up."""
    raise AppError(
        "not_implemented",
        "设备信任标记将在 v1.1 启用",
        http_status=501,
    )
