"""Error questions REST API (M08) — 6 endpoints."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_id, db_session_user_dep
from app.core.db import get_db_session
from app.modules.errors.repository import ErrorQuestionRepository
from app.modules.errors.schemas import (
    CreateErrorQuestionInput,
    ErrorQuestionListOut,
    ErrorQuestionOut,
    PatchErrorQuestionInput,
)
from app.modules.errors.service import ErrorService

router = APIRouter(prefix="/error-questions", tags=["error-questions"])


def _get_service(session: AsyncSession = Depends(db_session_user_dep)) -> ErrorService:
    return ErrorService(ErrorQuestionRepository(session))


@router.get("", response_model=ErrorQuestionListOut)
async def list_questions(
    dimension: str | None = Query(default=None),
    status: str | None = Query(default=None),
    frequency_min: int = Query(default=0, ge=0, le=3),
    limit: int = Query(default=20, ge=1, le=50),
    user_id: UUID = Depends(get_current_user_id),
    svc: ErrorService = Depends(_get_service),
) -> dict:
    data = await svc.list(
        user_id, dimension=dimension, status=status,
        frequency_min=frequency_min, limit=limit,
    )
    return {"data": data, "next_cursor": None, "has_more": len(data) >= limit}


@router.post("", status_code=201, response_model=ErrorQuestionOut)
async def create_question(
    body: CreateErrorQuestionInput,
    user_id: UUID = Depends(get_current_user_id),
    svc: ErrorService = Depends(_get_service),
) -> ErrorQuestionOut:
    return await svc.create(user_id, body.model_dump())


@router.get("/{id}", response_model=ErrorQuestionOut)
async def get_question(
    id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    svc: ErrorService = Depends(_get_service),
) -> ErrorQuestionOut:
    return await svc.get(id, user_id)


@router.patch("/{id}", response_model=ErrorQuestionOut)
async def patch_question(
    id: UUID,
    body: PatchErrorQuestionInput,
    user_id: UUID = Depends(get_current_user_id),
    svc: ErrorService = Depends(_get_service),
) -> ErrorQuestionOut:
    return await svc.patch(id, user_id, body.model_dump(exclude_none=True))


@router.delete("/{id}", status_code=204, response_class=Response)
async def delete_question(
    id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    svc: ErrorService = Depends(_get_service),
) -> Response:
    await svc.delete(id, user_id)
    return Response(status_code=204)


@router.post("/{id}/reset", response_model=ErrorQuestionOut)
async def reset_question(
    id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    svc: ErrorService = Depends(_get_service),
) -> ErrorQuestionOut:
    return await svc.reset(id, user_id)


__all__ = ["router"]
