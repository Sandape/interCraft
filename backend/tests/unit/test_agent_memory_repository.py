"""Unit tests for AgentMemoryRepository.

Per specs/028-long-term-memory/plan.md Phase 3 T011.
Tests the upsert + latest-wins logic in isolation. Uses an in-memory
SQLite session via MagicMock to assert SQL semantics; actual RLS behavior
is covered by the integration test (`backend/tests/integration/test_agent_memory.py`).

These unit tests focus on the latest-wins conflict resolution algorithm —
the heart of FR-007. They mock the session to capture SQL behavior and
verify the high-level semantics (existing row → supersede + insert new).
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.core.ids import new_uuid_v7
from app.modules.agent_memory.models import SemanticMemory
from app.modules.agent_memory.repository import AgentMemoryRepository


def _make_existing_memory(
    *,
    fact_key: str = "target_position",
    fact_value: str = "前端",
    version: int = 1,
    days_ago: int = 5,
) -> SemanticMemory:
    now = datetime.now(timezone.utc)
    return SemanticMemory(
        id=new_uuid_v7(),
        user_id=uuid4(),
        fact_key=fact_key,
        fact_value=fact_value,
        confidence=1.0,
        source="user_asserted",
        version=version,
        status="active",
        schema_version=1,
        meta={},
        created_at=now,
        updated_at=now,
    )


class TestUpsertSemanticMemory:
    @pytest.mark.asyncio
    async def test_inserts_new_when_no_existing(self) -> None:
        """First-time fact: insert with version=1, status='active'."""
        session = MagicMock()
        # No existing active row
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=result_mock)
        session.add = MagicMock()
        session.flush = AsyncMock()
        session.refresh = AsyncMock()

        repo = AgentMemoryRepository(session)
        row = await repo.upsert_semantic_memory(
            user_id=uuid4(),
            fact_key="target_position",
            fact_value="前端",
            confidence=1.0,
            source="user_asserted",
        )

        # session.add called once with a SemanticMemory instance
        assert session.add.call_count == 1
        added = session.add.call_args[0][0]
        assert isinstance(added, SemanticMemory)
        assert added.fact_key == "target_position"
        assert added.fact_value == "前端"
        assert added.version == 1
        assert added.status == "active"
        assert row is added

    @pytest.mark.asyncio
    async def test_noop_when_same_value(self) -> None:
        """Idempotent: existing active row with identical fact_value → no-op."""
        existing = _make_existing_memory(fact_value="前端", version=1)

        session = MagicMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = existing
        session.execute = AsyncMock(return_value=result_mock)
        session.add = MagicMock()
        session.flush = AsyncMock()
        session.refresh = AsyncMock()

        repo = AgentMemoryRepository(session)
        row = await repo.upsert_semantic_memory(
            user_id=existing.user_id,
            fact_key="target_position",
            fact_value="前端",  # same value
        )

        # No INSERT, no UPDATE — session.add not called.
        assert session.add.call_count == 0
        # Returned the existing row.
        assert row is existing

    @pytest.mark.asyncio
    async def test_supersedes_when_value_differs(self) -> None:
        """Latest-wins: existing row → status='superseded', new row → status='active'."""
        existing = _make_existing_memory(fact_value="前端", version=1)

        session = MagicMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = existing
        session.execute = AsyncMock(return_value=result_mock)
        session.add = MagicMock()
        session.flush = AsyncMock()
        session.refresh = AsyncMock()

        repo = AgentMemoryRepository(session)
        new_row = await repo.upsert_semantic_memory(
            user_id=existing.user_id,
            fact_key="target_position",
            fact_value="后端",  # different value
        )

        # New row INSERTED
        assert session.add.call_count == 1
        added = session.add.call_args[0][0]
        assert isinstance(added, SemanticMemory)
        assert added.fact_value == "后端"
        assert added.version == 2  # old.version + 1
        assert added.status == "active"

        # Three SQL statements issued:
        #   1. SELECT existing active row
        #   2. UPDATE old row: status='superseded' (releases partial unique constraint)
        #   3. UPDATE old row: superseded_by=new_id (FK now satisfiable)
        assert session.execute.await_count == 3
        # Calls 2 and 3 are the UPDATE statements (call 1 is the SELECT).
        update_stmts = [
            call.args[0]
            for call in session.execute.await_args_list[1:]
        ]
        for stmt in update_stmts:
            compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
            assert "semantic_memories" in compiled
            assert "update" in compiled.lower() or "superseded" in compiled.lower()

        # Returned the new row.
        assert new_row is added


class TestListActiveMemories:
    @pytest.mark.asyncio
    async def test_invokes_select_with_user_filter(self) -> None:
        session = MagicMock()
        result_mock = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = []
        result_mock.scalars.return_value = scalars_mock
        session.execute = AsyncMock(return_value=result_mock)

        uid = uuid4()
        repo = AgentMemoryRepository(session)
        await repo.list_active_memories(uid, limit=10)

        # Verify the SELECT was issued
        session.execute.assert_awaited_once()
        stmt_arg = session.execute.await_args.args[0]
        compiled = str(stmt_arg.compile(compile_kwargs={"literal_binds": True}))
        assert "semantic_memories" in compiled
        assert "active" in compiled


class TestDeleteMemory:
    @pytest.mark.asyncio
    async def test_returns_false_when_not_found(self) -> None:
        session = MagicMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=result_mock)

        repo = AgentMemoryRepository(session)
        deleted = await repo.delete_memory(uuid4(), uuid4())

        assert deleted is False

    @pytest.mark.asyncio
    async def test_deletes_row_when_found(self) -> None:
        existing = _make_existing_memory(fact_value="前端")
        session = MagicMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = existing
        session.execute = AsyncMock(return_value=result_mock)
        session.delete = AsyncMock()
        session.flush = AsyncMock()

        repo = AgentMemoryRepository(session)
        deleted = await repo.delete_memory(existing.id, existing.user_id)

        assert deleted is True
        session.delete.assert_awaited_once_with(existing)


class TestPurgeUserMemories:
    @pytest.mark.asyncio
    async def test_executes_delete_statement(self) -> None:
        session = MagicMock()
        result_mock = MagicMock()
        result_mock.rowcount = 5
        session.execute = AsyncMock(return_value=result_mock)
        session.flush = AsyncMock()

        repo = AgentMemoryRepository(session)
        count = await repo.purge_user_memories(uuid4())

        assert count == 5
        session.execute.assert_awaited_once()
        stmt_arg = session.execute.await_args.args[0]
        compiled = str(stmt_arg.compile(compile_kwargs={"literal_binds": True}))
        assert "delete" in compiled.lower()
        assert "semantic_memories" in compiled.lower()


class TestLogRetrieval:
    @pytest.mark.asyncio
    async def test_persists_log_row(self) -> None:
        session = MagicMock()
        session.add = MagicMock()
        session.flush = AsyncMock()
        session.refresh = AsyncMock()

        repo = AgentMemoryRepository(session)
        log = await repo.log_retrieval(
            user_id=uuid4(),
            graph="interview",
            node="planner_context",
            query=None,
            retrieved_memory_ids=["id1", "id2"],
            token_budget_used=120,
            retrieval_latency_ms=42,
        )

        session.add.assert_called_once()
        added = session.add.call_args[0][0]
        assert added.graph == "interview"
        assert added.node == "planner_context"
        assert added.retrieved_memory_ids == ["id1", "id2"]
        assert added.token_budget_used == 120
        assert added.retrieval_latency_ms == 42
        assert log is added
