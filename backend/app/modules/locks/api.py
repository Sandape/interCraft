"""M12 — Lock REST endpoints (T019).

POST /api/v1/locks/acquire — acquire a pessimistic lock
DELETE /api/v1/locks/{lock_id} — release a lock
GET /api/v1/locks/{resource_type}/{resource_id} — query lock status
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from app.api.deps import get_current_user_id
from app.modules.locks.schemas import (
    AcquireInput,
    LockStatus,
    ReleaseResponse,
)
from app.modules.locks.service import LockService

router = APIRouter(prefix="/locks", tags=["locks"])


@router.post(
    "/acquire",
    response_model=LockStatus,
    status_code=201,
    responses={
        201: {"description": "Lock acquired"},
        409: {"description": "Resource locked by another user"},
        422: {"description": "Invalid resource_type"},
    },
)
async def acquire_lock(
    body: AcquireInput,
    user_id: UUID = Depends(get_current_user_id),
):
    svc = LockService()
    result = await svc.acquire(
        user_id=str(user_id),
        device_id="",  # filled from X-Device-Fingerprint header in integration
        session_id="",  # filled from request state in integration
        input=body,
    )
    return JSONResponse(
        status_code=201,
        content=result.model_dump(mode="json"),
    )


@router.delete(
    "/{lock_id}",
    response_model=ReleaseResponse,
    responses={
        200: {"description": "Lock released"},
        403: {"description": "Not your lock"},
        404: {"description": "Lock not found"},
    },
)
async def release_lock(
    lock_id: str,
    user_id: UUID = Depends(get_current_user_id),
):
    svc = LockService()
    result = await svc.release(lock_id=lock_id, user_id=str(user_id))
    return result.model_dump(mode="json")


@router.post(
    "/{lock_id}/heartbeat",
    responses={
        200: {"description": "Heartbeat acknowledged"},
        403: {"description": "Not your lock"},
        404: {"description": "Lock not found"},
    },
)
async def heartbeat_lock(
    lock_id: str,
    user_id: UUID = Depends(get_current_user_id),
):
    svc = LockService()
    ok = await svc.heartbeat(lock_id=lock_id, user_id=str(user_id))
    return {"ok": ok, "lock_id": lock_id}


@router.get(
    "/{resource_type}/{resource_id}",
    response_model=LockStatus,
    responses={200: {"description": "Lock status"}},
)
async def get_lock_status(
    resource_type: str,
    resource_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
):
    svc = LockService()
    result = await svc.get_status(resource_type, str(resource_id))
    return result.model_dump(mode="json")
