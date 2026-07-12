"""Independent task claims for work that outlives the channel poll lease."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.agent.models import AgentTask, WeChatBinding
from app.modules.agent.repository import AgentTaskRepository
from app.modules.agent.runtime.telemetry import record_metric


class AgentTaskWorker:
    def __init__(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        owner_id: UUID,
        claim_seconds: int,
    ) -> None:
        self.user_id = user_id
        self.owner_id = owner_id
        self.claim_seconds = claim_seconds
        self.session = session
        self.repository = AgentTaskRepository(session)

    async def _record_rejection(self, task: AgentTask | None) -> None:
        if task is not None:
            active_binding = await self.session.scalar(
                select(WeChatBinding.id).where(
                    WeChatBinding.id == task.binding_id,
                    WeChatBinding.user_id == self.user_id,
                    WeChatBinding.binding_epoch == task.binding_epoch,
                    WeChatBinding.unbound_at.is_(None),
                )
            )
            if active_binding is None:
                record_metric("agent_binding_epoch_rejected_total", layer="task")
                return
        record_metric("agent_stale_claim_rejected_total", layer="task")

    async def claim(self, task_id: UUID) -> AgentTask | None:
        claimed = await self.repository.claim_task(
            self.user_id,
            task_id,
            owner_id=self.owner_id,
            claim_seconds=self.claim_seconds,
        )
        if claimed is None:
            task = await self.session.scalar(
                select(AgentTask).where(
                    AgentTask.id == task_id,
                    AgentTask.user_id == self.user_id,
                )
            )
            await self._record_rejection(task)
        return claimed

    async def transition(
        self,
        task: AgentTask,
        *,
        to_status: str,
        stage: str,
    ) -> AgentTask | None:
        transitioned = await self.repository.transition_claimed(
            self.user_id,
            task.id,
            owner_id=self.owner_id,
            claim_generation=task.claim_generation,
            binding_epoch=task.binding_epoch,
            from_status=task.status,
            to_status=to_status,
            stage=stage,
        )
        if transitioned is None:
            await self._record_rejection(task)
        return transitioned

    async def request_cancel(self, task_id: UUID) -> AgentTask | None:
        """Record cooperative cancellation without rolling back committed effects."""
        return await self.repository.request_cancel(self.user_id, task_id)

    async def resume(self, task_id: UUID) -> AgentTask | None:
        """Create a compatible, binding-valid resume lineage."""
        return await self.repository.resume_task(self.user_id, task_id)

    async def recover_expired(
        self, task_id: UUID, *, max_attempts: int
    ) -> AgentTask | None:
        """Recover an expired claim or require reconciliation before replay."""
        return await self.repository.recover_expired_task(
            self.user_id, task_id, max_attempts=max_attempts
        )


__all__ = ["AgentTaskWorker"]
