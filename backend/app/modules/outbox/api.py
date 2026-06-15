"""M13 — Outbox REST endpoints (T028).

POST /api/v1/outbox/replay — batch replay offline writes
GET /api/v1/outbox/status — server-side outbox health
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.api.deps import get_current_user_id
from app.core.exceptions import ValidationError
from app.modules.outbox.schemas import (
    OutboxStatusResponse,
    ReplayInput,
    ReplayResponse,
)
from app.modules.outbox.service import OutboxService

router = APIRouter(prefix="/outbox", tags=["outbox"])


@router.post(
    "/replay",
    response_model=ReplayResponse,
    responses={
        200: {"description": "Batch replay processed"},
        422: {"description": "Too many entries or invalid entity_type"},
    },
)
async def replay_entries(
    body: ReplayInput,
    user_id: UUID = Depends(get_current_user_id),
):
    if len(body.entries) > 30:
        raise ValidationError(
            code="outbox.too_many_entries",
            message=f"单次最多回放 30 条,收到 {len(body.entries)} 条",
            details={"limit": 30},
        )
    svc = OutboxService()
    result = await svc.replay_batch(body, str(user_id))
    return result.model_dump(mode="json")


@router.get(
    "/status",
    response_model=OutboxStatusResponse,
    responses={200: {"description": "Outbox health status"}},
)
async def get_outbox_status(user_id: UUID = Depends(get_current_user_id)):
    return OutboxStatusResponse(
        status="healthy",
        recent_replays={"last_hour": 0, "conflict_rate": 0.0},
    ).model_dump(mode="json")
