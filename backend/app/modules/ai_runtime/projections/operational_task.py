"""Operational task projection consumers (REQ-061 T158).

Builds/refreshes the admin read model from durable runtime facts.
Completeness, orphan, freshness, coverage and unknown-rate calculations
are derived from existing facts only — never by re-executing AI work.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ai_runtime.models import (
    AIExternalAttempt,
    AIMilestone,
    AITask,
    AITaskEvent,
    OperationalTaskProjection,
    TelemetryProjectionDelivery,
)

FRESHNESS_SLA = timedelta(minutes=5)
CATCHUP_SLA = timedelta(minutes=30)


@dataclass(frozen=True)
class CompletenessReport:
    task_id: UUID
    complete: bool
    orphan_event_ids: tuple[str, ...]
    missing_sequences: tuple[int, ...]
    coverage: dict[str, bool]
    unknown_count: int
    fresh_at: datetime | None
    stale: bool


@dataclass(frozen=True)
class RebuildPosition:
    destination: str
    last_confirmed_sequence: int | None
    backlog_count: int
    oldest_pending_at: datetime | None


async def upsert_from_task(
    session: AsyncSession,
    task: AITask,
    *,
    source_sequence: int = 0,
    coverage: dict[str, Any] | None = None,
) -> OperationalTaskProjection:
    """Upsert the denormalized operational projection for one task."""
    proj = await session.get(OperationalTaskProjection, task.id)
    denormalized = {
        "status": task.status,
        "capability_code": task.capability_code,
        "action_code": task.action_code,
        "user_summary": task.user_summary,
        "failure_category": task.failure_category,
        "available_actions": list(task.available_actions or []),
        "task_version": task.task_version,
    }
    now = datetime.now(UTC)
    if proj is None:
        proj = OperationalTaskProjection(
            task_id=task.id,
            user_id=task.user_id,
            root_task_id=getattr(task, "root_task_id", None) or task.id,
            status=task.status,
            capability_code=task.capability_code,
            action_code=task.action_code,
            denormalized=denormalized,
            source_event_sequence=source_sequence,
            coverage=coverage or {"admin_read_model": True},
            unknown_count=0,
            fresh_at=now,
        )
        session.add(proj)
    else:
        if source_sequence and source_sequence < proj.source_event_sequence:
            return proj
        proj.status = task.status
        proj.capability_code = task.capability_code
        proj.action_code = task.action_code
        proj.denormalized = denormalized
        if source_sequence:
            proj.source_event_sequence = source_sequence
        proj.coverage = {**(proj.coverage or {}), **(coverage or {"admin_read_model": True})}
        proj.fresh_at = now
        proj.updated_at = now
    await session.flush()
    return proj


async def check_completeness(
    session: AsyncSession,
    task_id: UUID,
) -> CompletenessReport:
    """Detect sequence gaps and orphaned projection rows for one task."""
    events = (
        await session.execute(
            select(AITaskEvent)
            .where(AITaskEvent.task_id == task_id)
            .order_by(AITaskEvent.sequence.asc())
        )
    ).scalars().all()
    sequences = [e.sequence for e in events]
    missing: list[int] = []
    if sequences:
        expected = range(min(sequences), max(sequences) + 1)
        present = set(sequences)
        missing = [i for i in expected if i not in present]

    proj = await session.get(OperationalTaskProjection, task_id)
    orphan_event_ids: list[str] = []
    if proj is not None and sequences:
        max_seq = max(sequences)
        if proj.source_event_sequence > max_seq:
            orphan_event_ids.append(f"projection_ahead:{proj.source_event_sequence}")

    unknown = (
        await session.execute(
            select(func.count())
            .select_from(AIExternalAttempt)
            .where(
                AIExternalAttempt.task_id == task_id,
                AIExternalAttempt.status == "unknown",
            )
        )
    ).scalar_one()

    milestones = (
        await session.execute(
            select(func.count())
            .select_from(AIMilestone)
            .where(AIMilestone.task_id == task_id)
        )
    ).scalar_one()

    coverage = dict(proj.coverage) if proj and proj.coverage else {}
    coverage.setdefault("events", bool(sequences))
    coverage.setdefault("milestones", int(milestones or 0) > 0)
    coverage.setdefault("admin_read_model", proj is not None)

    fresh_at = proj.fresh_at if proj else None
    stale = True
    if fresh_at is not None:
        age = datetime.now(UTC) - (
            fresh_at if fresh_at.tzinfo else fresh_at.replace(tzinfo=UTC)
        )
        stale = age > FRESHNESS_SLA

    complete = not missing and not orphan_event_ids and proj is not None
    return CompletenessReport(
        task_id=task_id,
        complete=complete,
        orphan_event_ids=tuple(orphan_event_ids),
        missing_sequences=tuple(missing),
        coverage=coverage,
        unknown_count=int(unknown or 0),
        fresh_at=fresh_at,
        stale=stale,
    )


async def calculate_unknown_rate(
    session: AsyncSession,
    *,
    since: datetime | None = None,
) -> float:
    """Return unknown/(known+unknown) attempt rate in [0, 1]."""
    q = select(AIExternalAttempt.status)
    if since is not None:
        q = q.where(AIExternalAttempt.created_at >= since)
    rows = (await session.execute(q)).scalars().all()
    if not rows:
        return 0.0
    unknown = sum(1 for s in rows if s == "unknown")
    return unknown / len(rows)


async def rebuild_positions(
    session: AsyncSession,
    *,
    destination: str = "admin_read_model",
) -> RebuildPosition:
    """Return catch-up cursor for a projection destination."""
    last = (
        await session.execute(
            select(TelemetryProjectionDelivery)
            .where(
                TelemetryProjectionDelivery.destination == destination,
                TelemetryProjectionDelivery.status == "confirmed",
            )
            .order_by(TelemetryProjectionDelivery.last_success_at.desc().nullslast())
            .limit(1)
        )
    ).scalar_one_or_none()
    pending = (
        await session.execute(
            select(func.count())
            .select_from(TelemetryProjectionDelivery)
            .where(
                TelemetryProjectionDelivery.destination == destination,
                TelemetryProjectionDelivery.status.in_(["pending", "retry_wait"]),
            )
        )
    ).scalar_one()
    oldest = (
        await session.execute(
            select(TelemetryProjectionDelivery)
            .where(
                TelemetryProjectionDelivery.destination == destination,
                TelemetryProjectionDelivery.status.in_(["pending", "retry_wait"]),
            )
            .order_by(TelemetryProjectionDelivery.first_attempt_at.asc().nullslast())
            .limit(1)
        )
    ).scalar_one_or_none()
    seq: int | None = None
    if last and last.confirmed_position:
        try:
            seq = int(last.confirmed_position)
        except (TypeError, ValueError):
            seq = None
    return RebuildPosition(
        destination=destination,
        last_confirmed_sequence=seq,
        backlog_count=int(pending or 0),
        oldest_pending_at=oldest.first_attempt_at if oldest else None,
    )


async def search_projections(
    session: AsyncSession,
    *,
    task_id: UUID | None = None,
    user_id: UUID | None = None,
    capability: str | None = None,
    status: str | None = None,
    cursor: str | None = None,
    limit: int = 50,
) -> tuple[list[OperationalTaskProjection], str | None]:
    """Cursor page over operational task projections."""
    q = select(OperationalTaskProjection).order_by(
        OperationalTaskProjection.updated_at.desc(),
        OperationalTaskProjection.task_id.desc(),
    )
    if task_id is not None:
        q = q.where(OperationalTaskProjection.task_id == task_id)
    if user_id is not None:
        q = q.where(OperationalTaskProjection.user_id == user_id)
    if capability is not None:
        q = q.where(OperationalTaskProjection.capability_code == capability)
    if status is not None:
        q = q.where(OperationalTaskProjection.status == status)
    if cursor:
        try:
            cursor_uuid = UUID(cursor)
            q = q.where(OperationalTaskProjection.task_id < cursor_uuid)
        except ValueError:
            pass
    rows = (await session.execute(q.limit(min(200, max(1, limit)) + 1))).scalars().all()
    next_cursor = None
    if len(rows) > limit:
        rows = rows[:limit]
        next_cursor = str(rows[-1].task_id)
    return list(rows), next_cursor


__all__ = [
    "CATCHUP_SLA",
    "CompletenessReport",
    "FRESHNESS_SLA",
    "RebuildPosition",
    "calculate_unknown_rate",
    "check_completeness",
    "rebuild_positions",
    "search_projections",
    "upsert_from_task",
]
