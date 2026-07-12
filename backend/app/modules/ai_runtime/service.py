"""REQ-061 AI Runtime state service — FSM + event append + CAS (T018)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ai_runtime.repository import (
    AIRuntimeRepository,
    ClaimGenerationConflict,
    TaskVersionConflict,
)
from app.modules.ai_runtime.state_machine import (
    TaskStatus,
    available_actions_for,
    decide_failure_policy,
    is_terminal,
    validate_task_transition,
)


class AIRuntimeService:
    """Transaction-safe task state transitions with optimistic versioning."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = AIRuntimeRepository(session)

    async def transition_task(
        self,
        *,
        task_id: UUID,
        target_status: TaskStatus | str,
        expected_task_version: int | None = None,
        execution_id: UUID | None = None,
        expected_claim_generation: int | None = None,
        reason_category: str | None = None,
        safe_message: str | None = None,
        payload: dict[str, Any] | None = None,
        actor_type: str = "system",
        actor_id: str | None = None,
    ):
        task = await self.repo.get_task(task_id)
        if task is None:
            raise LookupError(f"task {task_id} not found")
        if expected_task_version is not None and task.task_version != expected_task_version:
            raise TaskVersionConflict(
                f"task version {task.task_version} != expected {expected_task_version}"
            )

        current = TaskStatus(task.status)
        target = TaskStatus(target_status)
        validate_task_transition(current, target)

        if execution_id is not None and expected_claim_generation is not None:
            await self.repo.cas_execution_claim(
                execution_id=execution_id,
                expected_claim_generation=expected_claim_generation,
                values={"updated_at": datetime.now(timezone.utc)},
            )

        from_status = task.status
        task.status = target.value
        task.task_version += 1
        task.updated_at = datetime.now(timezone.utc)
        terminal = is_terminal(target)
        if terminal:
            task.terminal_at = datetime.now(timezone.utc)
        if reason_category:
            task.failure_category = reason_category
        if safe_message:
            task.user_summary = safe_message
        task.available_actions = available_actions_for(target, terminal=terminal)

        await self.repo.append_event(
            task=task,
            event_type="ai.task.state_changed",
            from_status=from_status,
            to_status=target.value,
            execution_id=execution_id,
            actor_type=actor_type,
            actor_id=actor_id,
            reason_category=reason_category,
            safe_message=safe_message,
            payload=payload or {"to_status": target.value},
        )
        await self.session.flush()
        return task

    async def adopt_effect_result(
        self,
        *,
        execution_id: UUID,
        effect_intent_id: UUID,
        expected_claim_generation: int,
        status: str,
        provider_request_id: str | None = None,
        result_evidence_ref: str | None = None,
    ):
        """CAS-adopt an external effect under the current claim fence."""
        values: dict[str, Any] = {
            "status": status,
            "adopted_at": datetime.now(timezone.utc),
        }
        if provider_request_id is not None:
            values["provider_request_id"] = provider_request_id
        if result_evidence_ref is not None:
            values["result_evidence_ref"] = result_evidence_ref
        return await self.repo.cas_effect_intent_transition(
            intent_id=effect_intent_id,
            execution_id=execution_id,
            expected_claim_generation=expected_claim_generation,
            values=values,
        )

    async def renew_execution_claim(
        self,
        *,
        execution_id: UUID,
        expected_claim_generation: int,
        claim_owner: str,
        claim_expires_at: datetime,
    ):
        return await self.repo.bump_claim_generation(
            execution_id=execution_id,
            expected_claim_generation=expected_claim_generation,
            claim_owner=claim_owner,
            claim_expires_at=claim_expires_at,
        )

    def classify_failure(
        self,
        category: str,
        *,
        attempt: int,
        max_attempts: int,
        effect_started: bool = False,
    ):
        return decide_failure_policy(
            category,
            attempt=attempt,
            max_attempts=max_attempts,
            effect_started=effect_started,
        )


__all__ = [
    "AIRuntimeService",
    "ClaimGenerationConflict",
    "TaskVersionConflict",
]
