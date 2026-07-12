"""PostgreSQL persistence adapters for Tool execution and confirmation."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.agent.models import AgentToolExecution, WeChatBinding
from app.modules.agent.runtime.confirmations import ConfirmationService
from app.modules.agent.runtime.orchestrator import ExecutionRecord
from app.modules.agent.tools.result import ToolResult, ToolResultStatus


class StaleExecutionClaimError(RuntimeError):
    pass


class SqlExecutionStore:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def propose(self, record: ExecutionRecord) -> bool:
        inserted = await self.session.scalar(
            insert(AgentToolExecution)
            .values(
                id=record.id,
                task_id=record.task_id,
                user_id=record.user_id,
                tool_call_id=record.tool_call_id,
                tool_name=record.tool_name,
                tool_version=record.tool_version,
                args_hash=record.args_hash,
                args_json=record.arguments,
                idempotency_key=record.idempotency_key,
                side_effect=record.side_effect,
                atomicity=record.atomicity,
                status="awaiting_confirmation" if record.requires_confirmation else "running",
                attempt_count=0,
                claim_generation=record.claim_generation,
                binding_id=record.binding_id,
                binding_epoch=record.binding_epoch,
                started_at=None if record.requires_confirmation else datetime.now(UTC),
            )
            .on_conflict_do_nothing()
            .returning(AgentToolExecution.id)
        )
        return inserted is not None

    async def complete(self, record: ExecutionRecord, result: ToolResult) -> None:
        status = {
            ToolResultStatus.SUCCEEDED: "succeeded",
            ToolResultStatus.RETRYABLE_ERROR: "retry_wait",
            ToolResultStatus.CANCELLED: "cancelled",
            ToolResultStatus.UNKNOWN_RESULT: "unknown_result",
        }.get(result.status, "failed")
        now = datetime.now(UTC)
        statement = (
            update(AgentToolExecution)
            .where(
                AgentToolExecution.id == record.id,
                AgentToolExecution.user_id == record.user_id,
                AgentToolExecution.binding_epoch == record.binding_epoch,
                AgentToolExecution.claim_generation == record.claim_generation,
                select(WeChatBinding.id)
                .where(
                    WeChatBinding.id == record.binding_id,
                    WeChatBinding.user_id == record.user_id,
                    WeChatBinding.unbound_at.is_(None),
                    WeChatBinding.binding_epoch == record.binding_epoch,
                )
                .exists(),
            )
            .values(
                status=status,
                result_json=result.model_dump(mode="json", exclude_none=True),
                error_category=result.error.category if result.error else None,
                committed_at=result.committed_at,
                finished_at=now,
            )
        )
        changed = await self.session.execute(statement)
        if changed.rowcount != 1:
            raise StaleExecutionClaimError("Tool execution lost claim or binding authority")


class SqlConfirmationIssuer:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def issue(self, record: ExecutionRecord) -> str:
        issued = await ConfirmationService(
            self.session, user_id=record.user_id
        ).issue(
            task_id=record.task_id,
            tool_execution_id=record.id,
            args_hash=record.args_hash,
            binding_id=record.binding_id,
            binding_epoch=record.binding_epoch,
        )
        return issued.token


__all__ = ["SqlConfirmationIssuer", "SqlExecutionStore", "StaleExecutionClaimError"]
