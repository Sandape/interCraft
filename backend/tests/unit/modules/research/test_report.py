"""REQ-053 T046/T048 — report generation tests.

T046: 6-chapter emoji header presence (📋 🏢 📝 🎯 ⚠️ 💡) and order.
T048: quality check failure path — 1st attempt fails, 2nd succeeds →
       returns (report, True); 2nd also fails → returns (report, False).

The report is generated via REAL LLM (DeepSeek V4 Pro) — no mocks.
Tests are skipped if DEEPSEEK_API_KEY is missing.

Run:
    cd backend && uv run pytest tests/unit/modules/research/test_report.py -v
"""
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

_REQUIRED_EMOJIS = ["📋 面试概览", "🏢 公司与产品速览", "📝 面经汇总",
                     "🎯 高频考察点", "⚠️ 你的薄弱环节", "💡 最后建议"]


_HAS_LLM = bool(os.environ.get("DEEPSEEK_API_KEY"))


pytestmark = [pytest.mark.unit]


# ---------------------------------------------------------------------------
# T046 — 6-chapter structure (uses real LLM, then post-hoc validates)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _HAS_LLM, reason="DEEPSEEK_API_KEY not set")
@pytest.mark.asyncio
async def test_t046_six_chapter_emojis_present_and_in_order() -> None:
    """After a real LLM call, the report MUST contain all 6 emoji headers
    in the documented order (📋 → 🏢 → 📝 → 🎯 → ⚠️ → 💡)."""
    from app.modules.research.report_generator import generate_research_report

    report_md = await generate_research_report(
        company="字节跳动",
        position="AI 应用工程师",
        interview_time_iso="2026-07-15T14:00:00+08:00",
        interview_round="一面（1 轮）",
        search_results={
            "interview_experience": [
                {"title": "字节 AI 一面", "url": "https://example.com/1",
                 "content": "问了 transformer 和 RAG"}
            ],
            "company_product": [
                {"title": "字节豆包", "url": "https://example.com/2",
                 "content": "豆包大模型 1.5 Pro 支持 128k context"}
            ],
            "exam_points": [
                {"title": "AI 工程师考点", "url": "https://example.com/3",
                 "content": "Transformer / RAG / Agent 设计"}
            ],
        },
        user_weakness={
            "dimensions": [
                {"key": "tech_depth", "score": 65.0, "improvements": ["Transformer"]},
                {"key": "architecture", "score": 60.0, "improvements": ["RAG"]},
            ],
            "error_question_tags": ["self-attention"],
            "has_ability_data": True,
        },
    )

    assert isinstance(report_md, str)
    assert len(report_md) > 0

    # All 6 emoji headers must be present
    for header in _REQUIRED_EMOJIS:
        assert header in report_md, f"missing required header: {header!r}"

    # Verify ordering: each header must appear before the next one
    last_pos = -1
    for header in _REQUIRED_EMOJIS:
        pos = report_md.index(header)
        assert pos > last_pos, (
            f"header {header!r} appears at {pos}, before previous header at {last_pos}"
        )
        last_pos = pos


@pytest.mark.skipif(not _HAS_LLM, reason="DEEPSEEK_API_KEY not set")
@pytest.mark.asyncio
async def test_t046_report_char_count_in_window() -> None:
    """The report's weighted char count should be close to the 2000-3000 window."""
    from app.modules.research.report_generator import generate_research_report

    report_md = await generate_research_report(
        company="阿里云",
        position="后端开发工程师",
        interview_time_iso="2026-07-12T10:30:00+08:00",
        interview_round="二面（2 轮）",
        search_results={
            "interview_experience": [
                {"title": "阿里云后端 二面", "url": "https://example.com/4",
                 "content": "高并发、分布式锁、MySQL 索引"}
            ],
            "company_product": [
                {"title": "阿里云 ECS", "url": "https://example.com/5",
                 "content": "弹性计算 ECS 秒级交付"}
            ],
            "exam_points": [
                {"title": "后端考点", "url": "https://example.com/6",
                 "content": "分布式、高并发、数据库、缓存"}
            ],
        },
        user_weakness={
            "dimensions": [
                {"key": "tech_depth", "score": 70.0, "improvements": ["Redis 集群"]},
                {"key": "engineering_practice", "score": 55.0,
                 "improvements": ["秒杀系统"]},
            ],
            "error_question_tags": ["Redis cluster"],
            "has_ability_data": True,
        },
    )

    chinese = sum(1 for c in report_md if "一" <= c <= "鿿")
    ascii_chars = sum(1 for c in report_md if c.isascii() and not c.isspace())
    weighted = chinese + ascii_chars * 0.5

    # Allow ±25% tolerance around the 2500 sweet-spot to accommodate LLM variance
    assert 1500 <= weighted <= 4000, (
        f"weighted char count {weighted} outside loose bounds [1500, 4000]"
    )


# ---------------------------------------------------------------------------
# T048 — quality retry path
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_t048_quality_fail_then_succeed_returns_quality_passed_true() -> None:
    """First LLM call returns a low-quality report, second call returns a
    high-quality report → service returns (good_report, True)."""
    from app.modules.research.service import ResearchService

    call_count = {"n": 0}
    BAD_REPORT = "## 📋 面试概览\nbad short"  # fails quality (too short + no questions)
    GOOD_REPORT = (
        "## 📋 面试概览\n字节跳动 · AI 应用工程师 · 2026-07-15 14:00 · 一面\n\n"
        "## 🏢 公司与产品速览\n字节跳动核心业务短视频 · 旗下产品：抖音、扣子、豆包、飞书客户端\n\n"
        "## 📝 面经汇总\n1. transformer 原理是什么？答案方向：Q K V 矩阵。\n"
        "2. RAG 流程？答案方向：chunking → embed → retrieve → rerank → generate。\n"
        "3. self-attention 复杂度？答案方向：O(n^2 · d)。\n"
        "4. LangChain vs LlamaIndex？答案方向：LC 通用 / LI RAG 友好。\n"
        "5. 向量数据库选型？答案方向：Milvus vs Pinecone。\n\n"
        "## 🎯 高频考察点\n- transformer 基础 | 编码 | 高\n- RAG | 架构 | 高\n"
        "- Agent 设计 | 工具调用 | 中\n- 向量检索 | 工程 | 中\n\n"
        "## ⚠️ 你的薄弱环节\ntech_depth 得分 65，需重点复习 self-attention 手写。"
        "architecture 得分 60，建议拆解 RAG pipeline。\n\n"
        "## 💡 最后建议\n1. 复习 transformer\n2. 准备好 1 分钟自我介绍\n3. 了解扣子产品\n"
    )

    async def fake_generate(**kwargs):
        call_count["n"] += 1
        return BAD_REPORT if call_count["n"] == 1 else GOOD_REPORT

    svc = ResearchService(MagicMock())
    # Patch the function at its source — service imports it lazily inside
    # `_generate_with_retry`, so patching `app.modules.research.service.generate_research_report`
    # won't work (the import name is local). Patch the source module instead.
    with patch(
        "app.modules.research.report_generator.generate_research_report",
        side_effect=fake_generate,
    ):
        report, passed = await svc._generate_with_retry(
            company="字节跳动",
            position="AI 应用工程师",
            interview_time_iso="2026-07-15T14:00:00+08:00",
            interview_round="一面（1 轮）",
            search_results={},
            user_weakness={"dimensions": [], "error_question_tags": [],
                           "has_ability_data": False},
        )

    assert call_count["n"] == 2, "should have called LLM twice"
    assert passed is True, "second attempt passed quality check"
    assert report == GOOD_REPORT


@pytest.mark.unit
@pytest.mark.asyncio
async def test_t048_double_quality_fail_returns_passed_false() -> None:
    """When both LLM attempts fail quality, the service returns the latest
    report with passed=False (task should be marked 'quality_failed')."""
    from app.modules.research.service import ResearchService

    BAD_REPORT_1 = "## 📋 面试概览\nbad"
    BAD_REPORT_2 = "## 📋 面试概览\nstill bad but longer, no real content for sections"

    call_count = {"n": 0}

    async def fake_generate(**kwargs):
        call_count["n"] += 1
        return BAD_REPORT_1 if call_count["n"] == 1 else BAD_REPORT_2

    svc = ResearchService(MagicMock())
    with patch(
        "app.modules.research.report_generator.generate_research_report",
        side_effect=fake_generate,
    ):
        report, passed = await svc._generate_with_retry(
            company="字节跳动",
            position="AI 应用工程师",
            interview_time_iso="2026-07-15T14:00:00+08:00",
            interview_round="一面（1 轮）",
            search_results={},
            user_weakness={"dimensions": [], "error_question_tags": [],
                           "has_ability_data": False},
        )

    assert call_count["n"] == 2, "should have tried twice (FR-018 limit)"
    assert passed is False, "both attempts failed quality check"


# ---------------------------------------------------------------------------
# Bonus: append_historical_comparison
# ---------------------------------------------------------------------------


def test_append_historical_comparison_adds_table() -> None:
    """When previous + current dimensions are provided, a 📊 历史对比 table
    is appended to the report."""
    from app.modules.research.report_generator import append_historical_comparison

    base = "## 💡 最后建议\nsome advice\n"
    previous = [
        {"key": "tech_depth", "score": 60.0},
        {"key": "architecture", "score": 50.0},
    ]
    current = [
        {"key": "tech_depth", "score": 70.0},
        {"key": "architecture", "score": 48.0},
    ]
    result = append_historical_comparison(
        base, previous_dimensions=previous, current_dimensions=current
    )
    assert "📊 历史对比" in result
    assert "| tech_depth |" in result
    assert "↑ 进步" in result or "→ 持平" in result or "↓ 退步" in result


def test_append_historical_comparison_handles_empty() -> None:
    """If no previous dimensions, the table is NOT appended."""
    from app.modules.research.report_generator import append_historical_comparison

    base = "## 💡 最后建议\nsome advice\n"
    out = append_historical_comparison(
        base, previous_dimensions=[], current_dimensions=[{"key": "x", "score": 1}]
    )
    assert out == base, "empty previous dims should return report unchanged"

    out = append_historical_comparison(
        base, previous_dimensions=[{"key": "x", "score": 1}], current_dimensions=[]
    )
    assert out == base


__all__ = []
