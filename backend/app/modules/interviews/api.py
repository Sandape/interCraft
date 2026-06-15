"""Interview sessions API — Phase 4 full CRUD (T030).

Phase 2: GET list/get only.
Phase 4: POST create/start/answers, GET report, cursor pagination.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import db_session_user_dep, get_current_user_id
from app.modules.interviews.schemas import (
    InterviewSessionCreate,
    InterviewSessionCreateOut,
    InterviewSessionListOut,
    InterviewSessionOut,
)
from app.modules.interviews.service import InterviewSessionService

router = APIRouter(prefix="/interview-sessions", tags=["interview-sessions"])


async def _get_service(session: AsyncSession = Depends(db_session_user_dep)) -> InterviewSessionService:
    return InterviewSessionService(session)


# ---- Phase 2: list / get (unchanged core) ----

@router.get("", response_model=InterviewSessionListOut)
async def list_sessions(
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=50),
    user_id: UUID = Depends(get_current_user_id),
    svc: InterviewSessionService = Depends(_get_service),
) -> dict:
    data = await svc.list(user_id, status=status, limit=limit)
    return {"data": data}


@router.get("/{id}", response_model=InterviewSessionOut)
async def get_session(
    id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    svc: InterviewSessionService = Depends(_get_service),
) -> InterviewSessionOut:
    return await svc.get(id, user_id)


# ---- Phase 4: create ----

@router.post("", response_model=InterviewSessionCreateOut, status_code=201)
async def create_session(
    body: InterviewSessionCreate,
    user_id: UUID = Depends(get_current_user_id),
    svc: InterviewSessionService = Depends(_get_service),
) -> dict:
    """Create an interview session and initialize LangGraph thread."""
    result = await svc.create(user_id, body)
    return {"data": result}


# ---- Phase 4: start ----

@router.post("/{id}/start", status_code=202)
async def start_session(
    id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    svc: InterviewSessionService = Depends(_get_service),
) -> dict:
    """Start the interview, triggering LangGraph intake node."""
    result = await svc.start(id, user_id)
    return {"data": result}


# ---- Phase 4: report ----

@router.get("/{id}/report")
async def get_report(
    id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    svc: InterviewSessionService = Depends(_get_service),
) -> dict:
    """Get the interview report for a completed session."""
    report = await svc.get_report(id, user_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found or interview not completed")
    return {"data": report}


# ---- Phase 4: submit answer ----

@router.post("/{id}/answers", status_code=200)
async def submit_answer(
    id: UUID,
    body: dict,
    user_id: UUID = Depends(get_current_user_id),
    svc: InterviewSessionService = Depends(_get_service),
) -> dict:
    """Submit an answer for the current interview question."""
    answer = body.get("content", "")
    sequence_no = body.get("sequence_no", 0)
    result = await svc.submit_answer(id, user_id, answer, sequence_no)
    return {"data": result}


# ---- Phase 4: resume (US2) ----

@router.get("/{id}/resume")
async def resume_session(
    id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    svc: InterviewSessionService = Depends(_get_service),
) -> dict:
    """Get resume information for an in-progress interview."""
    result = await svc.resume(id, user_id)
    return {"data": result}


# ---- soft delete ----

@router.delete("/{id}", status_code=204)
async def delete_session(
    id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    svc: InterviewSessionService = Depends(_get_service),
) -> Response:
    """Soft-delete an interview session (any status). Sets deleted_at."""
    await svc.delete(id, user_id)
    return Response(status_code=204)


__all__ = ["router"]
