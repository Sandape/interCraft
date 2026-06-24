"""ChineseFidelityChecker unit tests (Phase 2 TDD).

Validates the core defensive gate that catches the DeepSeek V4 Pro regression
where a zh-CN prompt silently produced English `summary_md` / `feedback`
(per `interview_report_chinese_caveat` lesson).

The checker MUST flag:
- Pure English text when zh-CN is expected (the regression)
- English-dominant segments even when wrapped in JSON

The checker MUST NOT flag:
- Pure Chinese text
- Chinese text with mixed English tech terms (React / useState / useMemo)
- Empty / whitespace edge cases are flagged as fail (no content = no fidelity)
"""
from __future__ import annotations

import pytest

from app.eval.checker import ChineseFidelityChecker, ChineseFidelityResult


@pytest.fixture
def checker() -> ChineseFidelityChecker:
    return ChineseFidelityChecker()


class TestChineseFidelityPureChinese:
    """Pure Chinese text should pass fidelity check."""

    def test_pure_chinese_text_passes(self, checker: ChineseFidelityChecker) -> None:
        text = "候选人对虚拟节点比较算法的理解非常深入，能够准确解释同层比较和差异更新策略。"
        result = checker.check(text, expected_language="zh-CN")
        assert result.is_correct is True, (
            f"pure Chinese text should pass; got ratio={result.chinese_ratio}"
        )
        assert result.chinese_ratio >= 0.7, (
            f"Chinese ratio should be ≥ 0.7; got {result.chinese_ratio}"
        )
        assert result.score == result.chinese_ratio
        assert result.expected_language == "zh-CN"

    def test_long_chinese_paragraph_passes(self, checker: ChineseFidelityChecker) -> None:
        text = (
            "候选人在本次面试中整体表现良好，沟通清晰、技术基础扎实。"
            "在前端工程化方面有较深的实践经验，能够清晰描述 Vite 构建流程的优化点。"
            "不足之处在于对服务端渲染的细节理解不够深入，建议加强同构渲染相关的学习。"
        )
        result = checker.check(text, expected_language="zh-CN")
        assert result.is_correct is True
        assert result.chinese_ratio >= 0.7


class TestChineseFidelityPureEnglish:
    """Pure English text when zh-CN expected should fail — this is the regression."""

    def test_pure_english_text_fails(self, checker: ChineseFidelityChecker) -> None:
        text = "The candidate demonstrated solid understanding of React diff algorithm."
        result = checker.check(text, expected_language="zh-CN")
        assert result.is_correct is False, (
            "pure English text should fail fidelity check (the regression we catch)"
        )
        assert result.english_ratio >= 0.7
        assert result.chinese_ratio < 0.3

    def test_english_feedback_regression_caught(self, checker: ChineseFidelityChecker) -> None:
        """Regression case: DeepSeek returned English feedback despite zh-CN prompt.

        This is the exact regression that motivated the eval suite — see
        `interview_report_chinese_caveat` memory.
        """
        text = (
            '{"score": 8, "dimension": "tech_depth", '
            '"feedback": "The candidate showed good understanding of React hooks '
            'and lifecycle methods, with minor gaps in error boundaries.", '
            '"sub_scores": {"clarity": 8, "depth": 7, "relevance": 8}}'
        )
        result = checker.check(text, expected_language="zh-CN")
        assert result.is_correct is False, (
            "English feedback in JSON wrapper must be caught — this is the regression"
        )
        # violation_segments should capture the English feedback phrase
        assert len(result.violation_segments) > 0, (
            "violation_segments should list the English-dominant segments"
        )

    def test_english_summary_md_regression_caught(
        self, checker: ChineseFidelityChecker
    ) -> None:
        """Regression case: DeepSeek returned English summary_md despite zh-CN prompt."""
        text = (
            '{"overall_score": 7.25, "summary_md": '
            '"The candidate performed well overall, with strong communication '
            'and solid technical fundamentals. Areas for improvement include '
            'deeper knowledge of server-side rendering."}'
        )
        result = checker.check(text, expected_language="zh-CN")
        assert result.is_correct is False, (
            "English summary_md in JSON wrapper must be caught"
        )


class TestChineseFidelityMixed:
    """Chinese text with English tech terms should pass (allow English术语混入)."""

    def test_chinese_with_english_tech_terms_passes(
        self, checker: ChineseFidelityChecker
    ) -> None:
        text = (
            "候选人熟练掌握 React hooks 包括 useState、useEffect、useMemo，"
            "能清晰解释 virtual DOM 与 reconciliation 的关系。"
            "在 TypeScript 类型推导方面有不错的实践，建议加强 Server Components 学习。"
        )
        result = checker.check(text, expected_language="zh-CN")
        assert result.is_correct is True, (
            f"Chinese text with English tech terms should pass; ratio={result.chinese_ratio}"
        )
        assert result.chinese_ratio >= 0.3, (
            "Chinese-dominant text with tech terms should have ratio ≥ 0.3"
        )

    def test_json_with_chinese_values_passes(self, checker: ChineseFidelityChecker) -> None:
        """JSON wrapper + Chinese values should pass — JSON keys are English by design."""
        text = (
            '{"score": 9, "dimension": "tech_depth", '
            '"feedback": "候选人对 React diff 算法理解深入，能准确解释同层比较策略。", '
            '"sub_scores": {"clarity": 9, "depth": 9, "relevance": 9}}'
        )
        result = checker.check(text, expected_language="zh-CN")
        assert result.is_correct is True, (
            f"JSON with Chinese values should pass; ratio={result.chinese_ratio}"
        )


class TestChineseFidelityEdgeCases:
    """Edge cases — empty / punctuation-only / non-zh-CN expectations."""

    def test_empty_string_fails(self, checker: ChineseFidelityChecker) -> None:
        result = checker.check("", expected_language="zh-CN")
        assert result.is_correct is False
        assert result.score == 0.0
        assert result.chinese_ratio == 0.0
        assert result.english_ratio == 0.0

    def test_whitespace_only_fails(self, checker: ChineseFidelityChecker) -> None:
        result = checker.check("   \n\t  ", expected_language="zh-CN")
        assert result.is_correct is False
        assert result.score == 0.0

    def test_only_punctuation_fails(self, checker: ChineseFidelityChecker) -> None:
        """JSON structural chars / digits / punctuation only — no linguistic content."""
        result = checker.check('{"score": 5, "feedback": ""}', expected_language="zh-CN")
        # Empty feedback value → no Chinese content → should fail
        assert result.is_correct is False, (
            "JSON with empty feedback should fail (no actual Chinese content)"
        )

    def test_digits_only_fails(self, checker: ChineseFidelityChecker) -> None:
        result = checker.check("12345 6789", expected_language="zh-CN")
        assert result.is_correct is False


class TestViolationSegmentExtraction:
    """violation_segments should extract English-dominant spans for diagnostics."""

    def test_english_only_segment_extracted(
        self, checker: ChineseFidelityChecker
    ) -> None:
        """A run of ≥ 5 English words should be captured as a violation segment."""
        text = (
            "候选人回答不错，"
            "The candidate demonstrated solid understanding of the topic "
            "但建议加强深度。"
        )
        result = checker.check(text, expected_language="zh-CN")
        assert len(result.violation_segments) > 0, (
            "long English run should be captured as violation_segment"
        )
        # The first violation segment should contain English words
        assert any("candidate" in seg.lower() for seg in result.violation_segments), (
            f"violation_segments should mention 'candidate'; got {result.violation_segments}"
        )

    def test_short_english_terms_not_flagged_as_segment(
        self, checker: ChineseFidelityChecker
    ) -> None:
        """Short English tech terms (React / useState) should NOT be violation_segments."""
        text = "候选人熟练使用 React 和 useState，能解释 virtual DOM。"
        result = checker.check(text, expected_language="zh-CN")
        assert result.is_correct is True
        # Short English tokens are fine — should not produce violation segments
        assert all(len(seg.split()) < 5 for seg in result.violation_segments), (
            f"short English terms should not be flagged; got {result.violation_segments}"
        )


class TestResultShape:
    """ChineseFidelityResult dataclass shape (for serialization)."""

    def test_result_has_all_required_fields(
        self, checker: ChineseFidelityChecker
    ) -> None:
        result = checker.check("测试文本", expected_language="zh-CN")
        assert isinstance(result, ChineseFidelityResult)
        assert hasattr(result, "expected_language")
        assert hasattr(result, "is_correct")
        assert hasattr(result, "chinese_ratio")
        assert hasattr(result, "english_ratio")
        assert hasattr(result, "violation_segments")
        assert hasattr(result, "score")

    def test_violation_segments_is_list(self, checker: ChineseFidelityChecker) -> None:
        result = checker.check("测试", expected_language="zh-CN")
        assert isinstance(result.violation_segments, list)
