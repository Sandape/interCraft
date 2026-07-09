"""REQ-053 T047 — quality checker tests.

Five scenarios (FR-018):
1. Empty / too-short report → fails with `report_too_short`
2. Template-only report (no substance, placeholder text) → fails with `template_only`
3. Good report with company + 3+ questions + ability ref → passes
4. Report without ability ref but user_has_ability_data=False → still passes (skip rule)
5. Report with <3 questions → fails with `insufficient_interview_questions`

These tests use pure functions; no LLM / DB needed.

Run:
    cd backend && uv run pytest tests/unit/modules/research/test_quality.py -v
"""
from __future__ import annotations

import pytest

from app.modules.research.quality_checker import check_report_quality

pytestmark = [pytest.mark.unit]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _good_report(company: str = "字节跳动") -> str:
    return f"""## 📋 面试概览
{company} · AI 应用工程师 · 2026-07-15 14:00 · 一面（1 轮）

## 🏢 公司与产品速览
{company}核心业务短视频 · 旗下产品：抖音、扣子、豆包、飞书客户端

## 📝 面经汇总
1. transformer 的 self-attention 公式是什么？答案方向：softmax(QK^T / sqrt(d))V。
2. RAG 整体流程是什么？答案方向：chunking → embed → retrieve → rerank → generate。
3. 向量数据库怎么选？答案方向：Milvus vs Pinecone vs Qdrant。
4. LangChain vs LlamaIndex 区别？答案方向：通用框架 vs RAG 友好。
5. Agent 工具调用如何编排？答案方向：ReAct / Function Calling。

## 🎯 高频考察点
- transformer 原理 | 必问 | 高
- RAG 工程化 | 必问 | 高
- 向量检索 | 深入 | 中

## ⚠️ 你的薄弱环节
tech_depth 得分 65，重点复习 self-attention 手写。
architecture 得分 60，建议拆解 RAG pipeline。

## 💡 最后建议
1. 复习 transformer 完整推导
2. 准备 1 分钟自我介绍
3. 了解扣子产品最新版本
"""


# ---------------------------------------------------------------------------
# T047 — 5 scenarios
# ---------------------------------------------------------------------------


def test_t047_empty_report_fails_with_too_short() -> None:
    """Empty / very short report must fail with report_too_short."""
    passed, failures = check_report_quality(
        "", company="字节跳动", user_has_ability_data=True
    )
    assert passed is False
    assert "report_too_short" in failures


def test_t047_template_only_report_fails_with_template_only() -> None:
    """A report with placeholder text like '暂无公开信息' must fail."""
    template = """## 📋 面试概览
暂无公开信息
## 🏢 公司与产品速览
待补充
## 📝 面经汇总
内容不足
## 🎯 高频考察点
placeholder
## ⚠️ 你的薄弱环节
无法获取
## 💡 最后建议
内容不足
"""
    passed, failures = check_report_quality(
        template, company="字节跳动", user_has_ability_data=False
    )
    assert passed is False
    # `report_too_short` or `template_only` should appear
    assert any("template_only" in f or "report_too_short" in f for f in failures)


def test_t047_good_report_passes() -> None:
    """A well-formed report with company + 3+ questions + ability ref passes."""
    passed, failures = check_report_quality(
        _good_report(), company="字节跳动", user_has_ability_data=True
    )
    assert passed is True, f"good report should pass, got failures={failures}"
    assert failures == []


def test_t047_no_ability_ref_skipped_when_user_has_no_data() -> None:
    """When user_has_ability_data=False, the ability-dimension rule is skipped."""
    # Report has no ability dimension mention but has all other requirements
    report = """## 📋 面试概览
字节跳动 · AI · 2026-07-15 · 一面

## 🏢 公司与产品速览
字节核心业务短视频。旗下产品：抖音、扣子、豆包、飞书客户端、剪映 APP。

## 📝 面经汇总
1. transformer 原理？答案方向：自注意力机制。
2. RAG 流程？答案方向：检索增强生成。
3. 向量数据库？答案方向：Milvus。
4. Agent 编排？答案方向：ReAct。

## 🎯 高频考察点
- transformer | 必问 | 高
- RAG | 必问 | 高

## ⚠️ 你的薄弱环节
你还没有足够的面试数据，完成一次模拟面试后可生成个性化薄弱点分析。

## 💡 最后建议
1. 复习 transformer
2. 准备好 1 分钟自我介绍
3. 了解扣子产品
"""
    passed, failures = check_report_quality(
        report, company="字节跳动", user_has_ability_data=False
    )
    assert passed is True, f"new-user report should pass, got {failures}"


def test_t047_insufficient_questions_fails() -> None:
    """A report with only 2 interview questions must fail."""
    report = """## 📋 面试概览
字节跳动 · AI · 2026-07-15 · 一面

## 🏢 公司与产品速览
字节核心业务。旗下产品：抖音、扣子、豆包、飞书 APP。

## 📝 面经汇总
1. transformer 原理？答案方向：自注意力机制。
2. RAG 流程？答案方向：检索增强生成。

## 🎯 高频考察点
- transformer | 必问 | 高

## ⚠️ 你的薄弱环节
tech_depth 得分 65。

## 💡 最后建议
1. 复习 transformer
"""
    passed, failures = check_report_quality(
        report, company="字节跳动", user_has_ability_data=True
    )
    assert passed is False
    assert any("insufficient_interview_questions" in f for f in failures), failures


# ---------------------------------------------------------------------------
# Bonus: edge cases
# ---------------------------------------------------------------------------


def test_t047_question_count_handles_chinese_numbering() -> None:
    """Chinese numbering (一二三) for questions must be counted."""
    report = """## 📋 面试概览
字节跳动 · AI · 一面

## 🏢 公司与产品速览
抖音、扣子、豆包、飞书 APP。

## 📝 面经汇总
一、transformer 原理？答案方向：自注意力机制。
二、RAG 流程？答案方向：检索增强生成。
三、向量数据库？答案方向：Milvus。
四、Agent 编排？答案方向：ReAct。

## 🎯 高频考察点
- transformer | 高

## ⚠️ 你的薄弱环节
tech_depth 得分 65。

## 💡 最后建议
1. 复习 transformer
2. 自我介绍
3. 了解扣子产品
"""
    passed, failures = check_report_quality(
        report, company="字节跳动", user_has_ability_data=True
    )
    assert passed is True, f"chinese-numbered questions should count, got {failures}"


def test_t047_report_without_company_mention_fails() -> None:
    """A report that doesn't mention the company or any product name fails.

    Carefully written to avoid product-suffix patterns (e.g. 后端, 客户端,
    系统) that would falsely satisfy the regex. Each phrase here is short
    and uses common particles that don't trigger the product suffix regex.
    """
    report = """## 📋 面试概览
AI · 一面 · 七月

## 🏢 公司与产品速览
我们今天聊聊岗位方向相关内容。

## 📝 面经汇总
1. transformer 原理？答案方向：自注意力机制。
2. RAG 流程？答案方向：检索增强生成。
3. 大模型微调？答案方向：LoRA 与全参对比。

## 🎯 高频考察点
- transformer | 高

## ⚠️ 你的薄弱环节
tech_depth 得分 65。

## 💡 最后建议
1. 复习 transformer
"""
    passed, failures = check_report_quality(
        report, company="字节跳动", user_has_ability_data=True
    )
    assert passed is False
    assert any("no_company_or_product" in f for f in failures), failures


__all__ = []
