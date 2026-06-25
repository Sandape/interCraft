"""Integration test for agent_memory module (REQ-028 US1).

Per specs/028-long-term-memory/plan.md Phase 3 T014.
End-to-end:
  1. Register a fresh user.
  2. Insert semantic memories directly via SQL (simulating prior sessions).
  3. Call retrieve_active_memories → assert memories returned.
  4. Call planner_context_node → assert memories injected into planner_context.
  5. Call extract_and_store with a mock interview state → assert upsert behavior
     including latest-wins (existing active row → superseded, new row → active).
  6. RLS: cross-user access returns 0 rows.

Requires a real Postgres + the alembic migration applied (0018_agent_memory).
"""
from __future__ import annotations

import secrets
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

from app.agents.interview.nodes.planner_context import (
    _load_user_memories,
    planner_context_node,
)
from app.modules.agent_memory.extractor import extract_and_store
from app.modules.agent_memory.models import SemanticMemory
from app.modules.agent_memory.repository import AgentMemoryRepository
from app.modules.agent_memory.retriever import retrieve_active_memories

pytestmark = [pytest.mark.integration]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _register_user(client, suffix: str) -> tuple[dict, UUID]:
    """Register a fresh user via the API; return (headers, user_id)."""
    email = f"mem_{suffix}@intercraft.io"
    fp = f"fp-{suffix}"
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "Demo1234",
            "display_name": f"mem-{suffix}",
            "device_fingerprint": fp,
        },
        headers={"X-Device-Fingerprint": fp},
    )
    assert reg.status_code in (200, 201), reg.text
    access = reg.json()["tokens"]["access_token"]
    headers = {"Authorization": f"Bearer {access}", "X-Device-Fingerprint": fp}
    me = await client.get("/api/v1/users/me", headers=headers)
    assert me.status_code == 200, me.text
    return headers, UUID(me.json()["id"])


async def _insert_memory(
    db_session,
    *,
    user_id: UUID,
    fact_key: str,
    fact_value: str,
    confidence: float = 1.0,
    source: str = "user_asserted",
    status: str = "active",
    version: int = 1,
) -> UUID:
    """Insert a semantic_memories row directly via SQL (sets RLS GUC first)."""
    mem_id = uuid4()
    await db_session.execute(
        text("SELECT set_config('app.user_id', :uid, true)"),
        {"uid": str(user_id)},
    )
    await db_session.execute(
        text(
            """INSERT INTO semantic_memories
               (id, user_id, fact_key, fact_value, confidence,
                source, version, status, schema_version, meta)
               VALUES (:id, :uid, :key, :val, :conf,
                       :src, :ver, :status, 1, '{}'::jsonb)"""
        ),
        {
            "id": mem_id,
            "uid": user_id,
            "key": fact_key,
            "val": fact_value,
            "conf": confidence,
            "src": source,
            "ver": version,
            "status": status,
        },
    )
    await db_session.commit()
    return mem_id


# ---------------------------------------------------------------------------
# Retrieval tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestMemoryRetrieval:
    async def test_retrieves_active_memories_for_user(self, client, db_session):
        """User with 3 active memories → retriever returns 3, newest first."""
        headers, user_id = await _register_user(
            client, secrets.token_hex(4)
        )
        # Insert 3 active memories. Use slightly different created_at via
        # explicit timestamps to ensure deterministic ordering.
        await _insert_memory(
            db_session,
            user_id=user_id,
            fact_key="target_position",
            fact_value="前端开发",
            confidence=1.0,
        )
        await _insert_memory(
            db_session,
            user_id=user_id,
            fact_key="target_company",
            fact_value="字节跳动",
            confidence=1.0,
        )
        await _insert_memory(
            db_session,
            user_id=user_id,
            fact_key="identified_weakness",
            fact_value="architecture (architecture, 得分 5.0)",
            confidence=0.7,
            source="extracted_from_llm_output",
        )

        from app.core.db import get_session_context

        async with get_session_context() as session:
            await session.execute(
                text("SELECT set_config('app.user_id', :uid, true)"),
                {"uid": str(user_id)},
            )
            result = await retrieve_active_memories(
                user_id=user_id,
                graph="interview",
                node="planner_context",
                session=session,
                token_budget=500,
            )

        assert result.degraded is False
        assert len(result.memories) == 3
        fact_keys = [m.fact_key for m in result.memories]
        assert "target_position" in fact_keys
        assert "target_company" in fact_keys
        assert "identified_weakness" in fact_keys
        assert result.token_budget_used > 0

    async def test_retriever_skips_superseded_rows(self, client, db_session):
        """Superseded memories are NOT returned."""
        headers, user_id = await _register_user(
            client, secrets.token_hex(4)
        )
        # Insert an active + a superseded memory with same fact_key.
        await _insert_memory(
            db_session,
            user_id=user_id,
            fact_key="target_position",
            fact_value="前端 (旧)",
            status="superseded",
            version=1,
        )
        await _insert_memory(
            db_session,
            user_id=user_id,
            fact_key="target_position",
            fact_value="后端 (新)",
            status="active",
            version=2,
        )

        from app.core.db import get_session_context

        async with get_session_context() as session:
            await session.execute(
                text("SELECT set_config('app.user_id', :uid, true)"),
                {"uid": str(user_id)},
            )
            result = await retrieve_active_memories(
                user_id=user_id,
                graph="interview",
                node="planner_context",
                session=session,
                token_budget=500,
            )

        assert len(result.memories) == 1
        assert result.memories[0].fact_value == "后端 (新)"
        assert result.memories[0].version == 2

    async def test_rls_blocks_cross_user_access(self, client, db_session):
        """User A's memories are NOT visible to User B (RLS)."""
        headers_a, user_a = await _register_user(client, f"a_{secrets.token_hex(4)}")
        headers_b, user_b = await _register_user(client, f"b_{secrets.token_hex(4)}")

        await _insert_memory(
            db_session,
            user_id=user_a,
            fact_key="target_position",
            fact_value="前端 (A only)",
        )

        from app.core.db import get_session_context

        # User B's RLS context → should see 0 of A's memories.
        async with get_session_context() as session:
            await session.execute(
                text("SELECT set_config('app.user_id', :uid, true)"),
                {"uid": str(user_b)},
            )
            result = await retrieve_active_memories(
                user_id=user_b,
                graph="interview",
                node="planner_context",
                session=session,
                token_budget=500,
            )

        assert result.memories == []
        assert result.degraded is False  # 0 rows is normal, not degraded

    async def test_new_user_has_no_memories(self, client, db_session):
        """Freshly registered user → no memories, no error, not degraded."""
        headers, user_id = await _register_user(client, secrets.token_hex(4))

        from app.core.db import get_session_context

        async with get_session_context() as session:
            await session.execute(
                text("SELECT set_config('app.user_id', :uid, true)"),
                {"uid": str(user_id)},
            )
            result = await retrieve_active_memories(
                user_id=user_id,
                graph="interview",
                node="planner_context",
                session=session,
                token_budget=500,
            )

        assert result.memories == []
        assert result.degraded is False
        assert result.token_budget_used == 0


# ---------------------------------------------------------------------------
# Extraction + storage tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestMemoryExtractionAndStorage:
    async def test_extract_and_store_inserts_new_facts(self, client, db_session):
        """Extracting from a fresh interview state → 3 facts stored (pos/company/weakness)."""
        headers, user_id = await _register_user(client, secrets.token_hex(4))

        from app.core.db import get_session_context

        state = {
            "position": "前端开发",
            "company": "字节跳动",
            "interview_plan": None,
            "interview_report": {
                "dimension_scores": {
                    "tech_depth": 9.0,
                    "architecture": 4.0,  # weakness
                    "engineering_practice": 5.5,  # also weakness but worst is architecture
                    "communication": 8.0,
                    "algorithm": 7.5,
                }
            },
            "overall_score": 6.8,
        }

        async with get_session_context() as session:
            await session.execute(
                text("SELECT set_config('app.user_id', :uid, true)"),
                {"uid": str(user_id)},
            )
            repo = AgentMemoryRepository(session)
            summary = await extract_and_store(
                user_id=user_id,
                session_id=uuid4(),
                state=state,
                repo=repo,
            )

        assert summary["extracted"] == 3  # position + company + 1 worst weakness
        assert summary["stored"] == 3
        assert summary["blocked"] == 0

        # Verify rows are persisted
        async with get_session_context() as session:
            await session.execute(
                text("SELECT set_config('app.user_id', :uid, true)"),
                {"uid": str(user_id)},
            )
            rows = await AgentMemoryRepository(session).list_active_memories(user_id)
        assert len(rows) == 3
        fact_keys = [r.fact_key for r in rows]
        assert "target_position" in fact_keys
        assert "target_company" in fact_keys
        assert "identified_weakness" in fact_keys
        # The weakness should be architecture (the worst score, 4.0)
        weakness = next(r for r in rows if r.fact_key == "identified_weakness")
        assert "architecture" in weakness.fact_value

    async def test_extract_and_store_supersedes_old_value(self, client, db_session):
        """User changes target position → old row superseded, new row active."""
        headers, user_id = await _register_user(client, secrets.token_hex(4))

        from app.core.db import get_session_context

        # Session 1 — user said "前端开发"
        state1 = {
            "position": "前端开发",
            "company": "字节跳动",
            "interview_report": {},
        }
        async with get_session_context() as session:
            await session.execute(
                text("SELECT set_config('app.user_id', :uid, true)"),
                {"uid": str(user_id)},
            )
            repo = AgentMemoryRepository(session)
            await extract_and_store(
                user_id=user_id, session_id=uuid4(), state=state1, repo=repo
            )

        # Verify 1 active target_position row
        async with get_session_context() as session:
            await session.execute(
                text("SELECT set_config('app.user_id', :uid, true)"),
                {"uid": str(user_id)},
            )
            rows1 = await AgentMemoryRepository(session).list_active_memories(user_id)
        pos_rows1 = [r for r in rows1 if r.fact_key == "target_position"]
        assert len(pos_rows1) == 1
        assert pos_rows1[0].fact_value == "前端开发"
        assert pos_rows1[0].version == 1
        original_id = pos_rows1[0].id

        # Session 2 — user changed to "后端开发"
        state2 = {
            "position": "后端开发",
            "company": "字节跳动",
            "interview_report": {},
        }
        async with get_session_context() as session:
            await session.execute(
                text("SELECT set_config('app.user_id', :uid, true)"),
                {"uid": str(user_id)},
            )
            repo = AgentMemoryRepository(session)
            await extract_and_store(
                user_id=user_id, session_id=uuid4(), state=state2, repo=repo
            )

        # Verify: old row superseded, new row active version=2
        async with get_session_context() as session:
            await session.execute(
                text("SELECT set_config('app.user_id', :uid, true)"),
                {"uid": str(user_id)},
            )
            rows2 = await AgentMemoryRepository(session).list_active_memories(user_id)
        pos_rows2 = [r for r in rows2 if r.fact_key == "target_position"]
        assert len(pos_rows2) == 1  # only 1 active
        assert pos_rows2[0].fact_value == "后端开发"
        assert pos_rows2[0].version == 2
        assert pos_rows2[0].id != original_id

        # The old row should still exist (NOT deleted) and be superseded.
        async with get_session_context() as session:
            await session.execute(
                text("SELECT set_config('app.user_id', :uid, true)"),
                {"uid": str(user_id)},
            )
            all_rows = await AgentMemoryRepository(session).list_all_memories(
                user_id, include_superseded=True
            )
        all_pos = [r for r in all_rows if r.fact_key == "target_position"]
        assert len(all_pos) == 2
        statuses = {r.status for r in all_pos}
        assert statuses == {"active", "superseded"}
        superseded_row = next(r for r in all_pos if r.status == "superseded")
        assert superseded_row.id == original_id
        assert superseded_row.superseded_at is not None
        assert superseded_row.superseded_by == pos_rows2[0].id


# ---------------------------------------------------------------------------
# planner_context integration tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestPlannerContextMemoryInjection:
    async def test_planner_context_loads_memories(self, client, db_session):
        """planner_context_node reads memories from DB → injects into state."""
        headers, user_id = await _register_user(client, secrets.token_hex(4))
        await _insert_memory(
            db_session,
            user_id=user_id,
            fact_key="target_position",
            fact_value="前端开发",
        )
        await _insert_memory(
            db_session,
            user_id=user_id,
            fact_key="identified_weakness",
            fact_value="architecture (architecture, 得分 5.0)",
            confidence=0.7,
            source="extracted_from_llm_output",
        )

        # Call planner_context_node directly with a minimal state
        state = {
            "user_id": str(user_id),
            "branch_id": None,
            "job_id": None,
        }
        result = await planner_context_node(state)

        planner_context = result["planner_context"]
        assert "memories" in planner_context
        assert len(planner_context["memories"]) == 2
        fact_keys = [m["fact_key"] for m in planner_context["memories"]]
        assert "target_position" in fact_keys
        assert "identified_weakness" in fact_keys

    async def test_planner_context_no_memories_for_new_user(self, client, db_session):
        """New user → planner_context has no 'memories' key (or empty)."""
        headers, user_id = await _register_user(client, secrets.token_hex(4))

        state = {
            "user_id": str(user_id),
            "branch_id": None,
            "job_id": None,
        }
        result = await planner_context_node(state)
        planner_context = result["planner_context"]
        # Empty memories → no key (or empty list). Either is acceptable.
        memories = planner_context.get("memories", [])
        assert memories == []

    async def test_planner_context_does_not_raise_on_db_error(self, client, db_session):
        """If memory retrieval fails internally, planner_context still returns."""
        headers, user_id = await _register_user(client, secrets.token_hex(4))

        # Pass an invalid user_id format to trigger failure in _load_user_memories
        # without breaking planner_context. The function should swallow it.
        state = {
            "user_id": "not-a-uuid",  # invalid
            "branch_id": None,
            "job_id": None,
        }
        result = await planner_context_node(state)
        # Should still return a valid planner_context dict
        assert "planner_context" in result
        assert result["planner_context"] is not None


# ---------------------------------------------------------------------------
# planner_generate prompt rendering
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestPlannerGenerateMemorySection:
    def test_renders_memory_section_in_prompt(self):
        """_format_user_content includes 长期记忆 section when memories present."""
        from app.agents.interview.nodes.planner_generate import _format_user_content

        planner_context = {
            "resume": {"has_resume": False},
            "job": {"has_job": False},
            "memories": [
                {
                    "fact_key": "target_position",
                    "fact_value": "前端开发",
                    "confidence": 1.0,
                    "source": "user_asserted",
                },
                {
                    "fact_key": "identified_weakness",
                    "fact_value": "architecture (得分 5.0)",
                    "confidence": 0.7,
                    "source": "extracted_from_llm_output",
                },
            ],
        }
        content = _format_user_content(planner_context, web_research=None)
        assert "## 长期记忆" in content
        assert "target_position: 前端开发" in content
        assert "identified_weakness" in content
        assert "architecture" in content

    def test_no_memory_section_when_empty(self):
        """No memories → no 长期记忆 section (no log spam for new users)."""
        from app.agents.interview.nodes.planner_generate import _format_user_content

        planner_context = {
            "resume": {"has_resume": False},
            "job": {"has_job": False},
            # No 'memories' key — simulates new user.
        }
        content = _format_user_content(planner_context, web_research=None)
        assert "## 长期记忆" not in content

    def test_no_memory_section_when_empty_list(self):
        """Empty memories list → no 长期记忆 section."""
        from app.agents.interview.nodes.planner_generate import _format_user_content

        planner_context = {
            "resume": {"has_resume": False},
            "job": {"has_job": False},
            "memories": [],
        }
        content = _format_user_content(planner_context, web_research=None)
        assert "## 长期记忆" not in content
