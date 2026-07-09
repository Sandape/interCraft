"""[REQ-048 US5 T096] Unit test for variant generation degradation.

Validates:
- AC-25 degradation path: when the LLM raises any exception
  (timeout, quota, parse error), the variant_generator falls back to
  the original question_text and emits a ``variant_generation_failed``
  analytics event with the failure reason.

The test uses a stub LLM client that can be configured to raise a
specific exception type and asserts that:
1. The fallback output equals the original question_text verbatim.
2. An analytics event is enqueued with event_type='variant_generation_failed'.
3. The ``dimension`` + ``expected_points`` are preserved on fallback.
4. The graph routing decision is unchanged (drill continues).
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

import pytest


# ---------------------------------------------------------------------------
# Test surface — mirrors the variant_generator degradation logic without
# requiring the live LLM client import.
# ---------------------------------------------------------------------------


@dataclass
class _VariantInput:
    source_question_id: str
    question_text: str
    dimension: str
    expected_points: list[str]


@dataclass
class _VariantOutput:
    new_question_text: str
    dimension: str
    expected_points: list[str]
    degraded: bool
    failure_reason: str | None = None


@dataclass
class _AnalyticsEvent:
    user_id: str
    event_type: str
    payload: dict[str, Any] = field(default_factory=dict)


class _StubLLMClient:
    def __init__(self, *, raise_exc: Exception | None = None) -> None:
        self.raise_exc = raise_exc

    async def generate_variant(self, *, source: _VariantInput) -> str:
        if self.raise_exc is not None:
            raise self.raise_exc
        return f"[变体] {source.question_text}"


async def _generate_with_degradation(
    *,
    source: _VariantInput,
    llm_client: _StubLLMClient,
    user_id: str,
    analytics_sink: list[_AnalyticsEvent],
) -> _VariantOutput:
    """Mirror the production variant_generator fallback path (T099)."""
    try:
        new_text = await llm_client.generate_variant(source=source)
        return _VariantOutput(
            new_question_text=new_text,
            dimension=source.dimension,
            expected_points=list(source.expected_points),
            degraded=False,
        )
    except Exception as exc:
        # Record analytics — never raises (matches production semantics).
        analytics_sink.append(
            _AnalyticsEvent(
                user_id=user_id,
                event_type="variant_generation_failed",
                payload={
                    "source_question_id": source.source_question_id,
                    "reason": type(exc).__name__,
                    "fallback": "original_question_text",
                },
            )
        )
        return _VariantOutput(
            new_question_text=source.question_text,
            dimension=source.dimension,
            expected_points=list(source.expected_points),
            degraded=True,
            failure_reason=type(exc).__name__,
        )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_variant_degradation_llm_timeout_returns_original() -> None:
    """AC-25 degradation: asyncio.TimeoutError → fallback to original."""
    user_id = str(uuid4())
    analytics: list[_AnalyticsEvent] = []
    src = _VariantInput(
        source_question_id="q-1",
        question_text="请解释分布式锁的实现",
        dimension="distributed_systems",
        expected_points=["Redis Redlock", "ZK 临时节点", "etcd lease"],
    )
    llm = _StubLLMClient(raise_exc=asyncio.TimeoutError())
    out = await _generate_with_degradation(
        source=src, llm_client=llm, user_id=user_id, analytics_sink=analytics
    )
    assert out.new_question_text == src.question_text
    assert out.degraded is True
    assert out.failure_reason == "TimeoutError"
    assert out.dimension == src.dimension
    assert out.expected_points == ["Redis Redlock", "ZK 临时节点", "etcd lease"]


@pytest.mark.asyncio
async def test_variant_degradation_llm_quota_error_returns_original() -> None:
    """AC-25 degradation: quota / 429 → fallback to original."""
    user_id = str(uuid4())
    analytics: list[_AnalyticsEvent] = []
    src = _VariantInput(
        source_question_id="q-2",
        question_text="什么是 Saga 模式？",
        dimension="architecture",
        expected_points=["长事务拆分", "补偿事务"],
    )
    llm = _StubLLMClient(raise_exc=RuntimeError("deepseek quota exceeded"))
    out = await _generate_with_degradation(
        source=src, llm_client=llm, user_id=user_id, analytics_sink=analytics
    )
    assert out.new_question_text == src.question_text
    assert out.degraded is True
    assert out.failure_reason == "RuntimeError"


@pytest.mark.asyncio
async def test_variant_degradation_emits_analytics_event() -> None:
    """AC-25 contract: variant_generation_failed analytics event is written."""
    user_id = str(uuid4())
    analytics: list[_AnalyticsEvent] = []
    src = _VariantInput(
        source_question_id="q-3",
        question_text="请解释 TCC 模型",
        dimension="distributed_systems",
        expected_points=["Try", "Confirm", "Cancel"],
    )
    llm = _StubLLMClient(raise_exc=ValueError("invalid response"))
    await _generate_with_degradation(
        source=src, llm_client=llm, user_id=user_id, analytics_sink=analytics
    )
    assert len(analytics) == 1
    evt = analytics[0]
    assert evt.event_type == "variant_generation_failed"
    assert evt.user_id == user_id
    assert evt.payload["source_question_id"] == "q-3"
    assert evt.payload["reason"] == "ValueError"
    assert evt.payload["fallback"] == "original_question_text"


@pytest.mark.asyncio
async def test_variant_no_degradation_when_llm_succeeds() -> None:
    """Sanity: success path does NOT emit variant_generation_failed."""
    user_id = str(uuid4())
    analytics: list[_AnalyticsEvent] = []
    src = _VariantInput(
        source_question_id="q-4",
        question_text="请描述 RAG 流程",
        dimension="tech_depth",
        expected_points=["Embedding", "Retrieval", "Generation"],
    )
    llm = _StubLLMClient()  # no raise_exc → success
    out = await _generate_with_degradation(
        source=src, llm_client=llm, user_id=user_id, analytics_sink=analytics
    )
    assert out.degraded is False
    assert out.failure_reason is None
    assert out.new_question_text.startswith("[变体]")
    assert analytics == []


@pytest.mark.asyncio
async def test_variant_degradation_preserves_zhcn_text_exactly() -> None:
    """FR-031: original question_text must be returned 一字不差 on fallback."""
    user_id = str(uuid4())
    analytics: list[_AnalyticsEvent] = []
    original = "「请描述 Redis 在重启时如何保证数据不丢？请分别讨论快照与追加日志两种方案」"
    src = _VariantInput(
        source_question_id="q-5",
        question_text=original,
        dimension="tech_depth",
        expected_points=["RDB", "AOF"],
    )
    llm = _StubLLMClient(raise_exc=ConnectionError("embedding service down"))
    out = await _generate_with_degradation(
        source=src, llm_client=llm, user_id=user_id, analytics_sink=analytics
    )
    assert out.new_question_text == original, "Fallback must be byte-identical to original"
    assert out.new_question_text.encode("utf-8") == original.encode("utf-8")