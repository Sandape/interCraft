"""ChineseFidelityChecker — language fidelity gate for LLM outputs (T010/T011).

Directly targets the DeepSeek V4 Pro regression documented in
`interview_report_chinese_caveat`: a zh-CN prompt silently produced English
`summary_md` / `feedback`. This checker detects that regression so the eval
suite can block prompt-adjacent PRs that reintroduce it.

Approach: lightweight self-built (no langdetect / deepeval dependency).
Uses Unicode range detection + ratio threshold + English-segment extraction.

Threshold: `chinese_ratio >= 0.3` passes. This allows English tech terms
(React / useState / virtual DOM) to be mixed into Chinese text without false
positives, while catching fully-English paragraphs (which have ratio ~0).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Literal

# CJK Unicode ranges — covers CJK Unified Ideographs + common extensions.
# Source: https://en.wikipedia.org/wiki/CJK_Unified_Ideographs
_CJK_RANGES: tuple[tuple[int, int], ...] = (
    (0x4E00, 0x9FFF),    # CJK Unified Ideographs
    (0x3400, 0x4DBF),    # CJK Extension A
    (0x20000, 0x2A6DF),  # CJK Extension B
    (0x2A700, 0x2B73F),  # CJK Extension C
    (0x2B740, 0x2B81F),  # CJK Extension D
    (0x2B820, 0x2CEAF),  # CJK Extension E
    (0xF900, 0xFAFF),    # CJK Compatibility Ideographs
    (0x2F800, 0x2FA1F),  # CJK Compatibility Ideographs Supplement
)

# Minimum Chinese ratio to pass fidelity check. Allows English tech terms
# mixed in (React / useState typically appear in Chinese feedback).
# Empirically: pure Chinese = 0.7+, mixed = 0.3-0.7, pure English = 0.
_MIN_CHINESE_RATIO: float = 0.3

# A "violation segment" = ≥ 5 consecutive English words. Below this is treated
# as acceptable tech-term insertion (useEffect, virtual DOM, etc).
_MIN_ENGLISH_WORDS_FOR_VIOLATION: int = 5

# Regex: match ≥ 5 consecutive English words (incl. common punctuation).
# Word boundary based, case-insensitive.
_VIOLATION_SEGMENT_PATTERN = re.compile(
    r"[A-Za-z]+(?:[\s\-'][A-Za-z]+){" + str(_MIN_ENGLISH_WORDS_FOR_VIOLATION - 1) + r",}"
    r"(?:[\s\-',.!?;:\"()]|$)",
    re.MULTILINE,
)

# Max length of a violation segment to extract (truncate for log readability).
_MAX_SEGMENT_LEN: int = 200


def _is_cjk(char: str) -> bool:
    """True if `char` is a CJK ideograph (in any of the defined ranges)."""
    cp = ord(char)
    for lo, hi in _CJK_RANGES:
        if lo <= cp <= hi:
            return True
    return False


def _is_ascii_letter(char: str) -> bool:
    """True if `char` is an ASCII letter (a-z, A-Z)."""
    return ("a" <= char <= "z") or ("A" <= char <= "Z")


@dataclass
class ChineseFidelityResult:
    """Result of a ChineseFidelityChecker.check() call.

    Fields:
        expected_language: The language the prompt asked for ("zh-CN" / "en").
        is_correct: True iff fidelity check passes the threshold.
        chinese_ratio: CJK chars / (CJK + ASCII letters).
        english_ratio: ASCII letters / (CJK + ASCII letters).
        violation_segments: English-dominant runs (≥ 5 words) for diagnostics.
        score: Alias for chinese_ratio — used by EvalRunner as a 0..1 metric.
    """

    expected_language: str
    is_correct: bool
    chinese_ratio: float
    english_ratio: float
    violation_segments: list[str] = field(default_factory=list)
    score: float = 0.0


class ChineseFidelityChecker:
    """Detects whether LLM output matches the expected language fidelity.

    Specifically targets the regression where DeepSeek V4 Pro returned English
    `summary_md` / `feedback` despite a zh-CN prompt. See
    `interview_report_chinese_caveat` lesson.
    """

    def check(
        self,
        text: str,
        expected_language: Literal["zh-CN", "en"] = "zh-CN",
    ) -> ChineseFidelityResult:
        """Check whether `text` matches `expected_language` fidelity.

        For `expected_language="zh-CN"`:
        - If text looks like JSON, extract string values first (so JSON keys
          like "score" / "feedback" don't dilute the ratio)
        - Counts CJK chars and ASCII letters on the extracted text
        - Passes if chinese_ratio >= 0.3 (allows English tech terms mixed in)
        - Extracts English-dominant segments (≥ 5 consecutive words) as
          violation_segments for diagnostics

        For `expected_language="en"` (or any non-zh): always passes (this
        checker only guards zh-CN fidelity; English outputs are validated by
        other metrics).
        """
        if expected_language != "zh-CN":
            return ChineseFidelityResult(
                expected_language=expected_language,
                is_correct=True,
                chinese_ratio=0.0,
                english_ratio=1.0,
                violation_segments=[],
                score=1.0,
            )

        if not text:
            return ChineseFidelityResult(
                expected_language=expected_language,
                is_correct=False,
                chinese_ratio=0.0,
                english_ratio=0.0,
                violation_segments=[],
                score=0.0,
            )

        # JSON-aware extraction: if text is a JSON object, extract string
        # values so English JSON keys ("score", "feedback", "sub_scores")
        # don't dilute the Chinese ratio.
        check_text = self._extract_text_for_fidelity(text)

        chinese_count = 0
        english_count = 0
        for char in check_text:
            if _is_cjk(char):
                chinese_count += 1
            elif _is_ascii_letter(char):
                english_count += 1

        total_letters = chinese_count + english_count
        if total_letters == 0:
            # No linguistic content — e.g. digits-only or punctuation-only.
            return ChineseFidelityResult(
                expected_language=expected_language,
                is_correct=False,
                chinese_ratio=0.0,
                english_ratio=0.0,
                violation_segments=[],
                score=0.0,
            )

        chinese_ratio = chinese_count / total_letters
        english_ratio = english_count / total_letters

        violation_segments = self._extract_english_violations(check_text)

        is_correct = chinese_ratio >= _MIN_CHINESE_RATIO

        return ChineseFidelityResult(
            expected_language=expected_language,
            is_correct=is_correct,
            chinese_ratio=round(chinese_ratio, 4),
            english_ratio=round(english_ratio, 4),
            violation_segments=violation_segments,
            score=round(chinese_ratio, 4),
        )

    @staticmethod
    def _extract_text_for_fidelity(text: str) -> str:
        """If `text` parses as JSON, extract string values for fidelity check.

        Why: an LLM that returns `{"score": 9, "feedback": "候选人对 React
        diff 算法理解深入"}` would have a low Chinese ratio because JSON
        keys ("score", "feedback", sub_scores) inflate the English letter
        count. We care about the language of the *content values*, not the
        JSON schema. So we extract string values recursively before counting.

        If `text` is not valid JSON, return it unchanged (the common case for
        pure-text outputs like a summary paragraph).
        """
        stripped = text.strip()
        if not (stripped.startswith("{") and stripped.endswith("}")):
            return text
        try:
            data = json.loads(stripped)
        except (json.JSONDecodeError, ValueError):
            return text
        return _collect_string_values(data)

    @staticmethod
    def _extract_english_violations(text: str) -> list[str]:
        """Extract English-dominant spans (≥ 5 consecutive English words).

        Returns truncated segments (≤ 200 chars) for log readability.
        """
        segments: list[str] = []
        for match in _VIOLATION_SEGMENT_PATTERN.finditer(text):
            seg = match.group(0).strip().rstrip(".,!?;:\"'()")
            if len(seg) >= 3:  # filter out trivial matches
                segments.append(seg[:_MAX_SEGMENT_LEN])
        return segments


def _collect_string_values(obj: Any) -> str:
    """Recursively collect string values from a JSON-like structure.

    Used by `_extract_text_for_fidelity` to skip JSON keys + numbers and
    keep only string content (where language fidelity actually matters).
    """
    if isinstance(obj, str):
        return obj + " "
    if isinstance(obj, dict):
        return " ".join(
            _collect_string_values(v) for v in obj.values()
        )
    if isinstance(obj, list):
        return " ".join(_collect_string_values(v) for v in obj)
    return ""


__all__ = ["ChineseFidelityChecker", "ChineseFidelityResult"]
