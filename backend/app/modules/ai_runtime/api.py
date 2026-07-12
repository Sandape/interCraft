"""REQ-061 AI Runtime user API (T029/T030)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import db_session_user_dep, get_current_user_id
from app.core.ids import new_uuid_v7
from app.modules.ai_runtime.acceptance import AcceptanceError, AcceptanceService
from app.modules.ai_runtime.control import ControlError, ControlService
from app.modules.ai_runtime.evidence_replay import EvidenceReplayService, ReplayChoice
from app.modules.ai_runtime.models import AIExecution, AIMilestone, AITask, AITaskEvent
from app.modules.ai_runtime.schemas import (
    AcceptTaskRequest,
    CapabilityCatalogOut,
    ExecutionRef,
    MilestoneOut,
    PointSummary,
    Problem,
    QuoteRequest,
    ReexecutionRequest,
    ResumeRequest,
    Stage,
    TaskActionRequest,
    TaskDetail,
    TaskEventOut,
    TaskPage,
    TaskSummary,
)
from app.modules.ai_runtime.state_machine import TERMINAL_STATUSES, TaskStatus
from app.modules.ai_runtime.provider_gateway.policy_service import user_capability_catalog

router = APIRouter(tags=["ai-runtime"])


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


def _point_summary(task: AITask) -> PointSummary:
    return PointSummary(
        quoted_max=0,
        reserved=0,
        settled=0,
        released=0,
        settlement_status="unsettled",
    )


def _task_summary(task: AITask) -> TaskSummary:
    terminal = task.status in {s.value for s in TERMINAL_STATUSES}
    return TaskSummary(
        task_id=task.id,
        capability=task.capability_code,
        action=task.action_code,
        title=task.user_summary,
        status=task.status,  # type: ignore[arg-type]
        stage=Stage(
            code=task.stage_code or "unknown",
            label=task.stage_label or task.stage_code or "Unknown",
            progress_percent=task.progress_percent,
        ),
        service_tier=task.service_tier,  # type: ignore[arg-type]
        accepted_at=task.accepted_at,
        terminal_at=task.terminal_at,
        terminal=terminal,
        available_actions=list(task.available_actions or []),  # type: ignore[arg-type]
        point_summary=_point_summary(task),
    )


@router.post("/ai-task-quotes", status_code=status.HTTP_201_CREATED)
async def create_quote(
    body: QuoteRequest,
    session: Annotated[AsyncSession, Depends(db_session_user_dep)],
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    svc = AcceptanceService(session)
    try:
        quote = await svc.create_quote(
            user_id=user_id,
            capability=body.capability,
            action=body.action,
            service_tier=body.service_tier,
            input_snapshot_ref=body.input_snapshot_ref,
            allow_degrade=body.allow_degrade,
            idempotency_key=idempotency_key,
        )
        await session.commit()
        return quote
    except AcceptanceError as exc:
        return _problem(
            status_code=exc.status, code=exc.code, title=exc.message, detail=exc.message
        )


@router.post("/ai-tasks", status_code=status.HTTP_202_ACCEPTED)
async def accept_task(
    body: AcceptTaskRequest,
    session: Annotated[AsyncSession, Depends(db_session_user_dep)],
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    svc = AcceptanceService(session)
    key = idempotency_key or body.idempotency_key
    try:
        result = await svc.accept(
            user_id=user_id,
            capability=body.capability,
            action=body.action,
            service_tier=body.service_tier,
            quote_id=body.quote_id,
            input_snapshot_ref=body.input_snapshot_ref,
            allow_degrade=body.allow_degrade,
            idempotency_key=key,
        )
        await session.commit()
        return svc.to_accepted_response(result)
    except AcceptanceError as exc:
        return _problem(
            status_code=exc.status, code=exc.code, title=exc.message, detail=exc.message
        )


@router.get("/ai-tasks", response_model=TaskPage)
async def list_tasks(
    session: Annotated[AsyncSession, Depends(db_session_user_dep)],
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    capability: str | None = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    cursor: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
):
    cutoff = datetime.now(timezone.utc) - timedelta(days=90)
    stmt = (
        select(AITask)
        .where(AITask.user_id == user_id, AITask.accepted_at >= cutoff)
        .order_by(AITask.accepted_at.desc(), AITask.id.desc())
    )
    if capability:
        stmt = stmt.where(AITask.capability_code == capability)
    if status_filter:
        stmt = stmt.where(AITask.status == status_filter)
    if cursor:
        try:
            cursor_time_s, cursor_id_s = cursor.split("|", 1)
            cursor_time = datetime.fromisoformat(cursor_time_s)
            cursor_id = UUID(cursor_id_s)
            stmt = stmt.where(
                (AITask.accepted_at < cursor_time)
                | ((AITask.accepted_at == cursor_time) & (AITask.id < cursor_id))
            )
        except ValueError:
            return _problem(
                status_code=422,
                code="INVALID_CURSOR",
                title="Invalid cursor",
            )

    result = await session.execute(stmt.limit(limit + 1))
    rows = list(result.scalars().all())
    next_cursor = None
    if len(rows) > limit:
        last = rows[limit - 1]
        next_cursor = f"{last.accepted_at.isoformat()}|{last.id}"
        rows = rows[:limit]
    return TaskPage(items=[_task_summary(t) for t in rows], next_cursor=next_cursor)


@router.get("/ai-tasks/{task_id}", response_model=TaskDetail)
async def get_task(
    task_id: UUID,
    session: Annotated[AsyncSession, Depends(db_session_user_dep)],
    user_id: Annotated[UUID, Depends(get_current_user_id)],
):
    task = await session.get(AITask, task_id)
    if task is None or task.user_id != user_id:
        return _problem(status_code=404, code="NOT_FOUND", title="Task not found")

    executions = list(
        (
            await session.execute(
                select(AIExecution)
                .where(AIExecution.task_id == task.id)
                .order_by(AIExecution.execution_no.asc())
            )
        )
        .scalars()
        .all()
    )
    milestones = list(
        (
            await session.execute(
                select(AIMilestone)
                .where(AIMilestone.task_id == task.id)
                .order_by(AIMilestone.weight_basis_points.desc())
            )
        )
        .scalars()
        .all()
    )
    summary = _task_summary(task)
    return TaskDetail(
        **summary.model_dump(),
        task_version=task.task_version,
        input_summary={"input_snapshot_id": str(task.input_snapshot_id)},
        executions=[
            ExecutionRef(
                execution_id=e.id,
                execution_no=e.execution_no,
                trigger_kind=e.trigger_kind,  # type: ignore[arg-type]
                source_execution_id=e.source_execution_id,
                status=e.status,  # type: ignore[arg-type]
                started_at=e.started_at or e.created_at,
                finished_at=e.finished_at,
            )
            for e in executions
        ],
        milestones=[
            MilestoneOut(
                code=m.milestone_code,
                label=m.label,
                status=m.status,  # type: ignore[arg-type]
                settle_eligible=m.settle_eligible,
                points_settled=0,
                result_ref=m.result_ref,
                delivered_at=m.delivered_at,
            )
            for m in milestones
        ],
        degraded=False,
        automatic_retry_count=0,
        failure=None,
        result_ref=None,
        degradation_summary=None,
    )


@router.get("/ai-tasks/{task_id}/events")
async def list_events(
    task_id: UUID,
    session: Annotated[AsyncSession, Depends(db_session_user_dep)],
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    after_sequence: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
):
    task = await session.get(AITask, task_id)
    if task is None or task.user_id != user_id:
        return _problem(status_code=404, code="NOT_FOUND", title="Task not found")

    result = await session.execute(
        select(AITaskEvent)
        .where(AITaskEvent.task_id == task_id, AITaskEvent.sequence > after_sequence)
        .order_by(AITaskEvent.sequence.asc())
        .limit(limit)
    )
    events = list(result.scalars().all())
    out = [
        TaskEventOut(
            event_id=e.id,
            sequence=e.sequence,
            event_type=e.event_type,
            occurred_at=e.occurred_at,
            recorded_at=e.recorded_at,
            status=(e.to_status or task.status),  # type: ignore[arg-type]
            stage=Stage(
                code=str((e.payload or {}).get("stage_code") or task.stage_code or "unknown"),
                label=str(
                    (e.payload or {}).get("stage_label") or task.stage_label or "Unknown"
                ),
            ),
            message=e.safe_message or e.event_type,
        )
        for e in events
    ]
    next_sequence = out[-1].sequence if out else after_sequence
    terminal = task.status in {s.value for s in TERMINAL_STATUSES}
    return {
        "task_id": str(task_id),
        "events": [e.model_dump(mode="json") for e in out],
        "next_sequence": next_sequence,
        "terminal": terminal,
        "next_poll_after_ms": 1000,
    }


@router.post("/ai-tasks/{task_id}/cancel", status_code=status.HTTP_202_ACCEPTED)
async def cancel_task(
    task_id: UUID,
    body: TaskActionRequest,
    session: Annotated[AsyncSession, Depends(db_session_user_dep)],
    user_id: Annotated[UUID, Depends(get_current_user_id)],
):
    svc = ControlService(session)
    accept = AcceptanceService(session)
    try:
        task = await svc.cancel(
            task_id=task_id,
            user_id=user_id,
            expected_task_version=body.expected_task_version,
            reason=body.reason,
        )
        await session.commit()
        # Minimal accepted-shaped payload for control responses.
        return {
            "task_id": str(task.id),
            "execution_id": str(task.current_execution_id),
            "status": task.status,
            "task_version": task.task_version,
            "available_actions": task.available_actions,
            "terminal": False,
        }
    except ControlError as exc:
        return _problem(
            status_code=exc.status, code=exc.code, title=exc.message, detail=exc.message
        )


@router.post("/ai-tasks/{task_id}/resume", status_code=status.HTTP_202_ACCEPTED)
async def resume_task(
    task_id: UUID,
    body: ResumeRequest,
    session: Annotated[AsyncSession, Depends(db_session_user_dep)],
    user_id: Annotated[UUID, Depends(get_current_user_id)],
):
    svc = ControlService(session)
    try:
        task = await svc.resume(
            task_id=task_id,
            user_id=user_id,
            expected_task_version=body.expected_task_version,
            user_input_ref=body.user_input_ref,
        )
        await session.commit()
        return {
            "task_id": str(task.id),
            "execution_id": str(task.current_execution_id),
            "status": task.status,
            "task_version": task.task_version,
            "available_actions": task.available_actions,
            "terminal": False,
        }
    except ControlError as exc:
        return _problem(
            status_code=exc.status, code=exc.code, title=exc.message, detail=exc.message
        )


@router.post(
    "/ai-tasks/{task_id}/system-failure-retry", status_code=status.HTTP_202_ACCEPTED
)
async def system_failure_retry(
    task_id: UUID,
    body: TaskActionRequest,
    session: Annotated[AsyncSession, Depends(db_session_user_dep)],
    user_id: Annotated[UUID, Depends(get_current_user_id)],
):
    svc = ControlService(session)
    try:
        task, execution = await svc.system_failure_retry(
            task_id=task_id,
            user_id=user_id,
            expected_task_version=body.expected_task_version,
            reason=body.reason,
        )
        await session.commit()
        return {
            "task_id": str(task.id),
            "execution_id": str(execution.id),
            "status": task.status,
            "task_version": task.task_version,
            "available_actions": task.available_actions,
            "terminal": False,
        }
    except ControlError as exc:
        return _problem(
            status_code=exc.status, code=exc.code, title=exc.message, detail=exc.message
        )


@router.post("/ai-tasks/{task_id}/re-executions", status_code=status.HTTP_202_ACCEPTED)
async def reexecute_task(
    task_id: UUID,
    body: ReexecutionRequest,
    session: Annotated[AsyncSession, Depends(db_session_user_dep)],
    user_id: Annotated[UUID, Depends(get_current_user_id)],
):
    svc = ControlService(session)
    try:
        task, execution = await svc.reexecute(
            task_id=task_id,
            user_id=user_id,
            expected_task_version=body.expected_task_version,
            input_mode=body.input_mode,
            behavior_mode=body.behavior_mode,
            quote_id=body.quote_id,
        )
        await session.commit()
        return {
            "task_id": str(task.id),
            "execution_id": str(execution.id),
            "status": task.status,
            "task_version": task.task_version,
            "available_actions": task.available_actions,
            "terminal": False,
        }
    except ControlError as exc:
        return _problem(
            status_code=exc.status, code=exc.code, title=exc.message, detail=exc.message
        )


@router.get("/ai-tasks/{task_id}/evidence-replay")
async def evidence_replay(
    task_id: UUID,
    session: Annotated[AsyncSession, Depends(db_session_user_dep)],
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    input_mode: str = Query(default="original_snapshot"),
    behavior_mode: str = Query(default="original_locked"),
):
    svc = EvidenceReplayService(session)
    try:
        report = await svc.replay(
            task_id=task_id,
            user_id=user_id,
            choice=ReplayChoice(input_mode=input_mode, behavior_mode=behavior_mode),
        )
    except LookupError:
        return _problem(status_code=404, code="NOT_FOUND", title="Task not found")
    return {
        "task_id": str(report.task_id),
        "complete": report.complete,
        "missing_sequences": report.missing_sequences,
        "events": report.events,
        "choice": {
            "input_mode": report.choice.input_mode if report.choice else None,
            "behavior_mode": report.choice.behavior_mode if report.choice else None,
        },
        "notes": report.notes,
    }


@router.get("/ai-capabilities", response_model=CapabilityCatalogOut)
async def list_ai_capabilities(
    user_id: Annotated[UUID, Depends(get_current_user_id)],
):
    """User capability catalog: tiers and points only (FR-047 — no provider names)."""
    _ = user_id
    items = user_capability_catalog()
    # Strip any accidental provider keys from projection.
    sanitized = []
    for item in items:
        cleaned = {
            k: v
            for k, v in item.items()
            if k
            not in {
                "primary_route",
                "provider",
                "provider_model_name",
                "route_internal_code",
                "model",
            }
        }
        sanitized.append(cleaned)
    return CapabilityCatalogOut(items=sanitized)  # type: ignore[arg-type]


__all__ = ["router"]
