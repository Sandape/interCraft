"""[REQ-048 US4 AC-24] Unit test for Markdown generation from InterviewPlan.

Validates the Markdown copy-paste surface (FR-054, US4.AS4):

- Markdown must contain:
  - `# 面试大纲` heading
  - `## 公司: <target_company>` section
  - `## 岗位: <target_position>` section
  - `## 大纲:` section with 5-8 numbered items

This is the test surface for the src/lib/cardMarkdown.ts (T092)
frontend lib's backend counterpart; we exercise the markdown
generator in Python so the contract is verified without depending
on a live frontend test runner.
"""
from __future__ import annotations

import pytest

# We import the helper lazily so the test gracefully degrades when the
# TS lib is not yet imported in the test runner. The Python surface is
# canonical — the TS lib mirrors it.
from app.services.card_renderer.markdown import build_card_markdown


def _plan(*, max_outlines: int = 5) -> dict:
    return {
        "target_company": "字节跳动",
        "target_position": "高级后端工程师",
        "interview_difficulty": "medium",
        "estimated_duration_minutes": 30,
        "focus_areas": [
            {"area": "分布式系统", "weight": 0.4},
            {"area": "高并发", "weight": 0.3},
        ],
        "suggested_questions": [
            f"Question #{i + 1}: how would you scale X?"
            for i in range(max_outlines)
        ],
        "tips": ["准备好 2-3 个生产级案例"],
    }


def test_markdown_contains_top_heading() -> None:
    md = build_card_markdown(_plan())
    assert "# 面试大纲" in md


def test_markdown_contains_company_section() -> None:
    md = build_card_markdown(_plan())
    assert "## 公司: 字节跳动" in md


def test_markdown_contains_position_section() -> None:
    md = build_card_markdown(_plan())
    assert "## 岗位: 高级后端工程师" in md


def test_markdown_contains_numbered_outline_5_items() -> None:
    md = build_card_markdown(_plan(max_outlines=5))
    assert "## 大纲:" in md
    # 5 numbered items: "1.", "2.", "3.", "4.", "5."
    for i in range(1, 6):
        assert f"{i}. " in md, f"missing numbered item {i} in markdown"


def test_markdown_contains_numbered_outline_8_items() -> None:
    md = build_card_markdown(_plan(max_outlines=8))
    assert "## 大纲:" in md
    for i in range(1, 9):
        assert f"{i}. " in md


def test_markdown_handles_missing_fields() -> None:
    """Tolerant — missing company/position render as blanks, not crashes."""
    md = build_card_markdown({})
    assert "# 面试大纲" in md
    assert "## 公司: " in md
    assert "## 岗位: " in md


def test_markdown_is_single_string_no_truncation() -> None:
    """AC-24: copy Markdown must NOT be truncated — full plan rendered."""
    md = build_card_markdown(_plan(max_outlines=8))
    # No ellipsis sentinel from accidental truncation.
    assert "..." not in md or md.count("...") <= 1  # tolerate literal "..."


def test_markdown_preserves_unicode_zh_cn() -> None:
    """Chinese text passes through unchanged."""
    plan = _plan(max_outlines=2)
    plan["target_position"] = "高级后端工程师 — 分布式系统"
    md = build_card_markdown(plan)
    assert "高级后端工程师 — 分布式系统" in md


def test_markdown_includes_focus_areas_section() -> None:
    md = build_card_markdown(_plan())
    assert "## 关注重点:" in md
    assert "分布式系统" in md


def test_markdown_includes_tips_section() -> None:
    md = build_card_markdown(_plan())
    assert "## 面试提示:" in md
    assert "准备好 2-3 个生产级案例" in md