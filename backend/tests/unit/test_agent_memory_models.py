"""Unit tests for SemanticMemory + MemoryRetrievalLog models.

Per specs/028-long-term-memory/plan.md Phase 3 T010.
Tests field defaults, CHECK constraint fixtures (DB-level, but model
instantiation must not reject any value the CHECK allows), and table args.
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.core.ids import new_uuid_v7
from app.modules.agent_memory.models import MemoryRetrievalLog, SemanticMemory


class TestSemanticMemoryInstantiation:
    def test_minimal_construction(self) -> None:
        """All non-null fields populated; defaults apply for the rest."""
        mem = SemanticMemory(
            id=new_uuid_v7(),
            user_id=uuid4(),
            fact_key="target_position",
            fact_value="前端开发",
        )
        # Defaults from server_default are applied by the DB on INSERT, not by
        # Python. The model itself doesn't set defaults unless we use `default=`.
        # Confirm what the column declarations set vs what DB will set.
        assert mem.fact_key == "target_position"
        assert mem.fact_value == "前端开发"

    def test_full_construction(self) -> None:
        uid = uuid4()
        sid = new_uuid_v7()
        now = datetime.now(timezone.utc)
        mem = SemanticMemory(
            id=sid,
            user_id=uid,
            fact_key="identified_weakness",
            fact_value="system_design (architecture, 得分 5.0)",
            confidence=0.7,
            source="extracted_from_llm_output",
            version=2,
            status="superseded",
            schema_version=1,
            meta={"session_id": str(uuid4()), "dimension": "architecture"},
            superseded_at=now,
            superseded_by=new_uuid_v7(),
            created_at=now,
            updated_at=now,
        )
        assert mem.user_id == uid
        assert mem.fact_key == "identified_weakness"
        assert mem.version == 2
        assert mem.status == "superseded"
        assert mem.meta["dimension"] == "architecture"
        assert mem.superseded_at is not None

    def test_status_active_default(self) -> None:
        """Model doesn't set status default at Python level (DB does via server_default).

        But the model accepts 'active' explicitly."""
        mem = SemanticMemory(
            id=new_uuid_v7(),
            user_id=uuid4(),
            fact_key="k",
            fact_value="v",
            status="active",
        )
        assert mem.status == "active"

    def test_status_superseded_accepted(self) -> None:
        mem = SemanticMemory(
            id=new_uuid_v7(),
            user_id=uuid4(),
            fact_key="k",
            fact_value="v",
            status="superseded",
        )
        assert mem.status == "superseded"

    def test_confidence_boundary_values(self) -> None:
        """0.0 and 1.0 are valid (CHECK constraint allows [0.0, 1.0])."""
        for conf in (0.0, 0.5, 1.0):
            mem = SemanticMemory(
                id=new_uuid_v7(),
                user_id=uuid4(),
                fact_key="k",
                fact_value="v",
                confidence=conf,
            )
            assert float(mem.confidence) == conf

    def test_source_enum_values(self) -> None:
        """CHECK constraint: source IN ('extracted_from_llm_output', 'user_asserted', 'system_inferred')."""
        for src in (
            "extracted_from_llm_output",
            "user_asserted",
            "system_inferred",
        ):
            mem = SemanticMemory(
                id=new_uuid_v7(),
                user_id=uuid4(),
                fact_key="k",
                fact_value="v",
                source=src,
            )
            assert mem.source == src

    def test_version_monotonic(self) -> None:
        """Versions 1, 2, 3 — model accepts any int ≥1."""
        for v in (1, 2, 3, 10):
            mem = SemanticMemory(
                id=new_uuid_v7(),
                user_id=uuid4(),
                fact_key="k",
                fact_value="v",
                version=v,
            )
            assert mem.version == v

    def test_meta_default_empty_dict(self) -> None:
        """meta column has server_default '{}' — model defaults to None at Python level
        until flushed. The DB will set '{}' on INSERT."""
        mem = SemanticMemory(
            id=new_uuid_v7(),
            user_id=uuid4(),
            fact_key="k",
            fact_value="v",
        )
        # Before flush, meta is whatever Python set (None unless explicit).
        # The DB will apply '{}' on INSERT. Just confirm the column exists.
        assert hasattr(mem, "meta")


class TestMemoryRetrievalLogInstantiation:
    def test_minimal_construction(self) -> None:
        log = MemoryRetrievalLog(
            id=new_uuid_v7(),
            user_id=uuid4(),
            graph="interview",
            node="planner_context",
        )
        assert log.graph == "interview"
        assert log.node == "planner_context"

    def test_full_construction(self) -> None:
        mem_ids = [str(new_uuid_v7()), str(new_uuid_v7())]
        log = MemoryRetrievalLog(
            id=new_uuid_v7(),
            user_id=uuid4(),
            graph="error_coach",
            node="hint_ladder",
            query="how to optimize React performance",
            retrieved_memory_ids=mem_ids,
            token_budget_used=120,
            retrieval_latency_ms=42,
        )
        assert log.graph == "error_coach"
        assert log.token_budget_used == 120
        assert log.retrieval_latency_ms == 42
        assert len(log.retrieved_memory_ids) == 2

    def test_query_can_be_none(self) -> None:
        log = MemoryRetrievalLog(
            id=new_uuid_v7(),
            user_id=uuid4(),
            graph="interview",
            node="planner_context",
            query=None,
        )
        assert log.query is None


class TestTableArgs:
    def test_partial_unique_index_exists(self) -> None:
        """The partial unique index on (user_id, fact_key) WHERE status='active'
        is declared in __table_args__ — confirm it's there."""
        from sqlalchemy import inspect as sqla_inspect

        # We can't inspect the table without a DB, but we can check the
        # __table_args__ tuple contains an Index with the expected name.
        args = SemanticMemory.__table_args__
        # __table_args__ is a tuple of (constraint, constraint, ..., Index, Index)
        index_names = [getattr(a, "name", None) for a in args]
        assert "uq_semantic_memories_active_user_key" in index_names
        assert "idx_semantic_memories_user_active" in index_names

    def test_check_constraints_exist(self) -> None:
        args = SemanticMemory.__table_args__
        constraint_names = [getattr(a, "name", None) for a in args]
        assert "ck_semantic_memories_status" in constraint_names
        assert "ck_semantic_memories_source" in constraint_names
        assert "ck_semantic_memories_confidence" in constraint_names
        assert "ck_semantic_memories_version" in constraint_names
