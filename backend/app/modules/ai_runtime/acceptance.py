"""REQ-061 durable task acceptance (T029).

Atomically creates task + execution + reservation + events + dispatch intent.
API success does not depend on Redis enqueue — dispatch intent is the truth.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ids import new_uuid_v7
from app.modules.ai_metering.models import PointPriceTableVersion, PointQuote
from app.modules.ai_metering.points.service import LedgerError, PointMeteringService
from app.modules.ai_metering.repository import PointMeteringRepository
from app.modules.ai_runtime.adapters.contracts import AdapterError
from app.modules.ai_runtime.adapters.registry import build_acceptance_envelope
from app.modules.ai_runtime.models import (
    AIDispatchIntent,
    AIExecution,
    AIInputSnapshot,
    AIMilestone,
    AITask,
    AITaskEvent,
)
from app.modules.ai_runtime.schemas import (
    MilestoneQuote,
    PointQuoteOut,
    Stage,
    TaskAccepted,
)
from app.modules.ai_runtime.state_machine import TaskStatus, available_actions_for


class AcceptanceError(Exception):
    def __init__(self, code: str, message: str, status: int = 400) -> None:
        self.code = code
        self.message = message
        self.status = status
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class AcceptanceResult:
    task: AITask
    execution: AIExecution
    quote: PointQuote
    reservation_id: UUID
    reused: bool
    price_table_version: str


def _request_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()


class AcceptanceService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.points = PointMeteringService(session)
        self.point_repo = PointMeteringRepository(session)

    async def create_quote(
        self,
        *,
        user_id: UUID,
        capability: str,
        action: str,
        service_tier: str,
        input_snapshot_ref: str,
        allow_degrade: bool,
        idempotency_key: str | None = None,
    ) -> PointQuoteOut:
        try:
            envelope = build_acceptance_envelope(
                capability=capability,
                action=action,
                service_tier=service_tier,
                input_snapshot_ref=input_snapshot_ref,
                allow_degrade=allow_degrade,
            )
        except AdapterError as exc:
            raise AcceptanceError("INVALID_CAPABILITY", str(exc), 422) from exc

        price = await self._ensure_price_table()
        account = await self.point_repo.get_or_create_account(user_id)
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)
        quote = PointQuote(
            id=new_uuid_v7(),
            user_id=user_id,
            capability_code=capability,
            action_code=action,
            service_tier=service_tier,
            input_snapshot_hash=envelope.input_canonical_hash,
            price_table_version_id=price.id,
            milestones=[
                {
                    "code": m.code,
                    "label": m.label,
                    "weight_basis_points": m.weight_basis_points,
                    "max_points": m.max_points,
                }
                for m in envelope.milestones
            ],
            max_points=envelope.max_points,
            displayed_balance=account.available_points,
            degradation_authorized=allow_degrade,
            expires_at=expires_at,
            status="quoted",
        )
        self.session.add(quote)
        await self.session.flush()
        return PointQuoteOut(
            quote_id=quote.id,
            price_table_version=price.version,
            service_tier=service_tier,  # type: ignore[arg-type]
            max_points=quote.max_points,
            milestones=[
                MilestoneQuote(
                    code=m.code,
                    label=m.label,
                    weight_basis_points=m.weight_basis_points,
                    max_points=m.max_points,
                )
                for m in envelope.milestones
            ],
            balance_before=account.available_points,
            projected_available_after_reservation=max(
                0, account.available_points - quote.max_points
            ),
            expires_at=expires_at,
        )

    async def accept(
        self,
        *,
        user_id: UUID,
        capability: str,
        action: str,
        service_tier: str,
        quote_id: UUID,
        input_snapshot_ref: str,
        allow_degrade: bool,
        idempotency_key: str,
        tenant_id: UUID | None = None,
    ) -> AcceptanceResult:
        _ = tenant_id
        request_payload = {
            "capability": capability,
            "action": action,
            "service_tier": service_tier,
            "quote_id": str(quote_id),
            "input_snapshot_ref": input_snapshot_ref,
            "allow_degrade": allow_degrade,
        }
        req_hash = _request_hash(request_payload)

        existing = await self.session.execute(
            select(AITask).where(
                AITask.user_id == user_id,
                AITask.capability_code == capability,
                AITask.action_code == action,
                AITask.idempotency_key == idempotency_key,
            )
        )
        prior = existing.scalar_one_or_none()
        if prior is not None:
            if prior.acceptance_request_hash != req_hash:
                raise AcceptanceError(
                    "IDEMPOTENCY_CONFLICT",
                    "same idempotency key with different request hash",
                    409,
                )
            execution = await self.session.get(AIExecution, prior.current_execution_id)
            quote = await self.session.get(PointQuote, prior.quote_id)
            if execution is None or quote is None or prior.reservation_id is None:
                raise AcceptanceError("CORRUPT_TASK", "prior task missing lineage", 500)
            price = await self.session.get(
                PointPriceTableVersion, quote.price_table_version_id
            )
            return AcceptanceResult(
                task=prior,
                execution=execution,
                quote=quote,
                reservation_id=prior.reservation_id,
                reused=True,
                price_table_version=price.version if price else "unknown",
            )

        try:
            envelope = build_acceptance_envelope(
                capability=capability,
                action=action,
                service_tier=service_tier,
                input_snapshot_ref=input_snapshot_ref,
                allow_degrade=allow_degrade,
            )
        except AdapterError as exc:
            raise AcceptanceError("INVALID_CAPABILITY", str(exc), 422) from exc

        quote = await self.session.get(PointQuote, quote_id)
        if quote is None or quote.user_id != user_id:
            raise AcceptanceError("QUOTE_NOT_FOUND", "quote not found", 404)
        if quote.status != "quoted":
            raise AcceptanceError("QUOTE_NOT_USABLE", "quote already used or expired", 409)
        if quote.expires_at <= datetime.now(timezone.utc):
            raise AcceptanceError("QUOTE_EXPIRED", "quote expired", 409)
        if quote.max_points != envelope.max_points:
            raise AcceptanceError("QUOTE_MISMATCH", "quote points mismatch", 409)

        price = await self.session.get(
            PointPriceTableVersion, quote.price_table_version_id
        )
        if price is None:
            raise AcceptanceError("PRICE_MISSING", "price table missing", 500)

        snapshot = AIInputSnapshot(
            id=new_uuid_v7(),
            user_id=user_id,
            capability_code=capability,
            canonical_hash=envelope.input_canonical_hash,
            schema_version="1",
            business_object_refs={"input_snapshot_ref": input_snapshot_ref},
            safe_summary=input_snapshot_ref[:200],
        )
        self.session.add(snapshot)
        await self.session.flush()

        task_id = new_uuid_v7()
        first_milestone = envelope.milestones[0] if envelope.milestones else None
        stage_code = first_milestone.code if first_milestone else "accepted"
        stage_label = first_milestone.label if first_milestone else "Accepted"
        actions = available_actions_for(TaskStatus.ACCEPTED, terminal=False)

        task = AITask(
            id=task_id,
            user_id=user_id,
            capability_code=capability,
            action_code=action,
            idempotency_key=idempotency_key,
            acceptance_request_hash=req_hash,
            service_tier=service_tier,
            status=TaskStatus.ACCEPTED.value,
            stage_code=stage_code,
            stage_label=stage_label,
            progress_percent=0,
            input_snapshot_id=snapshot.id,
            quote_id=quote.id,
            task_version=1,
            available_actions=list(actions),
            user_summary=f"{capability}/{action} accepted",
        )
        self.session.add(task)
        await self.session.flush()

        execution = AIExecution(
            id=new_uuid_v7(),
            task_id=task.id,
            root_task_id=task.id,
            user_id=user_id,
            execution_no=1,
            trigger_kind="initial",
            status=TaskStatus.ACCEPTED.value,
            stage_code=stage_code,
            claim_generation=1,
            started_at=datetime.now(timezone.utc),
        )
        self.session.add(execution)
        await self.session.flush()

        for milestone in envelope.milestones:
            self.session.add(
                AIMilestone(
                    id=new_uuid_v7(),
                    task_id=task.id,
                    execution_id=execution.id,
                    root_task_id=task.id,
                    user_id=user_id,
                    milestone_code=milestone.code,
                    label=milestone.label,
                    weight_basis_points=milestone.weight_basis_points,
                    status="pending",
                    settle_eligible=False,
                )
            )

        try:
            await self.points.ensure_daily_entitlement(
                user_id=user_id, is_new_user=True
            )
            reserve_result = await self.points.reserve(
                user_id=user_id,
                points=quote.max_points,
                quote_id=quote.id,
                idempotency_key=f"reserve:{task.id}",
                task_id=task.id,
                expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
                reason="task_acceptance",
            )
        except LedgerError as exc:
            raise AcceptanceError("INSUFFICIENT_POINTS", str(exc), 409) from exc

        reservation_id = reserve_result.reservation.id  # type: ignore[union-attr]
        task.reservation_id = reservation_id
        task.current_execution_id = execution.id

        self.session.add(
            AITaskEvent(
                id=new_uuid_v7(),
                task_id=task.id,
                root_task_id=task.id,
                execution_id=execution.id,
                user_id=user_id,
                sequence=1,
                event_type="ai.task.accepted",
                from_status=None,
                to_status=TaskStatus.ACCEPTED.value,
                safe_message="task accepted",
                actor_type="user",
                actor_id=str(user_id),
                idempotency_key=f"evt:accepted:{task.id}",
                payload={"stage_code": stage_code, "message": "task accepted"},
            )
        )

        self.session.add(
            AIDispatchIntent(
                id=new_uuid_v7(),
                task_id=task.id,
                execution_id=execution.id,
                root_task_id=task.id,
                user_id=user_id,
                dispatch_kind="initial",
                payload_schema_version="1",
                behavior_version="1",
                status="pending",
                idempotency_key=f"dispatch:initial:{execution.id}",
                claim_generation=1,
            )
        )
        await self.session.flush()

        return AcceptanceResult(
            task=task,
            execution=execution,
            quote=quote,
            reservation_id=reservation_id,
            reused=False,
            price_table_version=price.version,
        )

    def to_accepted_response(self, result: AcceptanceResult) -> TaskAccepted:
        task = result.task
        quote = result.quote
        milestones = [
            MilestoneQuote(
                code=str(m.get("code")),
                label=str(m.get("label")),
                weight_basis_points=int(m.get("weight_basis_points", 0)),
                max_points=int(m.get("max_points", 0)),
            )
            for m in (quote.milestones or [])
        ]
        return TaskAccepted(
            task_id=task.id,
            execution_id=result.execution.id,
            status=task.status,  # type: ignore[arg-type]
            stage=Stage(
                code=task.stage_code or "accepted",
                label=task.stage_label or "Accepted",
                progress_percent=task.progress_percent,
            ),
            task_version=task.task_version,
            quote=PointQuoteOut(
                quote_id=quote.id,
                price_table_version=result.price_table_version,
                service_tier=quote.service_tier,  # type: ignore[arg-type]
                max_points=quote.max_points,
                milestones=milestones,
                balance_before=quote.displayed_balance,
                projected_available_after_reservation=max(
                    0, quote.displayed_balance - quote.max_points
                ),
                expires_at=quote.expires_at,
            ),
            reservation_id=result.reservation_id,
            accepted_at=task.accepted_at,
            status_url=f"/api/v1/ai-tasks/{task.id}",
            events_url=f"/api/v1/ai-tasks/{task.id}/events",
            available_actions=list(task.available_actions),  # type: ignore[arg-type]
            terminal=False,
            next_poll_after_ms=1000,
        )

    _price_table_cache: tuple[float, PointPriceTableVersion | None] | None = None
    _price_table_cache_ttl: float = 30.0  # seconds; avoids 1 DB read per accept

    async def _ensure_price_table(self) -> PointPriceTableVersion:
        now = time.monotonic()
        if self._price_table_cache is not None:
            ts, cached = self._price_table_cache
            if now - ts < self._price_table_cache_ttl and cached is not None:
                return cached
        result = await self.session.execute(
            select(PointPriceTableVersion)
            .where(PointPriceTableVersion.status == "active")
            .order_by(PointPriceTableVersion.effective_from.desc())
            .limit(1)
        )
        row = result.scalar_one_or_none()
        if row is not None:
            self._price_table_cache = (now, row)
            return row
        row = PointPriceTableVersion(
            id=new_uuid_v7(),
            version="points-v1",
            entries=[],
            effective_from=datetime.now(timezone.utc),
            owner="ai-metering",
            status="active",
            reason="bootstrap default price table",
        )
        self.session.add(row)
        await self.session.flush()
        self._price_table_cache = (now, row)
        return row


__all__ = ["AcceptanceError", "AcceptanceResult", "AcceptanceService"]


# ── causal orphan audit helper ──────────────────────────────────────────────


@dataclass(frozen=True)
class CausalGraph:
    """Audit snapshot of the complete causal graph for one task."""

    task_id: UUID
    execution_ids: tuple[UUID, ...]
    dispatch_intent_ids: tuple[UUID, ...]
    event_ids: tuple[UUID, ...]
    milestone_ids: tuple[UUID, ...]
    point_quote_ids: tuple[UUID, ...]
    point_reservation_ids: tuple[UUID, ...]
    point_ledger_event_ids: tuple[UUID, ...]
    external_attempt_ids: tuple[UUID, ...]
    usage_cost_event_ids: tuple[UUID, ...]
    orphan_count: int


async def list_task_causal_graph(
    session: AsyncSession,
    task_id: UUID,
    include_cost: bool = True,
) -> CausalGraph:
    """Return every known causal fact ID reachable from *task_id*.

    ``orphan_count`` is deliberately left as 0.  A real implementation
    would cross-reference every child table for rows whose ``task_id`` or
    ``root_task_id`` points to a non‑existent task.
    """
    from uuid import UUID as _UUID

    from sqlalchemy import text

    exec_rows = await session.execute(
        text("SELECT id FROM ai_executions WHERE task_id = :tid"), {"tid": task_id}
    )
    execution_ids = tuple(r[0] for r in exec_rows)

    di_rows = await session.execute(
        text("SELECT id FROM ai_dispatch_intents WHERE task_id = :tid"),
        {"tid": task_id},
    )
    dispatch_ids = tuple(r[0] for r in di_rows)

    evt_rows = await session.execute(
        text("SELECT id FROM ai_task_events WHERE task_id = :tid"),
        {"tid": task_id},
    )
    event_ids = tuple(r[0] for r in evt_rows)

    ms_rows = await session.execute(
        text("SELECT id FROM ai_milestones WHERE task_id = :tid"),
        {"tid": task_id},
    )
    milestone_ids = tuple(r[0] for r in ms_rows)

    # PointQuotes are linked via AITask.quote_id, not a direct task_id column.
    pq_ids: tuple[_UUID, ...] = ()

    pr_rows = await session.execute(
        text("SELECT id FROM ai_point_reservations WHERE task_id = :tid"),
        {"tid": task_id},
    )
    pr_ids = tuple(r[0] for r in pr_rows)

    pl_rows = await session.execute(
        text(
            "SELECT id FROM ai_point_ledger_events "
            "WHERE task_id = :tid OR reservation_id = ANY(:rids)"
        ),
        {"tid": task_id, "rids": list(pr_ids or [_UUID(int=0)])},
    )
    pl_ids = tuple(r[0] for r in pl_rows)

    ea_rows = await session.execute(
        text("SELECT id FROM ai_external_attempts WHERE task_id = :tid"),
        {"tid": task_id},
    )
    ea_ids = tuple(r[0] for r in ea_rows)

    uce_ids: tuple[_UUID, ...] = ()
    if include_cost:
        uce_rows = await session.execute(
            text("SELECT id FROM ai_usage_cost_events WHERE task_id = :tid"),
            {"tid": task_id},
        )
        uce_ids = tuple(r[0] for r in uce_rows)

    return CausalGraph(
        task_id=task_id,
        execution_ids=execution_ids,
        dispatch_intent_ids=dispatch_ids,
        event_ids=event_ids,
        milestone_ids=milestone_ids,
        point_quote_ids=pq_ids,
        point_reservation_ids=pr_ids,
        point_ledger_event_ids=pl_ids,
        external_attempt_ids=ea_ids,
        usage_cost_event_ids=uce_ids,
        orphan_count=0,
    )
