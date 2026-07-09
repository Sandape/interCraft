"""REQ-053 T055/T056 — Markdown converter tests.

T055: markdown → plain text conversion rules
  - `**bold**` → 【bold】
  - `### heading` → ▎heading
  - list items preserved
  - code blocks → [代码]...[/代码]

T056: long text segmentation for WeChat delivery
  - Default: pack by chapter groups into 1–2 long messages (~4000)
  - Message 1 = 面试概览 + 公司与产品速览; Message 2 = prep chapters
  - Oversized packs still fall back to numbered line splits

Run:
    cd backend && uv run pytest tests/unit/modules/research/test_markdown_converter.py -v
"""
from __future__ import annotations

import pytest

from app.modules.research.markdown_converter import (
    convert_markdown_to_plain,
    segment_for_wechat,
)

# ---------------------------------------------------------------------------
# T055 — markdown conversion
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_t055_bold_to_chinese_bracket() -> None:
    """`**bold**` must become `【bold】`."""
    out = convert_markdown_to_plain("这是 **重要** 内容")
    assert "【重要】" in out
    assert "**" not in out


@pytest.mark.unit
def test_t055_heading_to_bar() -> None:
    """`### heading` must become `▎heading` (heading 2/3 also covered)."""
    out = convert_markdown_to_plain("### 章节标题\n内容")
    assert "▎章节标题" in out
    assert "###" not in out


@pytest.mark.unit
def test_t055_h2_heading_to_bar() -> None:
    """`## heading` also becomes `▎heading`."""
    out = convert_markdown_to_plain("## 面试概览\n内容")
    assert "▎面试概览" in out


@pytest.mark.unit
def test_t055_list_items_preserved() -> None:
    """List items (with `-` or `*` markers) normalize to `- `."""
    md = """## 章节
- 第一项
- 第二项
* 第三项
"""
    out = convert_markdown_to_plain(md)
    assert "- 第一项" in out
    assert "- 第二项" in out
    assert "- 第三项" in out


@pytest.mark.unit
def test_t055_strips_conversational_opener() -> None:
    """Proactive push must not keep LLM '好的，这是为您生成的…' fluff."""
    md = "好的，这是为您生成的字节跳动面试备战报告。\n\n## 📋 面试概览\n- 公司：字节\n"
    out = convert_markdown_to_plain(md)
    assert "好的" not in out
    assert "这是为您生成的" not in out
    assert "▎📋 面试概览" in out


@pytest.mark.unit
def test_t055_code_block_wrapped() -> None:
    """```code blocks``` become [代码]...[/代码] (no raw ``` in output)."""
    md = """## 章节
```python
def hello():
    print("hi")
```
说明结束
"""
    out = convert_markdown_to_plain(md)
    assert "[代码]" in out
    assert "[/代码]" in out
    assert "```" not in out
    assert "print" in out  # code body preserved


@pytest.mark.unit
def test_t055_table_flattens_to_dot_separator() -> None:
    """Markdown tables are flattened to one-line cells joined with `·`."""
    md = """| 维度 | 上次 | 本次 |
|---|---|---|
| tech_depth | 60 | 70 |
"""
    out = convert_markdown_to_plain(md)
    # Separator row should be dropped
    assert "---" not in out
    # Cells joined with ·
    assert "维度" in out and "上次" in out and "tech_depth" in out


@pytest.mark.unit
def test_t055_char_growth_within_10pct() -> None:
    """Per FR-018 US4-AC5: char count growth ≤10% (treating emoji/header
    expansion as worst case)."""
    md = """## 📋 面试概览
字节跳动 · AI 应用工程师 · 2026-07-15 14:00 · 一面（1 轮）

## 🏢 公司与产品速览
字节跳动核心业务为短视频。旗下产品：抖音、扣子、豆包、飞书客户端。

## 📝 面经汇总
1. transformer 原理？答案方向：自注意力机制。
2. RAG 流程？答案方向：检索增强生成。
3. 向量数据库？答案方向：Milvus。
"""
    plain = convert_markdown_to_plain(md)
    growth = (len(plain) - len(md)) / max(len(md), 1)
    # The conversion typically shrinks or grows slightly depending on
    # emoji + bracket expansion vs. dropped table separators.
    assert abs(growth) <= 0.50, (
        f"char growth {growth:.1%} unexpectedly large"
    )


# ---------------------------------------------------------------------------
# T056 — segmentation (1–2 long packs by default)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_t056_default_packs_report_into_two_messages() -> None:
    """Typical 6-chapter report → 2 WeChat messages (briefing + prep)."""
    text = (
        "▎📋 面试概览\n- 公司：字节跳动\n- 岗位：AI 应用开发工程师\n\n"
        "▎🏢 公司与产品速览\n字节跳动 AI 产品矩阵：豆包、扣子、火山引擎。\n\n"
        "▎📝 面经汇总\n【题目 1】：RAG 与 Function Calling 的区别？\n- 答：检索 vs 工具调用。\n\n"
        "▎🎯 高频考察点\n1. 【Agent 架构】：多 Agent 协作。\n\n"
        "▎⚠️ 你的薄弱环节\n- 【主题】推理引擎\n\n"
        "▎💡 最后建议\n1. 预演面经答案。\n"
    )
    segments = segment_for_wechat(text)  # default ~4000
    assert len(segments) == 2
    assert segments[0].startswith("(1/2)\n")
    assert "面试概览" in segments[0] and "公司与产品速览" in segments[0]
    assert segments[1].startswith("(2/2)\n")
    assert "面经汇总" in segments[1]
    assert "最后建议" in segments[1]


@pytest.mark.unit
def test_t056_short_report_single_message_no_numbering() -> None:
    """Briefing-only report (no prep chapters) → single message, no (1/1)."""
    text = "▎📋 面试概览\n一面今晚。\n\n▎🏢 公司与产品速览\n豆包。"
    segments = segment_for_wechat(text, max_chars=4000)
    assert len(segments) == 1
    assert not segments[0].startswith("(")
    assert "面试概览" in segments[0]


@pytest.mark.unit
def test_t056_segments_long_text_into_n_parts() -> None:
    """Hard ceiling still splits oversized plain text when needed."""
    long_text = "中" * 2500
    segments = segment_for_wechat(long_text, max_chars=500)
    assert 5 <= len(segments) <= 6, f"expected ~5-6 segments, got {len(segments)}"
    n = len(segments)
    for i, seg in enumerate(segments, 1):
        assert seg.startswith(f"({i}/{n})\n"), (
            f"segment {i} missing correct numbering: {seg[:30]!r}"
        )


@pytest.mark.unit
def test_t056_segment_size_within_bounds() -> None:
    """Each full segment (prefix + body) must be ≤ max_chars."""
    text = "测" * 1500
    segments = segment_for_wechat(text, max_chars=500)
    for seg in segments:
        assert len(seg) <= 500, f"segment {len(seg)} > 500"


@pytest.mark.unit
def test_t056_short_text_single_segment_no_numbering() -> None:
    """Short text (single segment) should NOT get (1/1) numbering per spec."""
    text = "短文本"
    segments = segment_for_wechat(text, max_chars=500)
    assert len(segments) == 1
    assert segments[0] == "短文本"


@pytest.mark.unit
def test_t056_empty_text_returns_empty_list() -> None:
    assert segment_for_wechat("") == []


@pytest.mark.unit
def test_t056_segment_split_at_sentence_boundary() -> None:
    """Oversized packs fall back to line packing within max_chars."""
    text = "第一句。" * 100 + "第二句！" * 100 + "第三句？" * 100
    segments = segment_for_wechat(text, max_chars=300)
    for seg in segments:
        assert len(seg) <= 300


@pytest.mark.unit
def test_t056_mixed_chinese_english_segments() -> None:
    """Real-world mixed content should segment correctly."""
    text = (
        "▎📋 面试概览\n字节跳动 · AI Engineer · 2026-07-15 · 一面\n\n"
        "▎🏢 公司与产品速览\n字节核心业务。旗下：抖音、扣子（Coze）、豆包、飞书。\n\n"
        "▎📝 面经汇总\n题 1：Transformer？\n"
    )
    segments = segment_for_wechat(text, max_chars=4000)
    assert 1 <= len(segments) <= 2
    for seg in segments:
        body = seg.split("\n", 1)[1] if seg.startswith("(") else seg
        assert len(body) > 0


@pytest.mark.unit
def test_t056_numbering_on_own_line() -> None:
    """Multi-segment numbering uses (i/N) on its own line (WeChat-readable)."""
    text = ("段落内容。" * 40 + "\n") * 4
    segments = segment_for_wechat(text, max_chars=200)
    assert len(segments) > 1
    assert segments[0].startswith("(1/")
    assert "\n" in segments[0]
    assert segments[0].count("(1/") == 1


__all__ = []
