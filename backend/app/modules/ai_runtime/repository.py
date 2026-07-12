"""REQ-061 AI Runtime repositories with claim_generation CAS (T018)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Sequence
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ids import new_uuid_v7
from app.modules.ai_runtime.models import (
    AIDispatchIntent,
    AIExecution,
    AIExternalEffectIntent,
    AIMilestone,
    AITask,
    AITaskEvent,
)
from app.modules.ai_runtime.state_machine import (
    TaskStatus,
    append_task_event,
    available_actions_for,
    is_terminal,
    next_event_sequence,
    validate_task_transition,
)


class ClaimGenerationConflict(Exception):
    """Raised when a CAS against claim_generation fails."""


class TaskVersionConflict(Exception):
    """Raised when expected_task_version does not match."""


class AIRuntimeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_task(self, task_id: UUID) -> AITask | None:
        result = await self.session.execute(select(AITask).where(AITask.id == task_id))
        return result.scalar_one_or_none()

    async def get_execution(self, execution_id: UUID) -> AIExecution | None:
        result = await self.session.execute(
            select(AIExecution).where(AIExecution.id == execution_id)
        )
        return result.scalar_one_or_none()

    async def list_task_event_sequences(self, task_id: UUID) -> list[int]:
        result = await self.session.execute(
            select(AITaskEvent.sequence)
            .where(AITaskEvent.task_id == task_id)
            .order_by(AITaskEvent.sequence)
        )
        return list(result.scalars().all())

    async def append_event(
        self,
        *,
        task: AITask,
        event_type: str,
        from_status: str | None,
        to_status: str | None,
        payload: dict[str, Any] | None = None,
        execution_id: UUID | None = None,
        actor_type: str = "system",
        actor_id: str | None = None,
        idempotency_key: str | None = None,
        correlation_id: str | None = None,
        reason_category: str | None = None,
        safe_message: str | None = None,
    ) -> AITaskEvent:
        existing = await self.list_task_event_sequences(task.id)
        sequence = next_event_sequence(existing)
        append_task_event(existing_sequences=existing, new_sequence=sequence)
        event = AITaskEvent(
            id=new_uuid_v7(),
            task_id=task.id,
            root_task_id=task.id,
            execution_id=execution_id or task.current_execution_id,
            user_id=task.user_id,
            sequence=sequence,
            event_type=event_type,
            from_status=from_status,
            to_status=to_status,
            actor_type=actor_type,
            actor_id=actor_id,
            idempotency_key=idempotency_key or f"{task.id}:{sequence}:{event_type}",
            correlation_id=correlation_id,
            reason_category=reason_category,
            safe_message=safe_message,
            payload=payload or {},
            payload_summary=payload or {},
        )
        self.session.add(event)
        await self.session.flush()
        return event

    async def cas_execution_claim(
        self,
        *,
        execution_id: UUID,
        expected_claim_generation: int,
        values: dict[str, Any],
    ) -> AIExecution:
        """Update execution only when claim_generation matches (optimistic fence)."""
        stmt = (
            update(AIExecution)
            .where(
                AIExecution.id == execution_id,
                AIExecution.claim_generation == expected_claim_generation,
            )
            .values(**values)
            .returning(AIExecution.id)
        )
        result = await self.session.execute(stmt)
        row = result.first()
        if row is None:
            raise ClaimGenerationConflict(
                f"execution {execution_id} claim_generation "
                f"{expected_claim_generation} mismatch"
            )
        await self.session.flush()
        execution = await self.get_execution(execution_id)
        assert execution is not None
        return execution

    async def bump_claim_generation(
        self,
        *,
        execution_id: UUID,
        expected_claim_generation: int,
        claim_owner: str,
        claim_expires_at: datetime,
    ) -> AIExecution:
        return await self.cas_execution_claim(
            execution_id=execution_id,
            expected_claim_generation=expected_claim_generation,
            values={
                "claim_generation": expected_claim_generation + 1,
                "claim_owner": claim_owner,
                "claim_expires_at": claim_expires_at,
                "updated_at": datetime.now(timezone.utc),
            },
        )

    async def cas_dispatch_intent(
        self,
        *,
        intent_id: UUID,
        expected_claim_generation: int,
        values: dict[str, Any],
    ) -> AIDispatchIntent:
        stmt = (
            update(AIDispatchIntent)
            .where(
                AIDispatchIntent.id == intent_id,
                AIDispatchIntent.claim_generation == expected_claim_generation,
            )
            .values(**values, updated_at=datetime.now(timezone.utc))
            .returning(AIDispatchIntent.id)
        )
        result = await self.session.execute(stmt)
        if result.first() is None:
            raise ClaimGenerationConflict(
                f"dispatch intent {intent_id} claim_generation mismatch"
            )
        await self.session.flush()
        loaded = await self.session.execute(
            select(AIDispatchIntent).where(AIDispatchIntent.id == intent_id)
        )
        intent = loaded.scalar_one()
        return intent

    async def cas_effect_intent_transition(
        self,
        *,
        intent_id: UUID,
        execution_id: UUID,
        expected_claim_generation: int,
        values: dict[str, Any],
    ) -> AIExternalEffectIntent:
        """Adopt/transition an effect intent only under the current execution fence."""
        exec_check = await self.session.execute(
            select(AIExecution.claim_generation).where(AIExecution.id == execution_id)
        )
        current_gen = exec_check.scalar_one_or_none()
        if current_gen != expected_claim_generation:
            raise ClaimGenerationConflict(
                f"effect intent adopt rejected; execution fence is {current_gen}, "
                f"expected {expected_claim_generation}"
            )
        stmt = (
            update(AIExternalEffectIntent)
            .where(
                AIExternalEffectIntent.id == intent_id,
                AIExternalEffectIntent.claim_generation == expected_claim_generation,
            )
            .values(**values)
            .returning(AIExternalEffectIntent.id)
        )
        result = await self.session.execute(stmt)
        if result.first() is None:
            raise ClaimGenerationConflict(
                f"effect intent {intent_id} claim_generation mismatch"
            )
        await self.session.flush()
        loaded = await self.session.execute(
            select(AIExternalEffectIntent).where(AIExternalEffectIntent.id == intent_id)
        )
        return loaded.scalar_one()

    async def list_milestones(self, execution_id: UUID) -> Sequence[AIMilestone]:
        result = await self.session.execute(
            select(AIMilestone).where(AIMilestone.execution_id == execution_id)
        )
        return list(result.scalars().all())
