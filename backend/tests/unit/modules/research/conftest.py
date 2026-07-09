"""Shared fixtures for REQ-053 research tests.

Provides:
- `mock_session` — a MagicMock AsyncSession for unit tests
- `sample_search_results` — 4-dimension search fixture
- `sample_user_weakness` — ability dimension + error tag fixture
- `sample_report_md` — a valid 6-section report for quality testing
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def mock_session() -> MagicMock:
    """A MagicMock that mimics AsyncSession."""
    s = MagicMock()
    s.execute = AsyncMock()
    s.commit = AsyncMock()
    s.flush = AsyncMock()
    s.refresh = AsyncMock()
    return s


@pytest.fixture
def sample_search_results() -> dict[str, list[dict[str, Any]]]:
    return {
        "interview_experience": [
            {"title": "字节 AI 一面", "url": "https://example.com/1",
             "content": "transformer + RAG + self-attention"},
            {"title": "字节 AI 二面", "url": "https://example.com/2",
             "content": "Agent 设计 + LangChain + 向量数据库"},
        ],
        "company_product": [
            {"title": "字节扣子", "url": "https://example.com/3",
             "content": "扣子是字节 AI Agent 平台"},
            {"title": "字节豆包", "url": "https://example.com/4",
             "content": "豆包大模型 1.5 Pro"},
        ],
        "exam_points": [
            {"title": "AI 工程师考点", "url": "https://example.com/5",
             "content": "Transformer/RAG/Agent"},
        ],
    }


@pytest.fixture
def sample_user_weakness() -> dict[str, Any]:
    return {
        "dimensions": [
            {"key": "tech_depth", "score": 65.0, "improvements": ["Transformer"]},
            {"key": "architecture", "score": 60.0, "improvements": ["RAG"]},
        ],
        "error_question_tags": ["self-attention", "RAG", "vector db"],
        "has_ability_data": True,
    }


@pytest.fixture
def sample_report_md() -> str:
    return """## 📋 面试概览
字节跳动 · AI 应用工程师 · 2026-07-15 14:00 · 一面（1 轮）

## 🏢 公司与产品速览
字节核心业务短视频。旗下产品：抖音、扣子、豆包、飞书客户端、剪映 APP。

## 📝 面经汇总
1. transformer 原理？答案方向：自注意力机制。
2. RAG 流程？答案方向：检索增强生成。
3. 向量数据库选型？答案方向：Milvus vs Pinecone。
4. LangChain vs LlamaIndex？答案方向：通用 vs RAG 友好。
5. Agent 编排？答案方向：ReAct / Function Calling。

## 🎯 高频考察点
- transformer | 必问 | 高
- RAG | 必问 | 高
- 向量检索 | 深入 | 中
- Agent 设计 | 工具调用 | 中

## ⚠️ 你的薄弱环节
tech_depth 得分 65，重点复习 self-attention 手写。
architecture 得分 60，建议拆解 RAG pipeline。

## 💡 最后建议
1. 复习 transformer 完整推导
2. 准备好 1 分钟自我介绍
3. 了解扣子产品最新版本
"""


@pytest.fixture
def sample_historical_comparison() -> dict[str, Any]:
    return {
        "previous_report_id": "11111111-1111-1111-1111-111111111111",
        "previous_generated_at": datetime.now(UTC).isoformat(),
        "previous_dimensions": [
            {"key": "tech_depth", "score": 60.0},
            {"key": "architecture", "score": 55.0},
        ],
        "current_dimensions": [
            {"key": "tech_depth", "score": 70.0},
            {"key": "architecture", "score": 60.0},
        ],
    }
