"""REQ-061 recovery — dispatch delivery, claims, expiry, effects, admission (T023).

PostgreSQL ``AIDispatchIntent`` rows are acceptance truth; ARQ jobs are a
best-effort transport projection. Redis loss never deletes durable intents.
"""

from __future__ import annotations

import socket
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.modules.ai_runtime.models import (
    AIDispatchIntent,
    AIExecution,
    AIExternalEffectIntent,
    AITask,
)
from app.modules.ai_runtime.repository import (
    AIRuntimeRepository,
    ClaimGenerationConflict,
)
from app.modules.ai_runtime.service import AIRuntimeService
from app.modules.ai_runtime.state_machine import TaskStatus, is_terminal

log = get_logger("ai_runtime.recovery")

DEFAULT_MAX_DISPATCH_ATTEMPTS = 5
DEFAULT_CLAIM_TTL_SECONDS = 60
DEFAULT_MAX_RUNNING_EXECUTIONS = 50
DEFAULT_RETRY_DELAY_SECONDS = 30
DEFAULT_CLAIM_RENEW_BEFORE_SECONDS = 20

DISPATCH_PENDING = "pending"
DISPATCH_DISPATCHING = "dispatching"
DISPATCH_CONFIRMED = "confirmed"
DISPATCH_RETRY_WAIT = "retry_wait"
DISPATCH_DEAD_LETTER = "dead_letter"
DISPATCH_CANCELLED = "cancelled"

EFFECT_UNKNOWN = "unknown"
EFFECT_RECONCILED = "reconciled"
EFFECT_SENT = "sent"
EFFECT_ADOPTED = "adopted"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def default_claim_owner() -> str:
    return f"{socket.gethostname()}:{uuid.uuid4().hex[:12]}"


@dataclass(frozen=True, slots=True)
class AdmissionDecision:
    admitted: bool
    running_count: int
    limit: int
    reason: str = ""


@dataclass(frozen=True, slots=True)
class DeliverResult:
    claimed: int
    enqueued: int
    dead_lettered: int
    admission_rejected: int
    intent_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RecoveryScanResult:
    stranded_reset: int
    retry_due: int
    expired_tasks: int
    claims_renewed: int
    unknown_effects: int
    delivered: DeliverResult | None = None


class RecoveryService:
    """Idempotent dispatch delivery, claim fencing, and effect reconciliation."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        claim_owner: str | None = None,
        max_dispatch_attempts: int = DEFAULT_MAX_DISPATCH_ATTEMPTS,
        max_running_executions: int = DEFAULT_MAX_RUNNING_EXECUTIONS,
        claim_ttl_seconds: int = DEFAULT_CLAIM_TTL_SECONDS,
        retry_delay_seconds: int = DEFAULT_RETRY_DELAY_SECONDS,
        claim_renew_before_seconds: int = DEFAULT_CLAIM_RENEW_BEFORE_SECONDS,
    ) -> None:
        self.session = session
        self.repo = AIRuntimeRepository(session)
        self.runtime = AIRuntimeService(session)
        self.claim_owner = claim_owner or default_claim_owner()
        self.max_dispatch_attempts = max(1, int(max_dispatch_attempts))
        self.max_running_executions = max(1, int(max_running_executions))
        self.claim_ttl_seconds = max(5, int(claim_ttl_seconds))
        self.retry_delay_seconds = max(1, int(retry_delay_seconds))
        self.claim_renew_before_seconds = max(1, int(claim_renew_before_seconds))

    # ------------------------------------------------------------------
    # Bounded admission
    # ------------------------------------------------------------------

    async def count_running_executions(self) -> int:
        result = await self.session.execute(
            select(func.count())
            .select_from(AIExecution)
            .where(AIExecution.status == TaskStatus.RUNNING.value)
        )
        return int(result.scalar_one() or 0)

    async def check_admission(self) -> AdmissionDecision:
        running = await self.count_running_executions()
        if running >= self.max_running_executions:
            return AdmissionDecision(
                admitted=False,
                running_count=running,
                limit=self.max_running_executions,
                reason="running_execution_limit",
            )
        return AdmissionDecision(
            admitted=True,
            running_count=running,
            limit=self.max_running_executions,
        )

    # ------------------------------------------------------------------
    # Dispatch claim / confirm / retry / dead-letter
    # ------------------------------------------------------------------

    async def list_runnable_dispatch_intents(
        self, *, limit: int = 50
    ) -> list[AIDispatchIntent]:
        now = _utcnow()
        bounded = min(max(int(limit), 1), 500)
        result = await self.session.execute(
            select(AIDispatchIntent)
            .where(
                AIDispatchIntent.status == DISPATCH_PENDING,
                or_(
                    AIDispatchIntent.next_attempt_at.is_(None),
                    AIDispatchIntent.next_attempt_at <= now,
                ),
            )
            .order_by(AIDispatchIntent.created_at)
            .limit(bounded)
            .with_for_update(skip_locked=True)
        )
        return list(result.scalars().all())

    async def claim_dispatch_intent(
        self, intent: AIDispatchIntent
    ) -> AIDispatchIntent | None:
        """Fence-claim a pending intent → ``dispatching`` (or dead-letter)."""
        if intent.status != DISPATCH_PENDING:
            return None
        next_attempts = intent.attempt_count + 1
        if next_attempts > self.max_dispatch_attempts:
            return await self.dead_letter_intent(
                intent.id,
                expected_claim_generation=intent.claim_generation,
                reason="attempts_exhausted",
            )
        expires = _utcnow() + timedelta(seconds=self.claim_ttl_seconds)
        try:
            return await self.repo.cas_dispatch_intent(
                intent_id=intent.id,
                expected_claim_generation=intent.claim_generation,
                values={
                    "status": DISPATCH_DISPATCHING,
                    "claim_owner": self.claim_owner,
                    "claim_expires_at": expires,
                    "claim_generation": intent.claim_generation + 1,
                    "attempt_count": next_attempts,
                    "next_attempt_at": None,
                },
            )
        except ClaimGenerationConflict:
            log.info(
                "ai_runtime.dispatch.claim_conflict",
                intent_id=str(intent.id),
            )
            return None

    async def confirm_dispatch_intent(
        self,
        *,
        intent_id: UUID,
        expected_claim_generation: int,
        transport_job_id: str | None,
        claim_owner: str | None = None,
    ) -> AIDispatchIntent:
        """CAS-confirm a claimed intent with optional ARQ job evidence."""
        owner = claim_owner or self.claim_owner
        values: dict[str, Any] = {
            "status": DISPATCH_CONFIRMED,
            "confirmed_at": _utcnow(),
            "claim_owner": owner,
            "claim_expires_at": None,
        }
        if transport_job_id is not None:
            values["transport_job_id"] = transport_job_id
        return await self.repo.cas_dispatch_intent(
            intent_id=intent_id,
            expected_claim_generation=expected_claim_generation,
            values=values,
        )

    async def schedule_retry_wait(
        self,
        *,
        intent_id: UUID,
        expected_claim_generation: int,
        delay_seconds: int | None = None,
        error_category: str = "transient",
    ) -> AIDispatchIntent:
        """Durable ``retry_wait`` scheduling via ``next_attempt_at``."""
        delay = self.retry_delay_seconds if delay_seconds is None else max(1, delay_seconds)
        return await self.repo.cas_dispatch_intent(
            intent_id=intent_id,
            expected_claim_generation=expected_claim_generation,
            values={
                "status": DISPATCH_RETRY_WAIT,
                "next_attempt_at": _utcnow() + timedelta(seconds=delay),
                "last_error_category": error_category,
                "claim_owner": None,
                "claim_expires_at": None,
            },
        )

    async def dead_letter_intent(
        self,
        intent_id: UUID,
        *,
        expected_claim_generation: int,
        reason: str = "attempts_exhausted",
    ) -> AIDispatchIntent:
        return await self.repo.cas_dispatch_intent(
            intent_id=intent_id,
            expected_claim_generation=expected_claim_generation,
            values={
                "status": DISPATCH_DEAD_LETTER,
                "last_error_category": reason,
                "claim_owner": None,
                "claim_expires_at": None,
                "next_attempt_at": None,
            },
        )

    async def enqueue_dispatch_job(
        self,
        redis: Any,
        intent: AIDispatchIntent,
    ) -> str | None:
        """Best-effort ARQ enqueue; intent remains truth if Redis fails."""
        if redis is None:
            log.error(
                "ai_runtime.dispatch.enqueue_skipped",
                intent_id=str(intent.id),
                reason="redis_unavailable",
            )
            return None
        try:
            job = await redis.enqueue_job(
                "dispatch_ai_task_intent",
                str(intent.id),
            )
        except Exception as exc:  # noqa: BLE001 — transport must not lose intent
            log.error(
                "ai_runtime.dispatch.enqueue_failed",
                intent_id=str(intent.id),
                error=str(exc),
            )
            return None
        if job is None:
            return None
        job_id = getattr(job, "job_id", None) or str(job)
        return str(job_id)

    async def deliver_pending_intents(
        self,
        redis: Any | None = None,
        *,
        limit: int = 50,
        respect_admission: bool = True,
    ) -> DeliverResult:
        """Claim pending intents and best-effort enqueue ARQ jobs."""
        if respect_admission:
            admission = await self.check_admission()
            if not admission.admitted:
                return DeliverResult(
                    claimed=0,
                    enqueued=0,
                    dead_lettered=0,
                    admission_rejected=1,
                    intent_ids=(),
                )

        candidates = await self.list_runnable_dispatch_intents(limit=limit)
        claimed = 0
        enqueued = 0
        dead_lettered = 0
        intent_ids: list[str] = []

        for intent in candidates:
            claimed_intent = await self.claim_dispatch_intent(intent)
            if claimed_intent is None:
                continue
            if claimed_intent.status == DISPATCH_DEAD_LETTER:
                dead_lettered += 1
                intent_ids.append(str(claimed_intent.id))
                continue
            claimed += 1
            intent_ids.append(str(claimed_intent.id))
            job_id = await self.enqueue_dispatch_job(redis, claimed_intent)
            if job_id is not None:
                enqueued += 1

        await self.session.flush()
        log.info(
            "ai_runtime.dispatch.delivered",
            claimed=claimed,
            enqueued=enqueued,
            dead_lettered=dead_lettered,
        )
        return DeliverResult(
            claimed=claimed,
            enqueued=enqueued,
            dead_lettered=dead_lettered,
            admission_rejected=0,
            intent_ids=tuple(intent_ids),
        )

    # ------------------------------------------------------------------
    # Stranded / retry_wait reconciliation
    # ------------------------------------------------------------------

    async def reconcile_stranded_intents(self, *, limit: int = 100) -> dict[str, int]:
        """Return stranded ``dispatching`` / due ``retry_wait`` intents to pending."""
        now = _utcnow()
        bounded = min(max(int(limit), 1), 500)
        stranded = 0
        retry_due = 0

        stranded_rows = await self.session.execute(
            select(AIDispatchIntent)
            .where(
                AIDispatchIntent.status == DISPATCH_DISPATCHING,
                or_(
                    AIDispatchIntent.claim_expires_at.is_(None),
                    AIDispatchIntent.claim_expires_at <= now,
                ),
            )
            .order_by(AIDispatchIntent.updated_at)
            .limit(bounded)
            .with_for_update(skip_locked=True)
        )
        for intent in stranded_rows.scalars().all():
            try:
                await self.repo.cas_dispatch_intent(
                    intent_id=intent.id,
                    expected_claim_generation=intent.claim_generation,
                    values={
                        "status": DISPATCH_PENDING,
                        "claim_owner": None,
                        "claim_expires_at": None,
                        "last_error_category": "stranded_dispatching",
                    },
                )
                stranded += 1
            except ClaimGenerationConflict:
                continue

        remaining = max(0, bounded - stranded)
        if remaining:
            retry_rows = await self.session.execute(
                select(AIDispatchIntent)
                .where(
                    AIDispatchIntent.status == DISPATCH_RETRY_WAIT,
                    AIDispatchIntent.next_attempt_at.is_not(None),
                    AIDispatchIntent.next_attempt_at <= now,
                )
                .order_by(AIDispatchIntent.next_attempt_at)
                .limit(remaining)
                .with_for_update(skip_locked=True)
            )
            for intent in retry_rows.scalars().all():
                try:
                    await self.repo.cas_dispatch_intent(
                        intent_id=intent.id,
                        expected_claim_generation=intent.claim_generation,
                        values={
                            "status": DISPATCH_PENDING,
                            "claim_owner": None,
                            "claim_expires_at": None,
                        },
                    )
                    retry_due += 1
                except ClaimGenerationConflict:
                    continue

        await self.session.flush()
        log.info(
            "ai_runtime.dispatch.reconciled",
            stranded_reset=stranded,
            retry_due=retry_due,
        )
        return {"stranded_reset": stranded, "retry_due": retry_due}

    # ------------------------------------------------------------------
    # Execution claim renewal + expired tasks
    # ------------------------------------------------------------------

    async def renew_execution_claims(
        self,
        *,
        claim_owner: str | None = None,
        limit: int = 100,
    ) -> int:
        """Extend leases for executions still owned by ``claim_owner``."""
        owner = claim_owner or self.claim_owner
        now = _utcnow()
        renew_before = now + timedelta(seconds=self.claim_renew_before_seconds)
        bounded = min(max(int(limit), 1), 500)
        result = await self.session.execute(
            select(AIExecution)
            .where(
                AIExecution.claim_owner == owner,
                AIExecution.finished_at.is_(None),
                AIExecution.claim_expires_at.is_not(None),
                AIExecution.claim_expires_at <= renew_before,
            )
            .order_by(AIExecution.claim_expires_at)
            .limit(bounded)
            .with_for_update(skip_locked=True)
        )
        renewed = 0
        new_expires = now + timedelta(seconds=self.claim_ttl_seconds)
        for execution in result.scalars().all():
            try:
                await self.runtime.renew_execution_claim(
                    execution_id=execution.id,
                    expected_claim_generation=execution.claim_generation,
                    claim_owner=owner,
                    claim_expires_at=new_expires,
                )
                renewed += 1
            except ClaimGenerationConflict:
                continue
        await self.session.flush()
        return renewed

    async def scan_expired_tasks(self, *, limit: int = 100) -> int:
        """Transition past-``expires_at`` non-terminal tasks to EXPIRED."""
        now = _utcnow()
        bounded = min(max(int(limit), 1), 500)
        terminal_values = [s.value for s in TaskStatus if is_terminal(s)]
        result = await self.session.execute(
            select(AITask)
            .where(
                AITask.expires_at.is_not(None),
                AITask.expires_at <= now,
                AITask.status.notin_(terminal_values),
            )
            .order_by(AITask.expires_at)
            .limit(bounded)
            .with_for_update(skip_locked=True)
        )
        expired = 0
        for task in result.scalars().all():
            try:
                await self.runtime.transition_task(
                    task_id=task.id,
                    target_status=TaskStatus.EXPIRED,
                    expected_task_version=task.task_version,
                    reason_category="expired",
                    safe_message="任务已过期",
                    actor_type="system",
                    actor_id="recovery",
                )
                expired += 1
            except Exception as exc:  # noqa: BLE001 — skip conflicting rows
                log.warning(
                    "ai_runtime.recovery.expire_failed",
                    task_id=str(task.id),
                    error=str(exc),
                )
        await self.session.flush()
        return expired

    # ------------------------------------------------------------------
    # Fenced external-effect send / adopt / unknown reconciliation
    # ------------------------------------------------------------------

    async def mark_effect_sent(
        self,
        *,
        effect_intent_id: UUID,
        execution_id: UUID,
        expected_claim_generation: int,
        provider_request_id: str | None = None,
        attempt_id: UUID | None = None,
    ) -> AIExternalEffectIntent:
        """Mark a prepared effect as sent under the current execution fence."""
        values: dict[str, Any] = {
            "status": EFFECT_SENT,
            "sent_at": _utcnow(),
        }
        if provider_request_id is not None:
            values["provider_request_id"] = provider_request_id
        if attempt_id is not None:
            values["attempt_id"] = attempt_id
        return await self.repo.cas_effect_intent_transition(
            intent_id=effect_intent_id,
            execution_id=execution_id,
            expected_claim_generation=expected_claim_generation,
            values=values,
        )

    async def adopt_effect_result(
        self,
        *,
        execution_id: UUID,
        effect_intent_id: UUID,
        expected_claim_generation: int,
        status: str = EFFECT_ADOPTED,
        provider_request_id: str | None = None,
        result_evidence_ref: str | None = None,
    ) -> AIExternalEffectIntent:
        """Delegate CAS adoption to ``AIRuntimeService`` (no provider_gateway import)."""
        return await self.runtime.adopt_effect_result(
            execution_id=execution_id,
            effect_intent_id=effect_intent_id,
            expected_claim_generation=expected_claim_generation,
            status=status,
            provider_request_id=provider_request_id,
            result_evidence_ref=result_evidence_ref,
        )

    async def reconcile_unknown_effects(self, *, limit: int = 100) -> int:
        """Mark unknown effects reconciled without replaying provider calls.

        Owning tasks in non-terminal states move to ``result_confirming`` so
        operators can inspect evidence; stale fences never mutate business truth.
        """
        bounded = min(max(int(limit), 1), 500)
        result = await self.session.execute(
            select(AIExternalEffectIntent)
            .where(AIExternalEffectIntent.status == EFFECT_UNKNOWN)
            .order_by(AIExternalEffectIntent.created_at)
            .limit(bounded)
            .with_for_update(skip_locked=True)
        )
        reconciled = 0
        for effect in result.scalars().all():
            execution = await self.repo.get_execution(effect.execution_id)
            if execution is None:
                continue
            # Only the current fence may finalize reconciliation.
            if execution.claim_generation != effect.claim_generation:
                # Leave as unknown evidence; current owner must reconcile.
                continue
            try:
                await self.repo.cas_effect_intent_transition(
                    intent_id=effect.id,
                    execution_id=effect.execution_id,
                    expected_claim_generation=effect.claim_generation,
                    values={
                        "status": EFFECT_RECONCILED,
                        "reconciled_at": _utcnow(),
                    },
                )
            except ClaimGenerationConflict:
                continue

            task = await self.repo.get_task(effect.task_id)
            if task is not None and not is_terminal(TaskStatus(task.status)):
                if task.status != TaskStatus.RESULT_CONFIRMING.value:
                    try:
                        await self.runtime.transition_task(
                            task_id=task.id,
                            target_status=TaskStatus.RESULT_CONFIRMING,
                            expected_task_version=task.task_version,
                            execution_id=effect.execution_id,
                            expected_claim_generation=effect.claim_generation,
                            reason_category="unknown_result",
                            safe_message="外部结果待确认",
                            actor_type="system",
                            actor_id="recovery",
                        )
                    except Exception as exc:  # noqa: BLE001
                        log.warning(
                            "ai_runtime.recovery.result_confirming_failed",
                            task_id=str(task.id),
                            error=str(exc),
                        )
            reconciled += 1

        await self.session.flush()
        return reconciled

    # ------------------------------------------------------------------
    # Safe-point cancel / trusted checkpoint / quarantine / retry budget
    # ------------------------------------------------------------------

    DEFAULT_TASK_RETRY_BUDGET = 3

    async def complete_cancel_at_safe_point(
        self,
        *,
        task_id: UUID,
        safe_point: str = "before_provider",
        expected_task_version: int | None = None,
    ) -> AITask | None:
        """Finish ``cancelling`` → ``cancelled`` only at a declared safe point.

        Safe points are adapter-declared moments where no in-flight provider /
        tool side effect is owed. Recovery never invents a cancel mid-call.
        """
        task = await self.repo.get_task(task_id)
        if task is None:
            return None
        if task.status != TaskStatus.CANCELLING.value:
            return task
        if expected_task_version is not None and task.task_version != expected_task_version:
            return None
        allowed = {
            "before_provider",
            "before_tool",
            "before_publish",
            "before_domain_write",
            "before_delivery",
            "after_checkpoint",
        }
        if safe_point not in allowed:
            log.warning(
                "ai_runtime.recovery.unsafe_cancel_point",
                task_id=str(task_id),
                safe_point=safe_point,
            )
            return None
        try:
            return await self.runtime.transition_task(
                task_id=task.id,
                target_status=TaskStatus.CANCELLED,
                expected_task_version=task.task_version,
                reason_category="cancelled_at_safe_point",
                safe_message=f"cancelled at safe point: {safe_point}",
                actor_type="system",
                actor_id="recovery",
                payload={"safe_point": safe_point},
            )
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "ai_runtime.recovery.cancel_safe_point_failed",
                task_id=str(task_id),
                error=str(exc),
            )
            return None

    async def continue_from_trusted_checkpoint(
        self,
        *,
        task_id: UUID,
        checkpoint_ref: str | None = None,
        checkpoint_version: str | None = None,
        capability: str | None = None,
    ) -> AITask | None:
        """Resume from a trusted live-matrix checkpoint; quarantine otherwise."""
        from app.modules.ai_runtime.compatibility import (
            decode_or_quarantine,
            evaluate_artifact_version,
        )

        task = await self.repo.get_task(task_id)
        if task is None:
            return None
        if is_terminal(TaskStatus(task.status)):
            return task

        execution = None
        if task.current_execution_id is not None:
            execution = await self.repo.get_execution(task.current_execution_id)

        ref = checkpoint_ref or (execution.checkpoint_ref if execution else None)
        version = checkpoint_version or "1"
        cap = capability or task.capability_code

        if ref is None:
            # No checkpoint — re-queue for a clean dispatch rather than inventing state.
            if task.status in {
                TaskStatus.RETRY_WAIT.value,
                TaskStatus.RUNNING.value,
                TaskStatus.WAITING_USER.value,
            }:
                try:
                    return await self.runtime.transition_task(
                        task_id=task.id,
                        target_status=TaskStatus.QUEUED,
                        expected_task_version=task.task_version,
                        reason_category="checkpoint_missing_requeue",
                        safe_message="no trusted checkpoint; re-queued",
                        actor_type="system",
                        actor_id="recovery",
                    )
                except Exception as exc:  # noqa: BLE001
                    log.warning(
                        "ai_runtime.recovery.requeue_failed",
                        task_id=str(task_id),
                        error=str(exc),
                    )
            return task

        decision = evaluate_artifact_version(
            "checkpoint", version, capability=cap
        )
        if decision.action == "quarantine":
            await self.quarantine_deterministic_failure(
                task_id=task.id,
                reason=decision.reason,
                failure_category="checkpoint_quarantine",
                decision=decision,
            )
            return await self.repo.get_task(task_id)

        outcome = decode_or_quarantine(
            "checkpoint",
            {"checkpoint_ref": ref, "schema_version": version},
            version=version,
            capability=cap,
        )
        if outcome.action == "quarantine":
            await self.quarantine_deterministic_failure(
                task_id=task.id,
                reason=outcome.reason,
                failure_category="checkpoint_decode_quarantine",
                decision=outcome,
            )
            return await self.repo.get_task(task_id)

        if execution is not None and ref:
            execution.checkpoint_ref = ref
        try:
            return await self.runtime.transition_task(
                task_id=task.id,
                target_status=TaskStatus.QUEUED,
                expected_task_version=task.task_version,
                reason_category="trusted_checkpoint_continue",
                safe_message="continued from trusted checkpoint",
                actor_type="system",
                actor_id="recovery",
                payload={"checkpoint_ref": ref, "checkpoint_version": version},
            )
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "ai_runtime.recovery.checkpoint_continue_failed",
                task_id=str(task_id),
                error=str(exc),
            )
            return None

    async def quarantine_deterministic_failure(
        self,
        *,
        task_id: UUID,
        reason: str,
        failure_category: str = "deterministic_failure",
        decision: Any | None = None,
    ) -> AITask | None:
        """Move a non-terminal task to failed with a visible quarantine reason."""
        task = await self.repo.get_task(task_id)
        if task is None:
            return None
        if is_terminal(TaskStatus(task.status)):
            task.failure_category = task.failure_category or failure_category
            return task
        payload: dict[str, Any] = {
            "quarantine": True,
            "reason": reason,
            "failure_category": failure_category,
        }
        if decision is not None:
            payload["compatibility"] = {
                "action": getattr(decision, "action", None),
                "kind": getattr(decision, "kind", None),
                "from_version": getattr(decision, "from_version", None),
                "reason": getattr(decision, "reason", None),
            }
        try:
            updated = await self.runtime.transition_task(
                task_id=task.id,
                target_status=TaskStatus.FAILED,
                expected_task_version=task.task_version,
                reason_category=failure_category,
                safe_message=reason[:500],
                actor_type="system",
                actor_id="recovery",
                payload=payload,
            )
            updated.failure_category = failure_category
            await self.session.flush()
            return updated
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "ai_runtime.recovery.quarantine_failed",
                task_id=str(task_id),
                error=str(exc),
            )
            return None

    def retry_budget_remaining(
        self,
        execution: AIExecution,
        *,
        max_attempts: int | None = None,
    ) -> int:
        budget = max_attempts if max_attempts is not None else self.DEFAULT_TASK_RETRY_BUDGET
        used = int(execution.retry_attempt_count or 0)
        return max(0, int(budget) - used)

    async def consume_retry_budget(
        self,
        *,
        execution_id: UUID,
        max_attempts: int | None = None,
    ) -> tuple[AIExecution | None, bool]:
        """Increment retry_attempt_count when budget remains.

        Returns ``(execution, allowed)``. When exhausted, caller should
        quarantine or dead-letter rather than re-dispatch.
        """
        execution = await self.repo.get_execution(execution_id)
        if execution is None:
            return None, False
        if self.retry_budget_remaining(execution, max_attempts=max_attempts) <= 0:
            return execution, False
        execution.retry_attempt_count = int(execution.retry_attempt_count or 0) + 1
        await self.session.flush()
        return execution, True

    async def enqueue_task_recovery(
        self,
        redis: Any,
        *,
        task_id: UUID,
        reason: str = "recovery",
    ) -> str | None:
        """Best-effort enqueue of a per-task recovery job (transport projection)."""
        if redis is None:
            log.error(
                "ai_runtime.recovery.enqueue_skipped",
                task_id=str(task_id),
                reason="redis_unavailable",
            )
            return None
        try:
            job = await redis.enqueue_job(
                "recover_ai_task",
                str(task_id),
                reason,
            )
        except Exception as exc:  # noqa: BLE001
            log.error(
                "ai_runtime.recovery.enqueue_failed",
                task_id=str(task_id),
                error=str(exc),
            )
            return None
        if job is None:
            return None
        return str(getattr(job, "job_id", None) or job)

    async def recover_cancelling_tasks(self, *, limit: int = 50) -> int:
        """Complete safe-point cancellation for tasks stuck in ``cancelling``."""
        bounded = min(max(int(limit), 1), 500)
        result = await self.session.execute(
            select(AITask)
            .where(AITask.status == TaskStatus.CANCELLING.value)
            .order_by(AITask.updated_at)
            .limit(bounded)
            .with_for_update(skip_locked=True)
        )
        completed = 0
        for task in result.scalars().all():
            updated = await self.complete_cancel_at_safe_point(
                task_id=task.id,
                safe_point="before_provider",
                expected_task_version=task.task_version,
            )
            if updated is not None and updated.status == TaskStatus.CANCELLED.value:
                completed += 1
        await self.session.flush()
        return completed

    async def recover_retry_wait_tasks(self, *, limit: int = 50) -> int:
        """Promote due ``retry_wait`` tasks when budget remains; else quarantine."""
        bounded = min(max(int(limit), 1), 500)
        result = await self.session.execute(
            select(AITask)
            .where(AITask.status == TaskStatus.RETRY_WAIT.value)
            .order_by(AITask.updated_at)
            .limit(bounded)
            .with_for_update(skip_locked=True)
        )
        promoted = 0
        for task in result.scalars().all():
            execution = None
            if task.current_execution_id is not None:
                execution = await self.repo.get_execution(task.current_execution_id)
            if execution is None:
                continue
            execution, allowed = await self.consume_retry_budget(
                execution_id=execution.id
            )
            if not allowed:
                await self.quarantine_deterministic_failure(
                    task_id=task.id,
                    reason="task-level retry budget exhausted",
                    failure_category="retry_budget_exhausted",
                )
                continue
            try:
                await self.runtime.transition_task(
                    task_id=task.id,
                    target_status=TaskStatus.QUEUED,
                    expected_task_version=task.task_version,
                    reason_category="retry_budget_ok",
                    safe_message="retry budget remaining; re-queued",
                    actor_type="system",
                    actor_id="recovery",
                )
                promoted += 1
            except Exception as exc:  # noqa: BLE001
                log.warning(
                    "ai_runtime.recovery.retry_promote_failed",
                    task_id=str(task.id),
                    error=str(exc),
                )
        await self.session.flush()
        return promoted

    # ------------------------------------------------------------------
    # Composite recovery scan
    # ------------------------------------------------------------------

    async def run_recovery_scan(
        self,
        redis: Any | None = None,
        *,
        limit: int = 100,
        deliver: bool = True,
    ) -> RecoveryScanResult:
        """Reconcile stranded intents, expire tasks, renew claims, unknown effects."""
        recon = await self.reconcile_stranded_intents(limit=limit)
        expired = await self.scan_expired_tasks(limit=limit)
        renewed = await self.renew_execution_claims(limit=limit)
        unknown = await self.reconcile_unknown_effects(limit=limit)
        cancelled = await self.recover_cancelling_tasks(limit=limit)
        retried = await self.recover_retry_wait_tasks(limit=limit)
        delivered: DeliverResult | None = None
        if deliver:
            delivered = await self.deliver_pending_intents(redis, limit=limit)
        result = RecoveryScanResult(
            stranded_reset=recon["stranded_reset"],
            retry_due=recon["retry_due"] + retried,
            expired_tasks=expired,
            claims_renewed=renewed,
            unknown_effects=unknown + cancelled,
            delivered=delivered,
        )
        log.info(
            "ai_runtime.recovery.scanned",
            stranded_reset=result.stranded_reset,
            retry_due=result.retry_due,
            expired_tasks=result.expired_tasks,
            claims_renewed=result.claims_renewed,
            unknown_effects=result.unknown_effects,
            cancellations_completed=cancelled,
            retry_promoted=retried,
            delivered_claimed=delivered.claimed if delivered else 0,
        )
        return result


def create_recovery_service(
    session: AsyncSession,
    **kwargs: Any,
) -> RecoveryService:
    return RecoveryService(session, **kwargs)


__all__ = [
    "AdmissionDecision",
    "DEFAULT_CLAIM_TTL_SECONDS",
    "DEFAULT_MAX_DISPATCH_ATTEMPTS",
    "DEFAULT_MAX_RUNNING_EXECUTIONS",
    "DEFAULT_RETRY_DELAY_SECONDS",
    "DISPATCH_CONFIRMED",
    "DISPATCH_DEAD_LETTER",
    "DISPATCH_DISPATCHING",
    "DISPATCH_PENDING",
    "DISPATCH_RETRY_WAIT",
    "DeliverResult",
    "RecoveryScanResult",
    "RecoveryService",
    "create_recovery_service",
    "default_claim_owner",
]
