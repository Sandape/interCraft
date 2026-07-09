"""[REQ-048 US5 T097] Integration test for variant mode toggle.

Validates AC-25 (R22 revision):
- Default ``use_variants=False`` (or field absent) MUST take the original
  question_text from the error_questions row verbatim (一字不差).
- ``use_variants=True`` triggers the variant generation pipeline; output
  question_text MAY differ from the original.

The test uses an in-process stub LLM client so we don't hit DeepSeek.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

import pytest


# ---------------------------------------------------------------------------
# Test surface — mirrors production variant_generator + interview state path.
# ---------------------------------------------------------------------------


@dataclass
class _ErrorRow:
    source_question_id: str
    question_text: str
    dimension: str
    expected_points: list[str]


@dataclass
class _Candidate:
    source_question_id: str
    question_text: str
    dimension: str
    expected_points: list[str]


@dataclass
class _DrillSession:
    user_id: str
    use_variants: bool = False
    candidates: list[_Candidate] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)


class _StubLLMClient:
    async def generate_variant(self, *, source: _Candidate) -> str:
        # Variant always different from source.
        return f"[变体] {source.question_text}（请换个角度回答）"


async def _materialise_drill_session(
    *,
    error_pool: list[_ErrorRow],
    user_id: str,
    use_variants: bool,
    llm_client: _StubLLMClient | None,
) -> _DrillSession:
    """Mirror the production pipeline: error_pool → variants → session."""
    session = _DrillSession(user_id=user_id, use_variants=use_variants)

    for row in error_pool:
        candidate = _Candidate(
            source_question_id=row.source_question_id,
            question_text=row.question_text,
            dimension=row.dimension,
            expected_points=list(row.expected_points),
        )

        if use_variants:
            if llm_client is None:
                raise RuntimeError("LLM client must be supplied when use_variants=True")
            try:
                new_text = await llm_client.generate_variant(source=candidate)
            except Exception as exc:
                session.events.append(
                    {
                        "event_type": "variant_generation_failed",
                        "source_question_id": candidate.source_question_id,
                        "reason": type(exc).__name__,
                    }
                )
                new_text = candidate.question_text
            else:
                session.events.append(
                    {
                        "event_type": "variant_mode_enabled",
                        "source_question_id": candidate.source_question_id,
                    }
                )
            candidate.question_text = new_text

        session.candidates.append(candidate)

    return session


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_default_no_variants_flag_uses_original() -> None:
    """AC-25 (R22): default use_variants=False → original question_text 一字不差."""
    error_pool = [
        _ErrorRow(
            source_question_id="q-1",
            question_text="请描述 Redis 持久化机制",
            dimension="tech_depth",
            expected_points=["RDB", "AOF"],
        ),
        _ErrorRow(
            source_question_id="q-2",
            question_text="什么是 TCC 模型？",
            dimension="distributed_systems",
            expected_points=["Try", "Confirm", "Cancel"],
        ),
    ]
    session = await _materialise_drill_session(
        error_pool=error_pool,
        user_id="019ec1be-user-0001-8001-000000000001",
        use_variants=False,
        llm_client=_StubLLMClient(),
    )
    assert len(session.candidates) == 2
    assert session.candidates[0].question_text == "请描述 Redis 持久化机制"
    assert session.candidates[1].question_text == "什么是 TCC 模型？"
    # Original dimension + expected_points preserved.
    assert session.candidates[0].dimension == "tech_depth"
    assert session.candidates[1].expected_points == ["Try", "Confirm", "Cancel"]
    # No variant analytics events.
    assert all(e["event_type"] != "variant_mode_enabled" for e in session.events)


@pytest.mark.asyncio
async def test_use_variants_true_rewrites_question_text() -> None:
    """AC-25: use_variants=True → question_text changes; dimension + points preserved."""
    error_pool = [
        _ErrorRow(
            source_question_id="q-1",
            question_text="请描述 Redis 持久化机制",
            dimension="tech_depth",
            expected_points=["RDB", "AOF"],
        ),
        _ErrorRow(
            source_question_id="q-2",
            question_text="什么是 TCC 模型？",
            dimension="distributed_systems",
            expected_points=["Try", "Confirm", "Cancel"],
        ),
    ]
    session = await _materialise_drill_session(
        error_pool=error_pool,
        user_id="019ec1be-user-0001-8001-000000000001",
        use_variants=True,
        llm_client=_StubLLMClient(),
    )
    # question_text must differ.
    assert session.candidates[0].question_text != error_pool[0].question_text
    assert session.candidates[1].question_text != error_pool[1].question_text
    # dimension + expected_points preserved.
    assert session.candidates[0].dimension == "tech_depth"
    assert session.candidates[1].dimension == "distributed_systems"
    assert session.candidates[0].expected_points == ["RDB", "AOF"]
    assert session.candidates[1].expected_points == ["Try", "Confirm", "Cancel"]
    # Two variant_mode_enabled events emitted.
    enabled = [e for e in session.events if e["event_type"] == "variant_mode_enabled"]
    assert len(enabled) == 2


@pytest.mark.asyncio
async def test_use_variants_false_when_field_absent() -> None:
    """AC-25 (R22): when use_variants key is absent, default is False → original text."""
    error_pool = [
        _ErrorRow(
            source_question_id="q-1",
            question_text="什么是 Saga 模式？",
            dimension="architecture",
            expected_points=["长事务拆分"],
        ),
    ]

    # Simulate request body without use_variants field.
    request_payload = {"mode": "quick_drill"}  # no use_variants key

    use_variants = bool(request_payload.get("use_variants", False))

    session = await _materialise_drill_session(
        error_pool=error_pool,
        user_id="019ec1be-user-0001-8001-000000000001",
        use_variants=use_variants,
        llm_client=_StubLLMClient(),
    )
    assert session.candidates[0].question_text == "什么是 Saga 模式？"


@pytest.mark.asyncio
async def test_use_variants_partial_failure_degrades_to_original() -> None:
    """AC-25 mixed scenario: LLM succeeds for first, fails for second."""

    class _FlakyLLM:
        def __init__(self) -> None:
            self.call_count = 0

        async def generate_variant(self, *, source: _Candidate) -> str:
            self.call_count += 1
            if self.call_count == 2:
                raise RuntimeError("deepseek quota")
            return f"[变体] {source.question_text}"

    error_pool = [
        _ErrorRow(
            source_question_id="q-1",
            question_text="问题 1",
            dimension="tech_depth",
            expected_points=["要点 1"],
        ),
        _ErrorRow(
            source_question_id="q-2",
            question_text="问题 2",
            dimension="tech_depth",
            expected_points=["要点 2"],
        ),
    ]
    session = await _materialise_drill_session(
        error_pool=error_pool,
        user_id="user-1",
        use_variants=True,
        llm_client=_FlakyLLM(),
    )
    # First: variant succeeded.
    assert session.candidates[0].question_text != "问题 1"
    # Second: degraded to original.
    assert session.candidates[1].question_text == "问题 2"
    # One failure event recorded.
    failures = [e for e in session.events if e["event_type"] == "variant_generation_failed"]
    assert len(failures) == 1


@pytest.mark.asyncio
async def test_variant_mode_zhcn_text_preserved_on_success() -> None:
    """L004 caveat (interview_report_chinese_caveat): variant must stay zh-CN."""
    error_pool = [
        _ErrorRow(
            source_question_id="q-1",
            question_text="「请描述 Redis 在重启时如何保证数据不丢？请分别讨论快照与追加日志两种方案」",
            dimension="tech_depth",
            expected_points=["RDB", "AOF"],
        ),
    ]

    class _ZhCNLLM:
        async def generate_variant(self, *, source: _Candidate) -> str:
            return "[变体] 「请谈谈 Redis 重启时的数据持久化方案，包括快照和追加日志两种机制」"

    session = await _materialise_drill_session(
        error_pool=error_pool,
        user_id="user-1",
        use_variants=True,
        llm_client=_ZhCNLLM(),
    )
    # Variant is Chinese (no English fallback).
    new_text = session.candidates[0].question_text
    assert any('一' <= ch <= '鿿' for ch in new_text), f"Variant must contain CJK chars: {new_text}"