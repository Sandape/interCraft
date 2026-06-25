"""Unit tests for the rule-based semantic memory extractor.

Per specs/028-long-term-memory/plan.md Phase 3 T012.
Tests `extract_facts()` (pure function) and `extract_and_store()` (side-effectful).

`extract_facts` is deterministic — given the same state, it produces the
same facts. `extract_and_store` wraps it with redaction + persistence; we
mock the repository to assert call sequences.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from app.modules.agent_memory.extractor import extract_and_store, extract_facts
from app.modules.agent_memory.models import SemanticMemory


def _make_state(
    *,
    position: str | None = "前端开发",
    company: str | None = "字节跳动",
    plan: dict | None = None,
    report: dict | None = None,
) -> dict:
    return {
        "position": position,
        "company": company,
        "interview_plan": plan,
        "interview_report": report or {},
    }


class TestExtractFactsPositionCompany:
    def test_extracts_position_and_company(self) -> None:
        state = _make_state(position="后端开发", company="腾讯")
        facts = extract_facts(state)
        keys = [f["fact_key"] for f in facts]
        assert "target_position" in keys
        assert "target_company" in keys
        pos = next(f for f in facts if f["fact_key"] == "target_position")
        assert pos["fact_value"] == "后端开发"
        assert pos["confidence"] == 1.0
        assert pos["source"] == "user_asserted"

    def test_falls_back_to_plan_target_position(self) -> None:
        """When state.position is empty, use interview_plan.target_position."""
        state = _make_state(
            position=None,
            company=None,
            plan={"target_position": "全栈", "target_company": "美团"},
        )
        facts = extract_facts(state)
        keys = [f["fact_key"] for f in facts]
        assert "target_position" in keys
        pos = next(f for f in facts if f["fact_key"] == "target_position")
        assert pos["fact_value"] == "全栈"

    def test_no_position_yields_no_position_fact(self) -> None:
        state = _make_state(position=None, company=None, plan={})
        facts = extract_facts(state)
        keys = [f["fact_key"] for f in facts]
        assert "target_position" not in keys
        assert "target_company" not in keys


class TestExtractFactsWeakness:
    def test_extracts_worst_dimension_as_weakness(self) -> None:
        """The single lowest-scoring dimension below 7.0 becomes 'identified_weakness'.

        We extract ONE weakness per interview (the worst one) so latest-wins
        across interviews reflects "the user's most recent worst weakness".
        """
        state = _make_state(
            report={
                "dimension_scores": {
                    "tech_depth": 8.5,
                    "architecture": 4.0,  # worst
                    "engineering_practice": 5.5,  # second-worst
                    "communication": 9.0,
                    "algorithm": 7.0,
                }
            }
        )
        facts = extract_facts(state)
        weakness_facts = [f for f in facts if f["fact_key"] == "identified_weakness"]
        assert len(weakness_facts) == 1
        assert "architecture" in weakness_facts[0]["fact_value"]
        assert weakness_facts[0]["confidence"] == 0.7
        assert weakness_facts[0]["source"] == "extracted_from_llm_output"

    def test_skips_dimensions_with_score_above_threshold(self) -> None:
        """Dimensions scoring ≥7.0 are NOT flagged as weaknesses."""
        state = _make_state(
            report={
                "dimension_scores": {
                    "tech_depth": 9.0,
                    "architecture": 8.0,
                    "communication": 7.5,
                }
            }
        )
        facts = extract_facts(state)
        weakness_facts = [f for f in facts if f["fact_key"] == "identified_weakness"]
        assert weakness_facts == []

    def test_handles_empty_dimension_scores(self) -> None:
        state = _make_state(report={"dimension_scores": {}})
        facts = extract_facts(state)
        weakness_facts = [f for f in facts if f["fact_key"] == "identified_weakness"]
        assert weakness_facts == []

    def test_handles_missing_report(self) -> None:
        state = _make_state(report=None)
        facts = extract_facts(state)
        weakness_facts = [f for f in facts if f["fact_key"] == "identified_weakness"]
        assert weakness_facts == []

    def test_skips_non_numeric_scores(self) -> None:
        state = _make_state(
            report={
                "dimension_scores": {
                    "tech_depth": "n/a",  # non-numeric — should be skipped
                    "architecture": 4.0,
                }
            }
        )
        facts = extract_facts(state)
        weakness_facts = [f for f in facts if f["fact_key"] == "identified_weakness"]
        # Only architecture qualifies
        assert len(weakness_facts) == 1
        assert "architecture" in weakness_facts[0]["fact_value"]


class TestExtractFactsPreference:
    def test_extracts_high_weight_focus_areas(self) -> None:
        state = _make_state(
            plan={
                "focus_areas": [
                    {"area": "React 底层原理", "weight": 0.5},  # ≥0.4 → preference
                    {"area": "工程化能力", "weight": 0.3},  # <0.4 → skipped
                    {"area": "架构设计", "weight": 0.4},  # =0.4 → preference
                ]
            }
        )
        facts = extract_facts(state)
        pref_facts = [f for f in facts if f["fact_key"] == "stated_preference"]
        assert len(pref_facts) == 2
        for f in pref_facts:
            assert f["confidence"] == 0.4
            assert f["source"] == "system_inferred"

    def test_skips_empty_area_name(self) -> None:
        state = _make_state(
            plan={
                "focus_areas": [
                    {"area": "", "weight": 0.5},  # empty → skipped
                    {"area": "  ", "weight": 0.6},  # whitespace-only → skipped
                ]
            }
        )
        facts = extract_facts(state)
        pref_facts = [f for f in facts if f["fact_key"] == "stated_preference"]
        assert pref_facts == []

    def test_no_focus_areas(self) -> None:
        state = _make_state(plan={"focus_areas": []})
        facts = extract_facts(state)
        pref_facts = [f for f in facts if f["fact_key"] == "stated_preference"]
        assert pref_facts == []


class TestExtractAndStore:
    @pytest.mark.asyncio
    async def test_persists_each_fact_via_upsert(self) -> None:
        """extract_and_store calls repo.upsert_semantic_memory once per fact."""
        repo = MagicMock()
        repo.upsert_semantic_memory = AsyncMock()

        # Make upsert return a fake SemanticMemory so the code can read .fact_key etc.
        async def _fake_upsert(**kwargs):
            mem = MagicMock(spec=SemanticMemory)
            mem.fact_key = kwargs["fact_key"]
            mem.fact_value = kwargs["fact_value"]
            mem.version = 1
            mem.status = "active"
            return mem

        repo.upsert_semantic_memory.side_effect = _fake_upsert

        state = _make_state(
            position="前端",
            company="字节",
            report={"dimension_scores": {"architecture": 4.0}},
        )
        summary = await extract_and_store(
            user_id=uuid4(),
            session_id=uuid4(),
            state=state,
            repo=repo,
        )

        # position + company + 1 weakness = 3 facts
        assert summary["extracted"] == 3
        assert summary["stored"] == 3
        assert summary["blocked"] == 0
        assert repo.upsert_semantic_memory.call_count == 3

    @pytest.mark.asyncio
    async def test_blocks_pii_heavy_fact_value(self) -> None:
        """When redactor blocks, the fact is skipped (not stored)."""
        repo = MagicMock()
        repo.upsert_semantic_memory = AsyncMock()

        async def _fake_upsert(**kwargs):
            mem = MagicMock(spec=SemanticMemory)
            mem.fact_key = kwargs["fact_key"]
            mem.fact_value = kwargs["fact_value"]
            mem.version = 1
            mem.status = "active"
            return mem

        repo.upsert_semantic_memory.side_effect = _fake_upsert

        # Position is just an email → redactor should block it.
        state = _make_state(position="foo@bar.com", company=None)
        summary = await extract_and_store(
            user_id=uuid4(),
            session_id=uuid4(),
            state=state,
            repo=repo,
        )

        assert summary["extracted"] == 1
        assert summary["stored"] == 0
        assert summary["blocked"] == 1
        repo.upsert_semantic_memory.assert_not_called()

    @pytest.mark.asyncio
    async def test_redacts_pii_in_kept_fact(self) -> None:
        """If fact_value contains incidental PII, it's redacted but stored."""
        repo = MagicMock()
        repo.upsert_semantic_memory = AsyncMock()

        captured: dict = {}

        async def _fake_upsert(**kwargs):
            captured.update(kwargs)
            mem = MagicMock(spec=SemanticMemory)
            mem.fact_key = kwargs["fact_key"]
            mem.fact_value = kwargs["fact_value"]
            mem.version = 1
            mem.status = "active"
            return mem

        repo.upsert_semantic_memory.side_effect = _fake_upsert

        # Position with incidental email → redacted but kept.
        state = _make_state(position="前端开发 联系 foo@bar.com", company=None)
        await extract_and_store(
            user_id=uuid4(),
            session_id=uuid4(),
            state=state,
            repo=repo,
        )

        assert "foo@bar.com" not in captured["fact_value"]
        assert "[REDACTED]" in captured["fact_value"]

    @pytest.mark.asyncio
    async def test_injects_session_id_into_meta(self) -> None:
        repo = MagicMock()
        repo.upsert_semantic_memory = AsyncMock()

        captured: dict = {}

        async def _fake_upsert(**kwargs):
            captured.update(kwargs)
            mem = MagicMock(spec=SemanticMemory)
            mem.fact_key = kwargs["fact_key"]
            mem.fact_value = kwargs["fact_value"]
            mem.version = 1
            mem.status = "active"
            return mem

        repo.upsert_semantic_memory.side_effect = _fake_upsert

        session_id = uuid4()
        state = _make_state(position="前端", company=None)
        await extract_and_store(
            user_id=uuid4(),
            session_id=session_id,
            state=state,
            repo=repo,
        )

        assert captured["meta"]["session_id"] == str(session_id)
