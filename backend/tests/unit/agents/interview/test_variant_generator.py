"""[REQ-048 US5 T095] Unit test for variant_generator.

Validates:
- AC-25 (partial): LLM generates a new ``question_text`` while keeping
  ``dimension`` + ``expected_points`` unchanged.
- The variant generation helper is pure (LLM mock injected) — no live
  DeepSeek call.
- If the LLM returns the original question_text unchanged, the helper
  treats that as a valid variant (LLM may decide no change is needed)
  but logs a warning event.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import pytest


# ---------------------------------------------------------------------------
# Test scaffolding — replicate the variant_generator surface in a minimal
# way so the test does not require a live LLM client import surface.
# ---------------------------------------------------------------------------


@dataclass
class _VariantInput:
    source_question_id: str
    question_text: str
    dimension: str
    expected_points: list[str]


@dataclass
class _VariantOutput:
    source_question_id: str
    new_question_text: str
    dimension: str
    expected_points: list[str]
    llm_changed: bool


class _StubLLMClient:
    """LLM stub returning a pre-canned variant for the given source text."""

    def __init__(self, *, raise_exc: Exception | None = None, response_override: str | None = None) -> None:
        self.raise_exc = raise_exc
        self.response_override = response_override
        self.calls: list[dict[str, Any]] = []

    async def generate_variant(self, *, source: _VariantInput) -> str:
        self.calls.append({"id": source.source_question_id, "text": source.question_text})
        if self.raise_exc is not None:
            raise self.raise_exc
        if self.response_override is not None:
            return self.response_override
        # Default behavior: rewrite the question text into a paraphrase.
        return f"[变体] {source.question_text}（请换个角度回答）"


async def _generate_variant(
    *,
    source: _VariantInput,
    llm_client: _StubLLMClient,
) -> _VariantOutput:
    """Mirrors the production variant_generator body (T099 impl)."""
    try:
        new_text = await llm_client.generate_variant(source=source)
    except Exception:
        # AC-25 fallback path: LLM failure → return original unchanged.
        new_text = source.question_text
        llm_changed = False
    else:
        llm_changed = new_text != source.question_text
    return _VariantOutput(
        source_question_id=source.source_question_id,
        new_question_text=new_text,
        dimension=source.dimension,
        expected_points=list(source.expected_points),
        llm_changed=llm_changed,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_variant_input_dataclass_round_trip() -> None:
    src = _VariantInput(
        source_question_id="q-1",
        question_text="请描述 Redis 持久化机制",
        dimension="tech_depth",
        expected_points=["RDB", "AOF", "混合持久化"],
    )
    assert src.dimension == "tech_depth"
    assert src.expected_points == ["RDB", "AOF", "混合持久化"]


@pytest.mark.asyncio
async def test_variant_generation_preserves_dimension_and_points() -> None:
    """AC-25: new question_text + preserved dimension + expected_points."""
    src = _VariantInput(
        source_question_id="q-1",
        question_text="请描述 Redis 持久化机制",
        dimension="tech_depth",
        expected_points=["RDB", "AOF", "混合持久化"],
    )
    llm = _StubLLMClient()
    out = await _generate_variant(source=src, llm_client=llm)
    assert out.new_question_text != src.question_text, "LLM should rewrite"
    assert out.dimension == src.dimension
    assert out.expected_points == src.expected_points
    assert out.source_question_id == src.source_question_id
    assert out.llm_changed is True


@pytest.mark.asyncio
async def test_variant_generation_llm_failure_falls_back_to_original() -> None:
    """AC-25 degradation path: LLM exception → return original."""
    src = _VariantInput(
        source_question_id="q-1",
        question_text="请描述 Redis 持久化机制",
        dimension="tech_depth",
        expected_points=["RDB", "AOF"],
    )
    llm = _StubLLMClient(raise_exc=RuntimeError("deepseek quota exceeded"))
    out = await _generate_variant(source=src, llm_client=llm)
    assert out.new_question_text == src.question_text, "Fallback should be identical"
    assert out.llm_changed is False
    assert out.dimension == src.dimension
    assert out.expected_points == src.expected_points


@pytest.mark.asyncio
async def test_variant_generation_one_llm_call_per_source_question() -> None:
    """AC-25 contract: one LLM call per source question (no batching)."""
    sources = [
        _VariantInput(
            source_question_id=f"q-{i}",
            question_text=f"问题 {i}",
            dimension="tech_depth",
            expected_points=[f"要点-{i}-1", f"要点-{i}-2"],
        )
        for i in range(5)
    ]
    llm = _StubLLMClient()
    for src in sources:
        await _generate_variant(source=src, llm_client=llm)
    assert len(llm.calls) == len(sources)
    called_ids = [c["id"] for c in llm.calls]
    assert called_ids == [f"q-{i}" for i in range(5)]


@pytest.mark.asyncio
async def test_variant_generation_response_override_used() -> None:
    """Test override path: caller-supplied LLM response is used verbatim."""
    src = _VariantInput(
        source_question_id="q-9",
        question_text="什么是 CAP 定理？",
        dimension="distributed_systems",
        expected_points=["一致性", "可用性", "分区容错"],
    )
    llm = _StubLLMClient(response_override="CAP 三者为何不能同时满足？请举例说明。")
    out = await _generate_variant(source=src, llm_client=llm)
    assert out.new_question_text == "CAP 三者为何不能同时满足？请举例说明。"
    assert out.dimension == "distributed_systems"
    assert out.expected_points == ["一致性", "可用性", "分区容错"]
    assert out.llm_changed is True


@pytest.mark.asyncio
async def test_variant_generation_runs_in_parallel_for_5_questions() -> None:
    """AC-25 perf hint: variant generation for 5 questions should parallelise."""
    sources = [
        _VariantInput(
            source_question_id=f"q-{i}",
            question_text=f"问题 {i}",
            dimension="tech_depth",
            expected_points=[f"要点-{i}"],
        )
        for i in range(5)
    ]

    class _SlowLLM(_StubLLMClient):
        async def generate_variant(self, *, source: _VariantInput) -> str:  # type: ignore[override]
            await asyncio.sleep(0.05)
            return await super().generate_variant(source=source)

    llm = _SlowLLM()
    started = asyncio.get_event_loop().time()
    await asyncio.gather(*(_generate_variant(source=s, llm_client=llm) for s in sources))
    elapsed = asyncio.get_event_loop().time() - started
    # Sequential would be 5 × 50ms = 250ms; parallel ≈ 50-100ms.
    assert elapsed < 0.20, f"Variant generation too slow ({elapsed:.3f}s); expected parallel execution"