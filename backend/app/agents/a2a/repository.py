"""A2AMessageRepository — DB persistence for ``a2a_messages`` (REQ-031 US1, T007).

Used by :class:`~app.agents.a2a.DelegationRunner` to persist each
delegation's outcome. All methods are async (SQLAlchemy 2.0 async
session); callers must hold the session open for the lifetime of the
repository (mirrors the pattern in
``backend/app/modules/agent_memory/repository.py``).
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.a2a.models import A2AMessage
from app.agents.a2a.schemas import A2AMessageStatus


class A2AMessageRepository:
    """Persistence helper for the ``a2a_messages`` table."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        trace_id: str,
        thread_id: str,
        parent_agent: str,
        child_agent: str,
        task: str,
        context: dict[str, Any] | None = None,
        expected_output: dict[str, Any] | None = None,
        status: A2AMessageStatus = A2AMessageStatus.PENDING,
    ) -> A2AMessage:
        """Insert a new pending A2A message; returns the persisted ORM row."""
        row = A2AMessage(
            trace_id=trace_id,
            thread_id=thread_id,
            parent_agent=parent_agent,
            child_agent=child_agent,
            task=task,
            context_jsonb=context or {},
            expected_output_jsonb=expected_output or {},
            status=status.value if isinstance(status, A2AMessageStatus) else status,
        )
        self.session.add(row)
        await self.session.flush()
        await self.session.refresh(row)
        return row

    async def update_status(
        self,
        message_id: UUID,
        *,
        status: A2AMessageStatus,
        result: dict[str, Any] | None = None,
        error_reason: str | None = None,
        duration_ms: int | None = None,
        retry_count: int | None = None,
    ) -> A2AMessage | None:
        """Update the terminal status of a delegation row."""
        row = await self.session.get(A2AMessage, message_id)
        if row is None:
            return None
        row.status = status.value if isinstance(status, A2AMessageStatus) else status
        if result is not None:
            row.result_jsonb = result
        if error_reason is not None:
            row.error_reason = error_reason
        if duration_ms is not None:
            row.duration_ms = duration_ms
        if retry_count is not None:
            row.retry_count = retry_count
        await self.session.flush()
        await self.session.refresh(row)
        return row

    async def list_for_thread(self, thread_id: str, limit: int = 50) -> list[A2AMessage]:
        """List all A2A messages for one thread, oldest first."""
        stmt = (
            select(A2AMessage)
            .where(A2AMessage.thread_id == thread_id)
            .order_by(A2AMessage.created_at.asc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_for_trace(self, trace_id: str, limit: int = 200) -> list[A2AMessage]:
        """List all A2A messages for one trace, oldest first.

        Used by debug dashboards to reconstruct a multi-agent
        invocation (FR-018).
        """
        stmt = (
            select(A2AMessage)
            .where(A2AMessage.trace_id == trace_id)
            .order_by(A2AMessage.created_at.asc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


__all__ = ["A2AMessageRepository"]