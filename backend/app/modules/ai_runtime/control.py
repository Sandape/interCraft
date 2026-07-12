"""REQ-061 durable task control commands (T039)."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ids import new_uuid_v7
from app.modules.ai_runtime.models import AIDispatchIntent, AIExecution, AITask
from app.modules.ai_runtime.repository import TaskVersionConflict
from app.modules.ai_runtime.service import AIRuntimeService
from app.modules.ai_runtime.state_machine import (
    InvalidTransition,
    TaskStatus,
    available_actions_for,
    is_terminal,
)


class ControlError(Exception):
    def __init__(self, code: str, message: str, status: int = 409) -> None:
        self.code = code
        self.message = message
        self.status = status
        super().__init__(message)


class ControlService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.runtime = AIRuntimeService(session)

    async def _load_owned(self, task_id: UUID, user_id: UUID) -> AITask:
        task = await self.runtime.repo.get_task(task_id)
        if task is None or task.user_id != user_id:
            raise ControlError("NOT_FOUND", "task not found", 404)
        return task

    def _require_version(self, task: AITask, expected: int) -> None:
        if task.task_version != expected:
            raise ControlError(
                "VERSION_CONFLICT",
                f"expected version {expected}, current {task.task_version}",
                409,
            )

    def _require_action(self, task: AITask, action: str) -> None:
        actions = set(task.available_actions or [])
        if action not in actions:
            raise ControlError(
                "ACTION_NOT_ALLOWED",
                f"action {action} not available in status {task.status}",
                409,
            )

    async def cancel(
        self,
        *,
        task_id: UUID,
        user_id: UUID,
        expected_task_version: int,
        reason: str | None = None,
    ) -> AITask:
        task = await self._load_owned(task_id, user_id)
        self._require_version(task, expected_task_version)
        self._require_action(task, "cancel")
        # accepted may go directly to cancelled; in-flight states enter cancelling.
        target = (
            TaskStatus.CANCELLED
            if task.status == TaskStatus.ACCEPTED.value
            else TaskStatus.CANCELLING
        )
        try:
            return await self.runtime.transition_task(
                task_id=task.id,
                target_status=target,
                expected_task_version=expected_task_version,
                safe_message=reason or "cancel requested",
                actor_type="user",
                actor_id=str(user_id),
                payload={"control": "cancel"},
            )
        except (InvalidTransition, TaskVersionConflict) as exc:
            code = (
                "VERSION_CONFLICT"
                if isinstance(exc, TaskVersionConflict)
                else "INVALID_TRANSITION"
            )
            raise ControlError(code, str(exc), 409) from exc

    async def resume(
        self,
        *,
        task_id: UUID,
        user_id: UUID,
        expected_task_version: int,
        user_input_ref: str | None = None,
    ) -> AITask:
        task = await self._load_owned(task_id, user_id)
        self._require_version(task, expected_task_version)
        self._require_action(task, "resume")
        updated = await self.runtime.transition_task(
            task_id=task.id,
            target_status=TaskStatus.QUEUED,
            expected_task_version=expected_task_version,
            safe_message="resume requested",
            actor_type="user",
            actor_id=str(user_id),
            payload={"control": "resume", "user_input_ref": user_input_ref},
        )
        await self._enqueue_dispatch(updated, kind="resume")
        return updated

    async def system_failure_retry(
        self,
        *,
        task_id: UUID,
        user_id: UUID,
        expected_task_version: int,
        reason: str | None = None,
    ) -> tuple[AITask, AIExecution]:
        task = await self._load_owned(task_id, user_id)
        self._require_version(task, expected_task_version)
        self._require_action(task, "system_failure_retry")
        if task.status != TaskStatus.FAILED.value:
            raise ControlError("INVALID_STATE", "system_failure_retry requires failed", 409)

        source_id = task.current_execution_id
        execution = AIExecution(
            id=new_uuid_v7(),
            task_id=task.id,
            root_task_id=task.id,
            user_id=user_id,
            execution_no=await self._next_execution_no(task.id),
            trigger_kind="system_failure_retry",
            source_execution_id=source_id,
            status=TaskStatus.QUEUED.value,
            claim_generation=1,
            started_at=datetime.now(timezone.utc),
        )
        self.session.add(execution)
        await self.session.flush()
        task.current_execution_id = execution.id
        task.status = TaskStatus.QUEUED.value
        task.task_version += 1
        task.available_actions = available_actions_for(TaskStatus.QUEUED, terminal=False)
        task.updated_at = datetime.now(timezone.utc)
        await self.runtime.repo.append_event(
            task=task,
            event_type="ai.task.system_failure_retry",
            from_status=TaskStatus.FAILED.value,
            to_status=TaskStatus.QUEUED.value,
            safe_message=reason or "system failure retry",
            actor_type="user",
            actor_id=str(user_id),
            execution_id=execution.id,
            payload={"control": "system_failure_retry"},
        )
        await self._enqueue_dispatch(task, kind="retry", execution_id=execution.id)
        return task, execution

    async def reexecute(
        self,
        *,
        task_id: UUID,
        user_id: UUID,
        expected_task_version: int,
        input_mode: str,
        behavior_mode: str,
        quote_id: UUID,
    ) -> tuple[AITask, AIExecution]:
        task = await self._load_owned(task_id, user_id)
        self._require_version(task, expected_task_version)
        self._require_action(task, "reexecute")
        if not is_terminal(TaskStatus(task.status)):
            raise ControlError("INVALID_STATE", "reexecute requires terminal task", 409)

        execution = AIExecution(
            id=new_uuid_v7(),
            task_id=task.id,
            root_task_id=task.id,
            user_id=user_id,
            execution_no=await self._next_execution_no(task.id),
            trigger_kind="user_reexecute",
            source_execution_id=task.current_execution_id,
            input_mode=input_mode,
            behavior_mode=behavior_mode,
            status=TaskStatus.ACCEPTED.value,
            claim_generation=1,
            started_at=datetime.now(timezone.utc),
        )
        self.session.add(execution)
        await self.session.flush()
        from_status = task.status
        task.current_execution_id = execution.id
        task.quote_id = quote_id
        task.status = TaskStatus.ACCEPTED.value
        task.terminal_at = None
        task.task_version += 1
        task.available_actions = available_actions_for(TaskStatus.ACCEPTED, terminal=False)
        task.updated_at = datetime.now(timezone.utc)
        await self.runtime.repo.append_event(
            task=task,
            event_type="ai.task.reexecuted",
            from_status=from_status,
            to_status=TaskStatus.ACCEPTED.value,
            safe_message="re-execution created",
            actor_type="user",
            actor_id=str(user_id),
            execution_id=execution.id,
            payload={
                "control": "reexecute",
                "input_mode": input_mode,
                "behavior_mode": behavior_mode,
                "quote_id": str(quote_id),
            },
        )
        await self._enqueue_dispatch(task, kind="initial", execution_id=execution.id)
        return task, execution

    async def _next_execution_no(self, task_id: UUID) -> int:
        from sqlalchemy import func, select

        result = await self.session.execute(
            select(func.coalesce(func.max(AIExecution.execution_no), 0)).where(
                AIExecution.task_id == task_id
            )
        )
        return int(result.scalar_one()) + 1

    async def _enqueue_dispatch(
        self,
        task: AITask,
        *,
        kind: str,
        execution_id: UUID | None = None,
    ) -> None:
        exec_id = execution_id or task.current_execution_id
        if exec_id is None:
            return
        self.session.add(
            AIDispatchIntent(
                id=new_uuid_v7(),
                task_id=task.id,
                execution_id=exec_id,
                root_task_id=task.id,
                user_id=task.user_id,
                dispatch_kind=kind,
                payload_schema_version="1",
                behavior_version="1",
                status="pending",
                idempotency_key=f"dispatch:{kind}:{exec_id}:{task.task_version}",
                claim_generation=1,
            )
        )
        await self.session.flush()


__all__ = ["ControlError", "ControlService", "TaskVersionConflict"]
