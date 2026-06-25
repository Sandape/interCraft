"""AgentMemoryRepository — CRUD + latest-wins conflict resolution.

Per spec FR-007: "Memory extraction MUST deduplicate and resolve conflicting
memories (latest-wins with superseded marker on the old)."

The upsert path:
  1. SELECT existing `active` row for (user_id, fact_key).
  2. If exists and fact_value differs:
     - UPDATE old row: status='superseded', superseded_at=now(), superseded_by=new_id.
     - INSERT new row: status='active', version=old.version+1.
  3. If exists and fact_value identical: no-op (idempotent).
  4. If not exists: INSERT new row: status='active', version=1.

Step 4 relies on the partial unique index
`uq_semantic_memories_active_user_key` to prevent races; concurrent inserts
of the same (user_id, fact_key) would raise UniqueViolation, which the
caller can retry or ignore.

RLS: caller must `SET LOCAL app.user_id = <user_id>` before invoking any
method. The repository does NOT set the GUC itself — keeps it composable
with the caller's existing transaction boundary (mirrors
`ability_profile.repository`).
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ids import new_uuid_v7
from app.modules.agent_memory.models import MemoryRetrievalLog, SemanticMemory

logger = structlog.get_logger(__name__)


class AgentMemoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ── SemanticMemory upsert (latest-wins) ──────────────────────────────────

    async def upsert_semantic_memory(
        self,
        *,
        user_id: UUID,
        fact_key: str,
        fact_value: str,
        confidence: float = 0.5,
        source: str = "extracted_from_llm_output",
        schema_version: int = 1,
        meta: dict | None = None,
    ) -> SemanticMemory:
        """Insert a new fact or supersede the existing active row.

        Returns the active row (either the newly inserted one or the
        pre-existing one if the value was identical — idempotent).
        """
        meta = meta or {}
        existing = await self._get_active(user_id, fact_key)

        if existing is not None:
            if existing.fact_value == fact_value:
                # Idempotent: same value, no-op.
                logger.info(
                    "memory.upsert.noop_same_value",
                    user_id=str(user_id),
                    fact_key=fact_key,
                )
                return existing

            # Supersede the old row. We must respect TWO constraints:
            #   1. Partial UNIQUE (user_id, fact_key) WHERE status='active':
            #      only one active row per (user_id, fact_key) at a time.
            #      → Must flip the old row to 'superseded' BEFORE inserting
            #        the new 'active' row.
            #   2. Self-referencing FK superseded_by → semantic_memories.id:
            #      the new row must exist BEFORE the old row's superseded_by
            #      can point at it.
            #      → Must INSERT the new row BEFORE updating superseded_by.
            #
            # Solution: 3-step sequence.
            #   (a) UPDATE old row: status='superseded', superseded_at=now()
            #       (superseded_by stays NULL — releases the unique constraint)
            #   (b) INSERT new row: status='active', version=old.version+1
            #   (c) UPDATE old row: superseded_by=new_id (FK now satisfiable)
            new_id = new_uuid_v7()
            now = datetime.now(timezone.utc)

            # Step (a): flip old row to 'superseded'. This releases the
            # partial unique constraint so step (b) can INSERT.
            await self.session.execute(
                update(SemanticMemory)
                .where(SemanticMemory.id == existing.id)
                .values(
                    status="superseded",
                    superseded_at=now,
                )
            )

            # Step (b): INSERT the new active row.
            new_row = SemanticMemory(
                id=new_id,
                user_id=user_id,
                fact_key=fact_key,
                fact_value=fact_value,
                confidence=confidence,
                source=source,
                version=existing.version + 1,
                status="active",
                schema_version=schema_version,
                meta=meta,
            )
            self.session.add(new_row)
            await self.session.flush()  # persists new_row, populates server defaults

            # Step (c): backfill superseded_by on the old row. The FK
            # superseded_by → semantic_memories.id is now satisfiable because
            # the new row exists.
            await self.session.execute(
                update(SemanticMemory)
                .where(SemanticMemory.id == existing.id)
                .values(superseded_by=new_id)
            )
            await self.session.flush()
            await self.session.refresh(new_row)
            logger.info(
                "memory.upsert.superseded",
                user_id=str(user_id),
                fact_key=fact_key,
                old_version=existing.version,
                new_version=new_row.version,
            )
            return new_row

        # First version.
        new_row = SemanticMemory(
            id=new_uuid_v7(),
            user_id=user_id,
            fact_key=fact_key,
            fact_value=fact_value,
            confidence=confidence,
            source=source,
            version=1,
            status="active",
            schema_version=schema_version,
            meta=meta,
        )
        self.session.add(new_row)
        await self.session.flush()
        await self.session.refresh(new_row)
        logger.info(
            "memory.upsert.inserted",
            user_id=str(user_id),
            fact_key=fact_key,
        )
        return new_row

    async def _get_active(
        self, user_id: UUID, fact_key: str
    ) -> SemanticMemory | None:
        stmt = select(SemanticMemory).where(
            SemanticMemory.user_id == user_id,
            SemanticMemory.fact_key == fact_key,
            SemanticMemory.status == "active",
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    # ── Retrieval ─────────────────────────────────────────────────────────────

    async def list_active_memories(
        self, user_id: UUID, *, limit: int = 50
    ) -> list[SemanticMemory]:
        """Return all active semantic memories for a user, newest first."""
        stmt = (
            select(SemanticMemory)
            .where(
                SemanticMemory.user_id == user_id,
                SemanticMemory.status == "active",
            )
            .order_by(SemanticMemory.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_all_memories(
        self, user_id: UUID, *, include_superseded: bool = False, limit: int = 100
    ) -> list[SemanticMemory]:
        """Return all memories for a user (US4 list API)."""
        stmt = select(SemanticMemory).where(SemanticMemory.user_id == user_id)
        if not include_superseded:
            stmt = stmt.where(SemanticMemory.status == "active")
        stmt = stmt.order_by(SemanticMemory.created_at.desc()).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def delete_memory(self, memory_id: UUID, user_id: UUID) -> bool:
        """Hard-delete a single memory (US4 delete API).

        Returns True if a row was deleted, False if not found / not owned.
        RLS hides other users' rows so the WHERE clause is sufficient.
        """
        stmt = select(SemanticMemory).where(
            SemanticMemory.id == memory_id,
            SemanticMemory.user_id == user_id,
        )
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return False
        await self.session.delete(row)
        await self.session.flush()
        return True

    async def purge_user_memories(self, user_id: UUID) -> int:
        """Delete ALL memories for a user (US4 forget-me).

        Returns the number of rows deleted. RLS hides other users' rows.
        """
        from sqlalchemy import delete

        stmt = delete(SemanticMemory).where(SemanticMemory.user_id == user_id)
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount or 0

    # ── MemoryRetrievalLog ─────────────────────────────────────────────────────

    async def log_retrieval(
        self,
        *,
        user_id: UUID,
        graph: str,
        node: str,
        query: str | None,
        retrieved_memory_ids: list[str],
        token_budget_used: int,
        retrieval_latency_ms: int,
    ) -> MemoryRetrievalLog:
        """Persist a retrieval observability row (FR-012)."""
        log = MemoryRetrievalLog(
            id=new_uuid_v7(),
            user_id=user_id,
            graph=graph,
            node=node,
            query=query,
            retrieved_memory_ids=retrieved_memory_ids,
            token_budget_used=token_budget_used,
            retrieval_latency_ms=retrieval_latency_ms,
        )
        self.session.add(log)
        await self.session.flush()
        await self.session.refresh(log)
        return log


__all__ = ["AgentMemoryRepository"]
