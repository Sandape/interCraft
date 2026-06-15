"""Tasks API (M10) — 6 endpoints."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_id, db_session_user_dep
from app.core.db import get_db_session
from app.modules.tasks.schemas import (
    CreateTaskInput, FindOrCreateInput, PatchTaskInput, TaskListOut, TaskOut,
)
from app.modules.tasks.service import TaskService

router = APIRouter(prefix="/tasks", tags=["tasks"])


async def _get_service(session: AsyncSession = Depends(db_session_user_dep)) -> TaskService:
    return TaskService(session)


@router.get("", response_model=TaskListOut)
async def list_tasks(
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=50),
    user_id: UUID = Depends(get_current_user_id),
    svc: TaskService = Depends(_get_service),
) -> dict:
    data = await svc.list(user_id, status=status, limit=limit)
    return {"data": data}


@router.post("", status_code=201, response_model=TaskOut)
async def create_task(
    body: CreateTaskInput,
    user_id: UUID = Depends(get_current_user_id),
    svc: TaskService = Depends(_get_service),
) -> TaskOut:
    return await svc.create(user_id, body.model_dump(exclude_none=True))


@router.get("/{id}", response_model=TaskOut)
async def get_task(
    id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    svc: TaskService = Depends(_get_service),
) -> TaskOut:
    return await svc.get(id, user_id)


@router.patch("/{id}", response_model=TaskOut)
async def patch_task(
    id: UUID, body: PatchTaskInput,
    user_id: UUID = Depends(get_current_user_id),
    svc: TaskService = Depends(_get_service),
) -> TaskOut:
    return await svc.patch(id, user_id, body.model_dump(exclude_none=True))


@router.delete("/{id}", status_code=204, response_class=Response)
async def delete_task(
    id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    svc: TaskService = Depends(_get_service),
) -> Response:
    await svc.delete(id, user_id)
    return Response(status_code=204)


__all__ = ["router"]
