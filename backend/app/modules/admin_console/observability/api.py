"""REQ-061 US12 — admin AI task inspection endpoints (T161).

Mounted at ``/api/v1/admin-console/ai`` alongside Bad Case facade.
Existing REQ-044 observability routes remain on
``/api/v1/admin-console/observability`` via ``admin_console.api``.
"""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID, uuid4

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_id_optional as _resolve_user_id_from_jwt
from app.core.db import get_db_session_no_rls, set_rls_user_id
from app.modules.admin_console.auth import require_admin
from app.modules.admin_console.observability.schemas import (
    AttemptPage,
    AttemptSummary,
    DataQualityBlock,
    EvidenceReplayResponse,
    OperationalTaskDetail,
    OperationalTaskPage,
    OperationalTaskSummary,
    TimelineItem,
    TimelinePage,
)
from app.modules.auth.ai_capabilities import AIAdminCapability, has_ai_admin_capability

log = structlog.get_logger(__name__)

router = APIRouter()


async def _session() -> Any:
    async for s in get_db_session_no_rls():
        yield s


def _require_ops_read(roles: list[str] | None = None) -> None:
    roles = roles or ["admin"]
    if not has_ai_admin_capability(
        roles=roles, capability=AIAdminCapability.OPERATIONS_READ.value
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "type": "about:blank",
                "title": "Forbidden",
                "status": 403,
                "code": "missing_capability",
                "correlation_id": str(uuid4()),
                "detail": AIAdminCapability.OPERATIONS_READ.value,
            },
        )


def _task_links(task_id: UUID) -> dict[str, str]:
    base = f"/api/v1/admin-console/ai/tasks/{task_id}"
    return {
        "self": base,
        "timeline": f"{base}/timeline",
        "attempts": f"{base}/attempts",
        "evidence_replay": f"{base}/evidence-replay",
        "points": f"/api/v1/admin-console/ai/points?task_id={task_id}",
        "costs": f"/api/v1/admin-console/ai/costs?task_id={task_id}",
        "badcases": f"/api/v1/admin-console/ai/badcases?task_id={task_id}",
    }


def _quality_from_report(report: Any | None, *, available: bool = True) -> DataQualityBlock:
    if report is None:
        return DataQualityBlock(projection_available=available, complete=False)
    return DataQualityBlock(
        freshness_at=report.fresh_at,
        coverage=dict(report.coverage or {}),
        unknown_count=int(report.unknown_count or 0),
        stale=bool(report.stale),
        complete=bool(report.complete),
        projection_available=available,
    )


@router.get(
    "/tasks",
    response_model=OperationalTaskPage,
    responses={403: {"description": "Missing capability"}},
)
async def search_operational_tasks(
    _user_id: Annotated[UUID, Depends(_resolve_user_id_from_jwt)],
    _cap: Annotated[bool, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(_session)],
    task_id: UUID | None = None,
    user_id: UUID | None = None,
    capability: str | None = None,
    status_filter: str | None = Query(None, alias="status"),
    cursor: str | None = None,
    limit: int = Query(50, ge=1, le=200),
) -> OperationalTaskPage:
    """Search redacted operational AI task projections (cursor page)."""
    _require_ops_read()
    from app.modules.ai_runtime.projections.operational_task import (
        check_completeness,
        search_projections,
    )

    try:
        rows, next_cursor = await search_projections(
            session,
            task_id=task_id,
            user_id=user_id,
            capability=capability,
            status=status_filter,
            cursor=cursor,
            limit=limit,
        )
    except Exception as exc:  # noqa: BLE001 — soft degrade when tables missing
        log.warning("ai_inspection.task_search_unavailable", error=str(exc))
        return OperationalTaskPage(
            items=[],
            next_cursor=None,
            data_quality=DataQualityBlock(projection_available=False, complete=False),
        )

    items: list[OperationalTaskSummary] = []
    for row in rows:
        try:
            report = await check_completeness(session, row.task_id)
            dq = _quality_from_report(report)
        except Exception:  # noqa: BLE001
            dq = DataQualityBlock(projection_available=True, complete=False)
        denorm = row.denormalized or {}
        items.append(
            OperationalTaskSummary(
                task_id=row.task_id,
                user_id=row.user_id,
                root_task_id=row.root_task_id,
                status=row.status,
                capability_code=row.capability_code,
                action_code=row.action_code,
                user_summary=denorm.get("user_summary"),
                failure_category=denorm.get("failure_category"),
                available_actions=list(denorm.get("available_actions") or []),
                links=_task_links(row.task_id),
                data_quality=dq,
            )
        )
    return OperationalTaskPage(items=items, next_cursor=next_cursor)


@router.get(
    "/tasks/{task_id}",
    response_model=OperationalTaskDetail,
    responses={403: {"description": "Forbidden"}, 404: {"description": "Not found"}},
)
async def get_operational_task(
    task_id: UUID,
    _user_id: Annotated[UUID, Depends(_resolve_user_id_from_jwt)],
    _cap: Annotated[bool, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(_session)],
) -> OperationalTaskDetail:
    """Complete redacted operational view of one AI task."""
    _require_ops_read()
    from app.modules.ai_runtime.models import OperationalTaskProjection
    from app.modules.ai_runtime.projections.operational_task import check_completeness
    from app.modules.ai_runtime.repository import AIRuntimeRepository

    proj = await session.get(OperationalTaskProjection, task_id)
    repo = AIRuntimeRepository(session)
    task = await repo.get_task(task_id)
    if proj is None and task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "type": "about:blank",
                "title": "Not Found",
                "status": 404,
                "code": "task_not_found",
                "correlation_id": str(uuid4()),
            },
        )

    if task is not None:
        await set_rls_user_id(session, task.user_id)

    try:
        report = await check_completeness(session, task_id)
        dq = _quality_from_report(report, available=proj is not None)
    except Exception:  # noqa: BLE001
        dq = DataQualityBlock(projection_available=proj is not None, complete=False)

    source = proj or task
    denorm = (proj.denormalized if proj else {}) or {}
    return OperationalTaskDetail(
        task_id=task_id,
        user_id=source.user_id,
        root_task_id=getattr(source, "root_task_id", None) or task_id,
        status=source.status,
        capability_code=source.capability_code,
        action_code=source.action_code,
        task_version=getattr(task, "task_version", None) if task else denorm.get("task_version"),
        user_summary=denorm.get("user_summary") or getattr(task, "user_summary", None),
        failure_category=denorm.get("failure_category")
        or getattr(task, "failure_category", None),
        available_actions=list(
            denorm.get("available_actions")
            or getattr(task, "available_actions", None)
            or []
        ),
        denormalized=denorm,
        related={
            "points": [f"/api/v1/admin-console/ai/points?task_id={task_id}"],
            "costs": [f"/api/v1/admin-console/ai/costs?task_id={task_id}"],
            "badcases": [f"/api/v1/admin-console/ai/badcases?task_id={task_id}"],
        },
        links=_task_links(task_id),
        data_quality=dq,
    )


@router.get("/tasks/{task_id}/timeline", response_model=TimelinePage)
async def get_operational_task_timeline(
    task_id: UUID,
    _user_id: Annotated[UUID, Depends(_resolve_user_id_from_jwt)],
    _cap: Annotated[bool, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(_session)],
    kind: str | None = None,
    cursor: str | None = None,
    limit: int = Query(100, ge=1, le=200),
) -> TimelinePage:
    """Ordered causal timeline (task events; soft-paginated)."""
    _require_ops_read()
    from app.modules.ai_runtime.models import AITaskEvent
    from app.modules.ai_runtime.projections.operational_task import check_completeness
    from app.modules.ai_runtime.repository import AIRuntimeRepository

    repo = AIRuntimeRepository(session)
    task = await repo.get_task(task_id)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "type": "about:blank",
                "title": "Not Found",
                "status": 404,
                "code": "task_not_found",
                "correlation_id": str(uuid4()),
            },
        )
    await set_rls_user_id(session, task.user_id)

    q = (
        select(AITaskEvent)
        .where(AITaskEvent.task_id == task_id)
        .order_by(AITaskEvent.sequence.asc())
    )
    if kind and kind != "task_event":
        # Soft filter: other kinds reserved; return empty page with quality flag.
        return TimelinePage(
            task_id=task_id,
            items=[],
            next_cursor=None,
            data_quality=DataQualityBlock(complete=False, coverage={"kind_filter": False}),
        )
    if cursor:
        try:
            q = q.where(AITaskEvent.sequence > int(cursor))
        except ValueError:
            pass
    rows = (await session.execute(q.limit(limit + 1))).scalars().all()
    next_cursor = None
    if len(rows) > limit:
        rows = rows[:limit]
        next_cursor = str(rows[-1].sequence)
    items = [
        TimelineItem(
            kind="task_event",
            sequence=e.sequence,
            event_type=e.event_type,
            from_status=e.from_status,
            to_status=e.to_status,
            safe_message=e.safe_message,
            occurred_at=e.occurred_at,
            ref_id=str(e.id),
        )
        for e in rows
    ]
    try:
        report = await check_completeness(session, task_id)
        dq = _quality_from_report(report)
    except Exception:  # noqa: BLE001
        dq = DataQualityBlock(complete=False)
    return TimelinePage(task_id=task_id, items=items, next_cursor=next_cursor, data_quality=dq)


@router.get("/tasks/{task_id}/attempts", response_model=AttemptPage)
async def list_operational_attempts(
    task_id: UUID,
    _user_id: Annotated[UUID, Depends(_resolve_user_id_from_jwt)],
    _cap: Annotated[bool, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(_session)],
    attempt_kind: str | None = None,
    status_filter: str | None = Query(None, alias="status"),
    cursor: str | None = None,
    limit: int = Query(50, ge=1, le=200),
) -> AttemptPage:
    """List model/search/tool attempts with provider fields redacted."""
    _require_ops_read()
    from app.modules.ai_runtime.models import AIExternalAttempt
    from app.modules.ai_runtime.repository import AIRuntimeRepository

    repo = AIRuntimeRepository(session)
    task = await repo.get_task(task_id)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "type": "about:blank",
                "title": "Not Found",
                "status": 404,
                "code": "task_not_found",
                "correlation_id": str(uuid4()),
            },
        )
    await set_rls_user_id(session, task.user_id)

    q = (
        select(AIExternalAttempt)
        .where(AIExternalAttempt.task_id == task_id)
        .order_by(AIExternalAttempt.created_at.asc())
    )
    if attempt_kind:
        q = q.where(AIExternalAttempt.attempt_kind == attempt_kind)
    if status_filter:
        q = q.where(AIExternalAttempt.status == status_filter)
    if cursor:
        try:
            q = q.where(AIExternalAttempt.id > UUID(cursor))
        except ValueError:
            pass
    rows = (await session.execute(q.limit(limit + 1))).scalars().all()
    next_cursor = None
    if len(rows) > limit:
        rows = rows[:limit]
        next_cursor = str(rows[-1].id)
    items = [
        AttemptSummary(
            attempt_id=a.id,
            attempt_kind=getattr(a, "attempt_kind", None),
            status=a.status,
            provider_redacted=True,
            created_at=getattr(a, "created_at", None),
        )
        for a in rows
    ]
    return AttemptPage(
        task_id=task_id,
        items=items,
        next_cursor=next_cursor,
        data_quality=DataQualityBlock(complete=True, projection_available=True),
    )


@router.get("/tasks/{task_id}/evidence-replay", response_model=EvidenceReplayResponse)
async def replay_task_evidence(
    task_id: UUID,
    _user_id: Annotated[UUID, Depends(_resolve_user_id_from_jwt)],
    _cap: Annotated[bool, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(_session)],
) -> EvidenceReplayResponse:
    """Read-only evidence reconstruction — never mutates providers/tools/ledger."""
    _require_ops_read()
    from app.modules.ai_runtime.evidence_replay import EvidenceReplayService
    from app.modules.ai_runtime.repository import AIRuntimeRepository

    repo = AIRuntimeRepository(session)
    task = await repo.get_task(task_id)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "type": "about:blank",
                "title": "Not Found",
                "status": 404,
                "code": "task_not_found",
                "correlation_id": str(uuid4()),
            },
        )
    await set_rls_user_id(session, task.user_id)
    report = await EvidenceReplayService(session).replay(
        task_id=task_id, user_id=task.user_id
    )
    return EvidenceReplayResponse(
        task_id=task_id,
        complete=report.complete,
        missing_sequences=list(report.missing_sequences or []),
        event_count=len(report.events),
        provider_calls_created=0,
        tool_calls_created=0,
        ledger_events_created=0,
        reconstructed=True,
        read_only=True,
    )


__all__ = ["router"]
