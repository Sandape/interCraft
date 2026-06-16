"""019 — build_requirements_block unit tests (US3, FR-013).

Verifies the prompt-injection helper handles:
- empty / whitespace-only input → empty block, provided=False
- short requirements → header + body, provided=True, truncated=False
- long requirements (over MAX_REQUIREMENTS_TOKENS) → truncated=True,
  body bounded near the cap
- non-string input (None) → safe default
"""
from __future__ import annotations

import pytest

from app.agents.interview.requirements_block import (
    MAX_REQUIREMENTS_TOKENS,
    build_requirements_block,
    estimate_tokens,
)


class TestBuildRequirementsBlock:
    def test_none_input_returns_empty_block_not_provided(self) -> None:
        text, provided, truncated, original = build_requirements_block(None)
        assert text == ""
        assert provided is False
        assert truncated is False
        assert original == 0

    def test_empty_string_returns_empty_block(self) -> None:
        text, provided, truncated, original = build_requirements_block("")
        assert text == ""
        assert provided is False
        assert original == 0

    def test_whitespace_only_returns_empty_block(self) -> None:
        text, provided, truncated, original = build_requirements_block("   \n\t  ")
        assert text == ""
        assert provided is False
        assert original == 0

    def test_short_requirements_returned_unchanged(self) -> None:
        req = "## 岗位要求\n- 3年 React 经验\n- 熟悉可视化"
        text, provided, truncated, original = build_requirements_block(req, max_tokens=500)
        assert provided is True
        assert truncated is False
        assert original == len(req)
        assert "## 岗位招聘需求" in text
        assert "3年 React 经验" in text

    def test_long_requirements_gets_truncated(self) -> None:
        # Build a long Chinese requirements doc — ~3x the cap
        per_item = "需要熟悉 React 生态、性能优化、TypeScript 高级类型、大型项目工程化。"
        req = "\n".join(per_item for _ in range(200))
        text, provided, truncated, original = build_requirements_block(req, max_tokens=200)
        assert provided is True
        assert truncated is True
        assert original == len(req)
        # Body should be shorter than the original
        assert len(text) < len(req) + 100
        # Header should reflect the truncation
        assert "已截断" in text

    def test_estimate_tokens_is_positive_for_non_empty(self) -> None:
        assert estimate_tokens("") == 0
        # Chinese-heavy string should estimate at > 0
        assert estimate_tokens("前端工程师") > 0
        # ASCII string should also estimate at > 0
        assert estimate_tokens("hello world") > 0


class TestMaxRequirementsTokens:
    def test_max_requirements_tokens_default_is_1500(self) -> None:
        assert MAX_REQUIREMENTS_TOKENS == 1500
