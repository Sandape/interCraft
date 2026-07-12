"""REQ-061 AI Metering user API (T051).

Owner-scoped account, ledger, export stub, budget, and task deep-links per
``contracts/ai-metering.openapi.yaml`` (mounted under ``/api/v1``).
"""

from __future__ import annotations

import base64
import json
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import db_session_user_dep, get_current_user_id
from app.core.ids import new_uuid_v7
from app.modules.account.beta_entitlement import get_beta_entitlement
from app.modules.ai_metering.models import (
    DailyGrantConfigVersion,
    PointBucket,
    PointLedgerEvent,
)
from app.modules.ai_metering.points.catalog import INITIAL_DAILY_GRANT_POINTS
from app.modules.ai_metering.points.configuration import (
    resolve_effective_grant_config,
    shanghai_business_date,
)
from app.modules.ai_metering.repository import PointMeteringRepository
from app.modules.ai_metering.schemas import (
    ExportJobOut,
    ExportLedgerRequest,
    LedgerEntryOut,
    LedgerPageOut,
    PointAccountOut,
    PointBudgetOut,
    PointBucketOut,
    Problem,
    UpdateBudgetRequest,
)

router = APIRouter(tags=["ai-points"])

DEFAULT_RISK_LIMIT = 10_000
MAX_EXPORT_WINDOW = timedelta(days=365 * 2)
EXPORT_JOB_TTL = timedelta(hours=24)


def _problem(
    *,
    status_code: int,
    code: str,
    title: str,
    detail: str | None = None,
    correlation_id: str | None = None,
) -> JSONResponse:
    body = Problem(
        type=f"https://intercraft.local/problems/{code.lower()}",
        title=title,
        status=status_code,
        code=code,
        correlation_id=correlation_id or str(new_uuid_v7()),
        detail=detail,
    )
    return JSONResponse(status_code=status_code, content=body.model_dump(mode="json"))


def _encode_cursor(recorded_at: datetime, event_id: UUID) -> str:
    raw = json.dumps(
        {"recorded_at": recorded_at.isoformat(), "event_id": str(event_id)}
    )
    return base64.urlsafe_b64encode(raw.encode()).decode()


def _decode_cursor(cursor: str) -> tuple[datetime, UUID]:
    raw = json.loads(base64.urlsafe_b64decode(cursor.encode()).decode())
    return datetime.fromisoformat(raw["recorded_at"]), UUID(raw["event_id"])


def _budget_version(account) -> int:
    return max(1, int(account.projection_sequence or 0))


async def _grant_config_label(
    session: AsyncSession, version_id: UUID | None
) -> str | None:
    if version_id is None:
        return None
    row = await session.get(DailyGrantConfigVersion, version_id)
    return row.version if row else None


@router.get("/ai-points/account", response_model=PointAccountOut)
async def get_ai_point_account(
    session: Annotated[AsyncSession, Depends(db_session_user_dep)],
    user_id: Annotated[UUID, Depends(get_current_user_id)],
) -> PointAccountOut:
    entitlement = get_beta_entitlement()
    repo = PointMeteringRepository(session)
    account = await repo.get_or_create_account(user_id)
    buckets = await repo.list_buckets_for_user(user_id)
    now = datetime.now(timezone.utc)
    active = [
        b
        for b in buckets
        if b.status == "active" and b.expires_at > now
    ]
    cfg = resolve_effective_grant_config(at=now)

    bucket_outs: list[PointBucketOut] = []
    next_expiry: datetime | None = None
    for bucket in active:
        if next_expiry is None or bucket.expires_at < next_expiry:
            next_expiry = bucket.expires_at
        grant_ver = await _grant_config_label(session, bucket.grant_config_version_id)
        btype = bucket.bucket_type
        if btype not in {"daily_experience", "compensation"}:
            btype = "daily_experience"
        bucket_outs.append(
            PointBucketOut(
                bucket_id=bucket.id,
                bucket_type=btype,  # type: ignore[arg-type]
                available=bucket.available_points,
                reserved=bucket.reserved_points,
                expires_at=bucket.expires_at,
                business_date=bucket.business_date,
                grant_config_version=grant_ver,
            )
        )

    await session.commit()
    return PointAccountOut(
        plan_label=entitlement.plan_label,  # type: ignore[arg-type]
        experience_badge=entitlement.experience_badge,  # type: ignore[arg-type]
        is_paid=False,
        business_date=shanghai_business_date(now),
        timezone="Asia/Shanghai",
        available=account.available_points,
        reserved=account.reserved_points,
        buckets=bucket_outs,
        next_expiry=next_expiry,
        daily_grant_amount=cfg.points_amount or INITIAL_DAILY_GRANT_POINTS,
        grant_config_version=cfg.version,
        parallel_ai_task_limit=entitlement.parallel_ai_task_limit,  # type: ignore[arg-type]
        history_days=entitlement.history_days,  # type: ignore[arg-type]
    )


@router.get("/ai-points/ledger", response_model=LedgerPageOut)
async def list_ai_point_ledger(
    session: Annotated[AsyncSession, Depends(db_session_user_dep)],
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    event_type: Annotated[str | None, Query()] = None,
    task_id: Annotated[UUID | None, Query()] = None,
    from_: Annotated[datetime | None, Query(alias="from")] = None,
    to: Annotated[datetime | None, Query()] = None,
    cursor: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> LedgerPageOut:
    filters = [PointLedgerEvent.user_id == user_id]
    if event_type:
        filters.append(PointLedgerEvent.event_type == event_type)
    if task_id:
        filters.append(PointLedgerEvent.task_id == task_id)
    if from_ is not None:
        filters.append(PointLedgerEvent.occurred_at >= from_)
    if to is not None:
        filters.append(PointLedgerEvent.occurred_at <= to)
    if cursor:
        try:
            cursor_at, cursor_id = _decode_cursor(cursor)
        except Exception as exc:
            raise HTTPException(
                status_code=400, detail="Invalid ledger cursor"
            ) from exc
        filters.append(
            (PointLedgerEvent.recorded_at < cursor_at)
            | (
                (PointLedgerEvent.recorded_at == cursor_at)
                & (PointLedgerEvent.id < cursor_id)
            )
        )

    result = await session.execute(
        select(PointLedgerEvent)
        .where(and_(*filters))
        .order_by(
            PointLedgerEvent.recorded_at.desc(),
            PointLedgerEvent.id.desc(),
        )
        .limit(limit + 1)
    )
    rows = list(result.scalars().all())
    next_cursor = None
    if len(rows) > limit:
        last = rows[limit - 1]
        next_cursor = _encode_cursor(last.recorded_at, last.id)
        rows = rows[:limit]

    items: list[LedgerEntryOut] = []
    for event in rows:
        payload: dict[str, Any] = event.payload or {}
        items.append(
            LedgerEntryOut(
                event_id=event.id,
                event_type=event.event_type,  # type: ignore[arg-type]
                occurred_at=event.occurred_at,
                recorded_at=event.recorded_at,
                available_delta=event.available_delta,
                reserved_delta=event.reserved_delta,
                available_after=event.after_available,
                reserved_after=event.after_reserved,
                reason=event.reason or event.event_type,
                task_id=event.task_id,
                execution_id=event.execution_id,
                milestone_code=payload.get("milestone_code"),
                capability=payload.get("capability"),
                service_tier=payload.get("service_tier"),
                expires_at=event.expiry_at,
            )
        )
    return LedgerPageOut(items=items, next_cursor=next_cursor)


@router.post(
    "/ai-points/ledger/export",
    response_model=ExportJobOut,
    status_code=status.HTTP_202_ACCEPTED,
)
async def export_ai_point_ledger(
    body: ExportLedgerRequest,
    session: Annotated[AsyncSession, Depends(db_session_user_dep)],
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
) -> ExportJobOut | JSONResponse:
    _ = (session, user_id, idempotency_key)
    start = body.from_
    end = body.to
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    if end < start:
        return _problem(
            status_code=400,
            code="INVALID_EXPORT_WINDOW",
            title="Export window end must be after start",
        )
    if end - start > MAX_EXPORT_WINDOW:
        return _problem(
            status_code=400,
            code="EXPORT_WINDOW_TOO_LARGE",
            title="Export window may cover at most 24 months",
            detail="from/to span exceeds 24 months",
        )

    now = datetime.now(timezone.utc)
    # Stub job acceptance — durable export worker lands in a later task.
    return ExportJobOut(
        export_id=new_uuid_v7(),
        status="queued",
        created_at=now,
        expires_at=now + EXPORT_JOB_TTL,
    )


@router.get("/ai-points/budget", response_model=PointBudgetOut)
async def get_ai_point_budget(
    session: Annotated[AsyncSession, Depends(db_session_user_dep)],
    user_id: Annotated[UUID, Depends(get_current_user_id)],
) -> PointBudgetOut:
    repo = PointMeteringRepository(session)
    account = await repo.get_or_create_account(user_id)
    biz = shanghai_business_date()
    consumed_result = await session.execute(
        select(func.coalesce(func.sum(PointBucket.consumed_points), 0)).where(
            PointBucket.user_id == user_id,
            PointBucket.business_date == biz,
        )
    )
    consumed_today = int(consumed_result.scalar_one() or 0)
    risk_limit = account.risk_consumption_limit or DEFAULT_RISK_LIMIT
    daily_limit = (
        account.daily_budget_points
        if account.daily_budget_points is not None
        else max(account.available_points, INITIAL_DAILY_GRANT_POINTS)
    )
    effective = min(daily_limit, account.available_points, risk_limit)
    await session.commit()
    return PointBudgetOut(
        daily_limit=daily_limit,
        consumed_today=consumed_today,
        available=account.available_points,
        risk_limit=risk_limit,
        effective_limit=max(0, effective),
        version=_budget_version(account),
    )


@router.patch("/ai-points/budget", response_model=PointBudgetOut)
async def update_ai_point_budget(
    body: UpdateBudgetRequest,
    session: Annotated[AsyncSession, Depends(db_session_user_dep)],
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
) -> PointBudgetOut | JSONResponse:
    _ = idempotency_key
    repo = PointMeteringRepository(session)
    account = await repo.get_or_create_account(user_id)
    current_version = _budget_version(account)
    if body.expected_version != current_version:
        return _problem(
            status_code=409,
            code="BUDGET_VERSION_CONFLICT",
            title="Budget version conflict",
            detail=f"expected {body.expected_version}, current {current_version}",
        )

    risk_limit = account.risk_consumption_limit or DEFAULT_RISK_LIMIT
    capped = min(body.daily_limit, max(account.available_points, 0), risk_limit)
    account.daily_budget_points = capped
    account.projection_sequence = int(account.projection_sequence or 0) + 1
    account.updated_at = datetime.now(timezone.utc)
    await session.flush()

    biz = shanghai_business_date()
    consumed_result = await session.execute(
        select(func.coalesce(func.sum(PointBucket.consumed_points), 0)).where(
            PointBucket.user_id == user_id,
            PointBucket.business_date == biz,
        )
    )
    consumed_today = int(consumed_result.scalar_one() or 0)
    effective = min(capped, account.available_points, risk_limit)
    await session.commit()
    return PointBudgetOut(
        daily_limit=capped,
        consumed_today=consumed_today,
        available=account.available_points,
        risk_limit=risk_limit,
        effective_limit=max(0, effective),
        version=_budget_version(account),
    )


__all__ = ["router"]
