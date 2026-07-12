"""Transactional projection outbox — re-project facts only (REQ-061 T022).

Deliveries never call providers, tools, domain writes, or metering commands.
Retries only re-read existing facts and update destination projections/status.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Sequence
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.modules.ai_runtime.models import (
    AITask,
    AITaskEvent,
    OperationalTaskProjection,
    TelemetryProjectionDelivery,
)

log = get_logger("ai_runtime.projections")

DESTINATIONS: tuple[str, ...] = ("admin_read_model", "otel", "langsmith")
DEFAULT_POLICY_VERSION = "v1"
DEFAULT_REPRESENTATION = "metadata"

STATUS_PENDING = "pending"
STATUS_DELIVERING = "delivering"
STATUS_CONFIRMED = "confirmed"
STATUS_RETRY_WAIT = "retry_wait"
STATUS_BLOCKED = "blocked"
STATUS_ABANDONED = "abandoned"

TERMINAL_DELIVERY_STATUSES = frozenset(
    {STATUS_CONFIRMED, STATUS_BLOCKED, STATUS_ABANDONED}
)

MAX_DELIVERY_ATTEMPTS = 8
BATCH_LIMIT = 100
BASE_RETRY_SECONDS = 2


def build_event_envelope(
    *,
    source_event_id: str,
    root_task_id: str,
    correlation_id: str,
    event_type: str,
    sequence: int,
    payload: dict[str, Any] | None = None,
    occurred_at: datetime | None = None,
) -> dict[str, Any]:
    """Canonical durable event envelope for projection / CLI contracts."""
    return {
        "source_event_id": source_event_id,
        "root_task_id": root_task_id,
        "correlation_id": correlation_id,
        "event_type": event_type,
        "sequence": sequence,
        "payload": payload or {},
        "occurred_at": (occurred_at or datetime.now(UTC)).isoformat(),
    }


@dataclass
class DeliveryResult:
    status: str
    duplicate: bool = False
    delivery_id: str | None = None


class ProjectionDeliveryService:
    """In-process idempotent delivery helper (contract / unit surface).

    Persistent outbox delivery uses :class:`ProjectionService`.
    """

    def __init__(self) -> None:
        self._confirmed: dict[str, DeliveryResult] = {}

    def deliver(
        self,
        *,
        delivery_id: str,
        destination: str,
        representation: dict[str, Any] | None = None,
    ) -> DeliveryResult:
        _ = destination, representation
        existing = self._confirmed.get(delivery_id)
        if existing is not None:
            return DeliveryResult(
                status=STATUS_CONFIRMED,
                duplicate=True,
                delivery_id=delivery_id,
            )
        result = DeliveryResult(
            status=STATUS_CONFIRMED,
            duplicate=False,
            delivery_id=delivery_id,
        )
        self._confirmed[delivery_id] = result
        return result


class ProjectionService:
    """PostgreSQL-backed projection outbox with idempotent enqueue/delivery."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def enqueue_for_event(
        self,
        *,
        source_event_id: UUID,
        user_id: UUID | None = None,
        destinations: Sequence[str] | None = None,
        representation: str = DEFAULT_REPRESENTATION,
        destination_policy_version: str = DEFAULT_POLICY_VERSION,
    ) -> list[TelemetryProjectionDelivery]:
        """Enqueue one delivery row per destination; idempotent on unique key."""
        targets = tuple(destinations) if destinations is not None else DESTINATIONS
        created: list[TelemetryProjectionDelivery] = []
        for destination in targets:
            if destination not in DESTINATIONS:
                raise ValueError(f"unsupported projection destination: {destination}")
            row = await self._get_delivery(
                source_event_id=source_event_id,
                destination=destination,
                destination_policy_version=destination_policy_version,
            )
            if row is not None:
                created.append(row)
                continue
            row = TelemetryProjectionDelivery(
                source_event_id=source_event_id,
                user_id=user_id,
                destination=destination,
                representation=representation,
                destination_policy_version=destination_policy_version,
                status=STATUS_PENDING,
                attempt_count=0,
                next_attempt_at=datetime.now(UTC),
            )
            try:
                async with self.session.begin_nested():
                    self.session.add(row)
                    await self.session.flush()
            except IntegrityError:
                row = await self._get_delivery(
                    source_event_id=source_event_id,
                    destination=destination,
                    destination_policy_version=destination_policy_version,
                )
                if row is None:
                    raise
            created.append(row)
        return created

    async def deliver_pending(self, *, limit: int = BATCH_LIMIT) -> dict[str, int]:
        """Claim and deliver pending/retry_wait rows. Fact re-projection only."""
        now = datetime.now(UTC)
        rows = list(
            (
                await self.session.scalars(
                    select(TelemetryProjectionDelivery)
                    .where(
                        TelemetryProjectionDelivery.status.in_(
                            [STATUS_PENDING, STATUS_RETRY_WAIT]
                        ),
                        or_(
                            TelemetryProjectionDelivery.next_attempt_at.is_(None),
                            TelemetryProjectionDelivery.next_attempt_at <= now,
                        ),
                    )
                    .order_by(TelemetryProjectionDelivery.next_attempt_at.nullsfirst())
                    .limit(limit)
                    .with_for_update(skip_locked=True)
                )
            ).all()
        )

        confirmed = 0
        retry_wait = 0
        blocked = 0
        abandoned = 0

        for row in rows:
            row.status = STATUS_DELIVERING
            row.attempt_count += 1
            row.last_attempt_at = now
            if row.first_attempt_at is None:
                row.first_attempt_at = now
            await self.session.flush()

            try:
                outcome = await self._deliver_one(row)
            except Exception as exc:  # noqa: BLE001 — bounded retry path
                outcome = self._schedule_retry(row, error_category=type(exc).__name__)

            if outcome == STATUS_CONFIRMED:
                confirmed += 1
            elif outcome == STATUS_RETRY_WAIT:
                retry_wait += 1
            elif outcome == STATUS_BLOCKED:
                blocked += 1
            elif outcome == STATUS_ABANDONED:
                abandoned += 1

        return {
            "claimed": len(rows),
            "confirmed": confirmed,
            "retry_wait": retry_wait,
            "blocked": blocked,
            "abandoned": abandoned,
        }

    async def mark_confirmed(
        self,
        delivery_id: UUID,
        *,
        destination_record_ref: str | None = None,
        confirmed_position: str | None = None,
    ) -> TelemetryProjectionDelivery:
        row = await self.session.get(TelemetryProjectionDelivery, delivery_id)
        if row is None:
            raise LookupError(f"projection delivery {delivery_id} not found")
        row.status = STATUS_CONFIRMED
        row.last_success_at = datetime.now(UTC)
        row.next_attempt_at = None
        row.last_error_category = None
        if destination_record_ref is not None:
            row.destination_record_ref = destination_record_ref
        if confirmed_position is not None:
            row.confirmed_position = confirmed_position
        await self.session.flush()
        return row

    async def mark_blocked(
        self,
        delivery_id: UUID,
        *,
        error_category: str = "privacy_policy_denied",
    ) -> TelemetryProjectionDelivery:
        row = await self.session.get(TelemetryProjectionDelivery, delivery_id)
        if row is None:
            raise LookupError(f"projection delivery {delivery_id} not found")
        row.status = STATUS_BLOCKED
        row.last_error_category = error_category
        row.next_attempt_at = None
        await self.session.flush()
        return row

    async def rebuild_admin_projection(
        self,
        *,
        task_id: UUID | None = None,
        limit: int = BATCH_LIMIT,
    ) -> dict[str, int]:
        """Stub rebuild of operational read model from authoritative task rows."""
        stmt = select(AITask).order_by(AITask.updated_at.desc()).limit(limit)
        if task_id is not None:
            stmt = select(AITask).where(AITask.id == task_id)
        tasks = list((await self.session.scalars(stmt)).all())
        rebuilt = 0
        for task in tasks:
            await self._upsert_admin_projection(task)
            rebuilt += 1
        return {"rebuilt": rebuilt}

    async def _get_delivery(
        self,
        *,
        source_event_id: UUID,
        destination: str,
        destination_policy_version: str,
    ) -> TelemetryProjectionDelivery | None:
        return await self.session.scalar(
            select(TelemetryProjectionDelivery).where(
                and_(
                    TelemetryProjectionDelivery.source_event_id == source_event_id,
                    TelemetryProjectionDelivery.destination == destination,
                    TelemetryProjectionDelivery.destination_policy_version
                    == destination_policy_version,
                )
            )
        )

    async def _deliver_one(self, row: TelemetryProjectionDelivery) -> str:
        event = await self.session.get(AITaskEvent, row.source_event_id)
        if event is None:
            return self._schedule_retry(row, error_category="source_event_missing")

        if row.destination == "admin_read_model":
            task = await self.session.get(AITask, event.task_id)
            if task is None:
                return self._schedule_retry(row, error_category="source_task_missing")
            await self._upsert_admin_projection(task, source_event=event)
            row.destination_record_ref = f"operational_task:{task.id}"
            row.confirmed_position = str(event.sequence)
        elif row.destination == "otel":
            # Local fact re-projection marker only — live OTel export is T159.
            row.destination_record_ref = f"otel:event:{event.id}"
            row.confirmed_position = str(event.sequence)
        elif row.destination == "langsmith":
            if row.representation not in ("metadata", "redacted", "restricted"):
                return await self._block(row, "representation_not_approved")
            row.destination_record_ref = f"langsmith:event:{event.id}"
            row.confirmed_position = str(event.sequence)
        else:
            return await self._block(row, "unknown_destination")

        row.status = STATUS_CONFIRMED
        row.last_success_at = datetime.now(UTC)
        row.next_attempt_at = None
        row.last_error_category = None
        await self.session.flush()
        return STATUS_CONFIRMED

    async def _upsert_admin_projection(
        self,
        task: AITask,
        *,
        source_event: AITaskEvent | None = None,
    ) -> OperationalTaskProjection:
        proj = await self.session.get(OperationalTaskProjection, task.id)
        sequence = source_event.sequence if source_event is not None else 0
        denormalized = {
            "status": task.status,
            "capability_code": task.capability_code,
            "action_code": task.action_code,
            "user_summary": task.user_summary,
            "failure_category": task.failure_category,
            "available_actions": task.available_actions,
        }
        if proj is None:
            root_task_id = (
                source_event.root_task_id
                if source_event is not None
                else getattr(task, "root_task_id", None) or task.id
            )
            proj = OperationalTaskProjection(
                task_id=task.id,
                user_id=task.user_id,
                root_task_id=root_task_id,
                status=task.status,
                capability_code=task.capability_code,
                action_code=task.action_code,
                denormalized=denormalized,
                source_event_sequence=sequence,
                coverage={"admin_read_model": True},
                unknown_count=0,
                fresh_at=datetime.now(UTC),
            )
            self.session.add(proj)
        else:
            if sequence and sequence < proj.source_event_sequence:
                # Older fact — skip overwrite but still count as successful re-project.
                return proj
            proj.status = task.status
            proj.capability_code = task.capability_code
            proj.action_code = task.action_code
            proj.denormalized = denormalized
            if sequence:
                proj.source_event_sequence = sequence
            proj.coverage = {**(proj.coverage or {}), "admin_read_model": True}
            proj.fresh_at = datetime.now(UTC)
            proj.updated_at = datetime.now(UTC)
        await self.session.flush()
        return proj

    def _schedule_retry(
        self,
        row: TelemetryProjectionDelivery,
        *,
        error_category: str,
    ) -> str:
        row.last_error_category = error_category
        if row.attempt_count >= MAX_DELIVERY_ATTEMPTS:
            row.status = STATUS_ABANDONED
            row.next_attempt_at = None
            log.warning(
                "projection_delivery_abandoned",
                delivery_id=str(row.id),
                destination=row.destination,
                error_category=error_category,
                attempt_count=row.attempt_count,
            )
            return STATUS_ABANDONED

        delay = min(300, BASE_RETRY_SECONDS ** min(row.attempt_count, 8))
        row.status = STATUS_RETRY_WAIT
        row.next_attempt_at = datetime.now(UTC) + timedelta(seconds=delay)
        return STATUS_RETRY_WAIT

    async def _block(
        self,
        row: TelemetryProjectionDelivery,
        error_category: str,
    ) -> str:
        row.status = STATUS_BLOCKED
        row.last_error_category = error_category
        row.next_attempt_at = None
        await self.session.flush()
        return STATUS_BLOCKED


__all__ = [
    "DEFAULT_POLICY_VERSION",
    "DESTINATIONS",
    "DeliveryResult",
    "ProjectionDeliveryService",
    "ProjectionService",
    "build_event_envelope",
]
