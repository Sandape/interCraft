"""Unit tests for the memory retriever.

Per specs/028-long-term-memory/plan.md Phase 3 T013.
Tests token budget cap, ranking (newest-first), and graceful failure when
the DB throws.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from app.modules.agent_memory.models import SemanticMemory
from app.modules.agent_memory.retriever import (
    _estimate_tokens,
    _format_memory_for_budget,
    retrieve_active_memories,
)
from app.modules.agent_memory.schemas import SemanticMemoryOut


def _make_memory(
    *,
    fact_key: str = "target_position",
    fact_value: str = "前端开发",
    confidence: float = 1.0,
    source: str = "user_asserted",
    days_ago: int = 0,
) -> SemanticMemory:
    """Build a SemanticMemory instance with sensible defaults for tests."""
    now = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return SemanticMemory(
        id=uuid4(),
        user_id=uuid4(),
        fact_key=fact_key,
        fact_value=fact_value,
        confidence=confidence,
        source=source,
        version=1,
        status="active",
        schema_version=1,
        meta={},
        created_at=now,
        updated_at=now,
    )


class TestEstimateTokens:
    def test_empty_string(self) -> None:
        assert _estimate_tokens("") == 0

    def test_short_string(self) -> None:
        # 4 chars / 4 chars-per-token = 1, max(1, 1) = 1
        assert _estimate_tokens("abcd") == 1

    def test_long_string(self) -> None:
        # 20 chars / 4 = 5 tokens
        assert _estimate_tokens("a" * 20) == 5

    def test_chinese_text(self) -> None:
        # 8 Chinese chars / 4 = 2 tokens (rough estimate)
        assert _estimate_tokens("前端开发工程师") >= 1


class TestFormatMemoryForBudget:
    def test_includes_fact_key_and_value(self) -> None:
        mem = SemanticMemoryOut(
            id=uuid4(),
            user_id=uuid4(),
            fact_key="target_position",
            fact_value="前端",
            confidence=1.0,
            source="user_asserted",
            version=1,
            status="active",
            schema_version=1,
            meta={},
            superseded_at=None,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        text = _format_memory_for_budget(mem)
        assert "target_position" in text
        assert "前端" in text
        assert "1.00" in text  # confidence


class TestRetrieveActiveMemories:
    @pytest.mark.asyncio
    async def test_returns_memories_sorted_by_created_desc(self) -> None:
        """Repo returns newest first; retriever preserves order."""
        old_mem = _make_memory(fact_key="target_position", fact_value="前端", days_ago=10)
        new_mem = _make_memory(fact_key="target_position", fact_value="后端", days_ago=1)

        repo = MagicMock()
        repo.list_active_memories = AsyncMock(return_value=[new_mem, old_mem])
        repo.log_retrieval = AsyncMock()

        session = MagicMock()
        # Patch AgentMemoryRepository to return our mock repo
        with patch(
            "app.modules.agent_memory.retriever.AgentMemoryRepository",
            return_value=repo,
        ):
            result = await retrieve_active_memories(
                user_id=uuid4(),
                graph="interview",
                node="planner_context",
                session=session,
                token_budget=500,
            )

        assert len(result.memories) == 2
        assert result.memories[0].fact_value == "后端"  # newest first
        assert result.memories[1].fact_value == "前端"
        assert result.degraded is False

    @pytest.mark.asyncio
    async def test_caps_at_token_budget(self) -> None:
        """When memories exceed token budget, only the first N fit."""
        # Each memory text ~ 60 chars → ~15 tokens. Budget 30 → 2 memories fit.
        memories = [
            _make_memory(fact_key=f"k{i}", fact_value=f"value_{i}_" * 10)
            for i in range(5)
        ]

        repo = MagicMock()
        repo.list_active_memories = AsyncMock(return_value=memories)
        repo.log_retrieval = AsyncMock()

        session = MagicMock()
        with patch(
            "app.modules.agent_memory.retriever.AgentMemoryRepository",
            return_value=repo,
        ):
            result = await retrieve_active_memories(
                user_id=uuid4(),
                graph="interview",
                node="planner_context",
                session=session,
                token_budget=30,
            )

        assert len(result.memories) < 5
        assert result.token_budget_used <= 30
        assert result.degraded is False

    @pytest.mark.asyncio
    async def test_returns_empty_on_db_error(self) -> None:
        """FR-013 — when repo raises, retriever returns empty + degraded=True."""
        repo = MagicMock()
        repo.list_active_memories = AsyncMock(side_effect=RuntimeError("DB down"))
        repo.log_retrieval = AsyncMock()

        session = MagicMock()
        session.commit = AsyncMock()

        with patch(
            "app.modules.agent_memory.retriever.AgentMemoryRepository",
            return_value=repo,
        ):
            result = await retrieve_active_memories(
                user_id=uuid4(),
                graph="interview",
                node="planner_context",
                session=session,
                token_budget=500,
            )

        assert result.memories == []
        assert result.degraded is True

    @pytest.mark.asyncio
    async def test_returns_empty_for_new_user(self) -> None:
        """FR-013 edge case — no memories is NOT degraded, just empty."""
        repo = MagicMock()
        repo.list_active_memories = AsyncMock(return_value=[])
        repo.log_retrieval = AsyncMock()

        session = MagicMock()
        with patch(
            "app.modules.agent_memory.retriever.AgentMemoryRepository",
            return_value=repo,
        ):
            result = await retrieve_active_memories(
                user_id=uuid4(),
                graph="interview",
                node="planner_context",
                session=session,
                token_budget=500,
            )

        assert result.memories == []
        # Empty user is NOT the same as degraded — empty is normal.
        assert result.degraded is False

    @pytest.mark.asyncio
    async def test_logs_retrieval_for_observability(self) -> None:
        """FR-012 — every successful retrieval writes a MemoryRetrievalLog."""
        mem = _make_memory(fact_key="target_position", fact_value="前端")

        repo = MagicMock()
        repo.list_active_memories = AsyncMock(return_value=[mem])
        repo.log_retrieval = AsyncMock()

        session = MagicMock()
        with patch(
            "app.modules.agent_memory.retriever.AgentMemoryRepository",
            return_value=repo,
        ):
            await retrieve_active_memories(
                user_id=uuid4(),
                graph="interview",
                node="planner_context",
                session=session,
                token_budget=500,
            )

        repo.log_retrieval.assert_awaited_once()
        call_kwargs = repo.log_retrieval.call_args.kwargs
        assert call_kwargs["graph"] == "interview"
        assert call_kwargs["node"] == "planner_context"
        assert len(call_kwargs["retrieved_memory_ids"]) == 1
        assert call_kwargs["token_budget_used"] > 0

    @pytest.mark.asyncio
    async def test_does_not_raise_when_log_write_fails(self) -> None:
        """If MemoryRetrievalLog write fails, retrieval still succeeds."""
        mem = _make_memory(fact_key="target_position", fact_value="前端")

        repo = MagicMock()
        repo.list_active_memories = AsyncMock(return_value=[mem])
        repo.log_retrieval = AsyncMock(side_effect=RuntimeError("log write failed"))

        session = MagicMock()
        with patch(
            "app.modules.agent_memory.retriever.AgentMemoryRepository",
            return_value=repo,
        ):
            result = await retrieve_active_memories(
                user_id=uuid4(),
                graph="interview",
                node="planner_context",
                session=session,
                token_budget=500,
            )

        # Memories still returned
        assert len(result.memories) == 1
        assert result.degraded is False
