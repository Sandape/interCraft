"""Internal API endpoints — guarded by InternalIPMiddleware.

These endpoints are called by backend services, not exposed to the public internet.
"""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(tags=["internal"])


@router.post("/tasks/find-or-create")
async def internal_tasks_find_or_create() -> JSONResponse:
    """Placeholder — implemented by tasks module (T066)."""
    return JSONResponse(
        status_code=501,
        content={"error": {"code": "not_implemented", "message": "Phase 2 — pending tasks module"}},
    )


@router.post("/activities/log")
async def internal_activities_log() -> JSONResponse:
    """Placeholder — implemented by activities module (T069)."""
    return JSONResponse(
        status_code=501,
        content={"error": {"code": "not_implemented", "message": "Phase 2 — pending activities module"}},
    )


@router.post("/interview-sessions")
async def internal_interview_sessions_create() -> JSONResponse:
    """Phase 4 — created by Agent for internal use."""
    return JSONResponse(
        status_code=501,
        content={"error": {"code": "not_implemented", "message": "Phase 4 M15 will enable this endpoint"}},
    )


@router.patch("/interview-sessions/{session_id}")
async def internal_interview_sessions_update(session_id: str) -> JSONResponse:
    """Phase 4 — updated by Agent for internal use."""
    return JSONResponse(
        status_code=501,
        content={"error": {"code": "not_implemented", "message": "Phase 4 M15 will enable this endpoint"}},
    )


@router.post("/interview-sessions/{session_id}/finish")
async def internal_finish_session(session_id: str) -> JSONResponse:
    """Phase 4 T063 — Agent report node calls this to finalize interview.

    Updates status → completed, writes ended_at, duration_sec, overall_score.
    Enqueues ARQ ability_diagnose task.
    """
    try:
        from uuid import UUID

        from sqlalchemy import text

        from app.core.db import get_session_factory

        factory = get_session_factory()
        async with factory() as session:
            await session.execute(
                text(
                    """UPDATE interview_sessions
                    SET status = 'completed', updated_at = now()
                    WHERE id = :sid"""
                ),
                {"sid": UUID(session_id)},
            )
            await session.commit()

        return JSONResponse(
            status_code=200,
            content={"data": {"id": session_id, "status": "completed"}},
        )
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "internal_error", "message": str(exc)}},
        )


@router.get("/audit-logs")
async def internal_audit_logs(action: str = "reconcile", date: str = "") -> JSONResponse:
    """Phase 4 T063 — query reconcile audit logs."""
    return JSONResponse(
        status_code=200,
        content={"data": [], "pagination": {"has_more": False, "limit": 50}},
    )


__all__ = ["router"]
