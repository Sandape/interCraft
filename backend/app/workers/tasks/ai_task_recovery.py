"""ARQ: periodic AI runtime recovery scan (REQ-061 T023 / T040)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.core.db import get_session_context, set_rls_user_id
from app.core.logging import get_logger
from app.modules.ai_runtime.recovery.service import RecoveryService, default_claim_owner
from app.modules.ai_runtime.state_machine import TaskStatus

log = get_logger("ai_runtime.recovery_worker")


async def scan_ai_task_recovery(
    ctx: dict[str, Any], *, max_count: int = 100
) -> dict[str, Any]:
    """Reconcile stranded intents, expire tasks, renew claims, unknown effects.

    Also completes safe-point cancellations, promotes retry_wait under budget,
    and best-effort delivers pending dispatch intents when Redis is present.
    """
    bounded = min(max(int(max_count), 1), 1000)
    redis = ctx.get("redis")
    owner = default_claim_owner()

    async with get_session_context() as session:
        recovery = RecoveryService(session, claim_owner=owner)
        result = await recovery.run_recovery_scan(
            redis, limit=bounded, deliver=True
        )

    payload: dict[str, Any] = {
        "stranded_reset": result.stranded_reset,
        "retry_due": result.retry_due,
        "expired_tasks": result.expired_tasks,
        "claims_renewed": result.claims_renewed,
        "unknown_effects": result.unknown_effects,
    }
    if result.delivered is not None:
        payload.update(
            {
                "claimed": result.delivered.claimed,
                "enqueued": result.delivered.enqueued,
                "dead_lettered": result.delivered.dead_lettered,
                "admission_rejected": result.delivered.admission_rejected,
            }
        )
    log.info("ai_runtime.recovery.scan_complete", **payload)
    return payload


async def recover_ai_task(
    ctx: dict[str, Any],
    task_id: str,
    reason: str = "recovery",
) -> dict[str, Any]:
    """Per-task recovery: safe-point cancel, trusted checkpoint, or retry budget."""
    _ = ctx
    tid = UUID(str(task_id))
    owner = default_claim_owner()

    async with get_session_context() as session:
        recovery = RecoveryService(session, claim_owner=owner)
        task = await recovery.repo.get_task(tid)
        if task is None:
            return {"task_id": str(tid), "status": "not_found", "reason": reason}

        await set_rls_user_id(session, task.user_id)
        task = await recovery.repo.get_task(tid)
        if task is None:
            return {"task_id": str(tid), "status": "not_found", "reason": reason}

        actions: list[str] = []
        if task.status == "cancelling":
            updated = await recovery.complete_cancel_at_safe_point(task_id=tid)
            actions.append("cancel_at_safe_point")
            status = updated.status if updated else task.status
        elif task.status == "retry_wait":
            execution = None
            if task.current_execution_id is not None:
                execution = await recovery.repo.get_execution(task.current_execution_id)
            if execution is None:
                actions.append("retry_budget_skip")
                status = task.status
            else:
                execution, allowed = await recovery.consume_retry_budget(
                    execution_id=execution.id
                )
                if not allowed:
                    await recovery.quarantine_deterministic_failure(
                        task_id=tid,
                        reason="task-level retry budget exhausted",
                        failure_category="retry_budget_exhausted",
                    )
                    actions.append("retry_budget_exhausted")
                else:
                    await recovery.runtime.transition_task(
                        task_id=tid,
                        target_status=TaskStatus.QUEUED,
                        expected_task_version=task.task_version,
                        reason_category="retry_budget_ok",
                        safe_message="retry budget remaining; re-queued",
                        actor_type="system",
                        actor_id="recovery",
                    )
                    actions.append("retry_budget_promote")
                refreshed = await recovery.repo.get_task(tid)
                status = refreshed.status if refreshed else task.status
        elif task.status in {"running", "waiting_user", "result_confirming"}:
            updated = await recovery.continue_from_trusted_checkpoint(task_id=tid)
            actions.append("trusted_checkpoint_continue")
            status = updated.status if updated else task.status
        else:
            status = task.status

        await session.commit()
        payload = {
            "task_id": str(tid),
            "status": status,
            "reason": reason,
            "actions": actions,
        }
        log.info("ai_runtime.recovery.task_complete", **payload)
        return payload


__all__ = ["recover_ai_task", "scan_ai_task_recovery"]
