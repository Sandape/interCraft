"""Unit tests for report_generator post-processing helpers."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.modules.research.report_generator import (
    _drop_empty_history_section,
    _ensure_countdown,
    _format_countdown,
    _strip_fluff,
)


@pytest.mark.unit
def test_strip_fluff_removes_opener() -> None:
    md = "好的，这是为您生成的字节跳动 AI 应用开发工程师面试备战报告。\n\n## 📋 面试概览\n- x"
    assert _strip_fluff(md).startswith("## 📋 面试概览")


@pytest.mark.unit
def test_format_countdown_future() -> None:
    now = datetime(2026, 7, 9, 11, 0, 0, tzinfo=timezone.utc)
    # 15:06 UTC = 23:06 BJ — 4h6m after 11:00 UTC
    out = _format_countdown("2026-07-09T15:06:00Z", now=now)
    assert "小时" in out and "分钟" in out


@pytest.mark.unit
def test_ensure_countdown_replaces_placeholder() -> None:
    md = "## 📋 面试概览\n- **倒计时**：请根据当前日期计算。如果今天是 2026 年 7 月 9 日，面试就在今晚。\n"
    out = _ensure_countdown(md, "约 4 小时 50 分钟后")
    assert "约 4 小时 50 分钟后" in out
    assert "请根据当前日期计算" not in out


@pytest.mark.unit
def test_drop_empty_history_section() -> None:
    md = (
        "## 💡 最后建议\n1. a\n\n"
        "## 📊 历史对比\n你还没有足够的面试数据，完成一次模拟面试后可生成个性化薄弱点分析。"
    )
    out = _drop_empty_history_section(md)
    assert "历史对比" not in out
    assert "最后建议" in out
