"""M22 — ai_messages repository for audit trail (T059)."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class AiMessageRepo:
    """CRUD for ai_messages append-only audit log."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        user_id: UUID,
        thread_id: str,
        checkpoint_ns: str = "",
        checkpoint_id: str | None = None,
        node_name: str,
        role: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        cache_hit: bool = False,
        duration_ms: int,
    ) -> UUID:
        row_id = uuid4()
        await self.session.execute(
            select(1)  # placeholder — full impl in T059
        )
        return row_id

    async def list_by_thread(
        self,
        thread_id: str,
        *,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> list:
        return []


__all__ = ["AiMessageRepo"]
