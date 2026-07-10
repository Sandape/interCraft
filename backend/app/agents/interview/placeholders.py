"""Sanitize interview target strings for candidate-facing text (REQ-058).

See ``specs/058-interview-agent-optimize/data-model.md`` validation rules
and ``contracts/question-selection.md`` step 1.
"""
from __future__ import annotations

import re

# Explicit junk / placeholder denylist (case-insensitive).
_DENYLIST = frozenset(
    {
        "123123",
        "123456",
        "111111",
        "000000",
        "test",
        "testing",
        "xxx",
        "asdf",
        "qwerty",
        "n/a",
        "na",
        "none",
        "null",
        "undefined",
        "公司",
        "岗位",
        "未知",
        "未指定",
        "通用",
        "通用公司",
    }
)

_PURE_DIGITS = re.compile(r"^\d+$")
_WHITESPACE = re.compile(r"\s+")


def sanitize_interview_target(
    value: str | None,
    *,
    kind: str = "company",
) -> tuple[str | None, bool]:
    """Return ``(display_value, is_valid)`` for a company/position string.

    Invalid values (empty, pure digits, denylist) return ``(None, False)``
    so callers can omit them from stems instead of echoing junk.
    """
    if value is None:
        return None, False
    text = _WHITESPACE.sub(" ", str(value)).strip()
    if not text:
        return None, False
    lowered = text.casefold()
    if _PURE_DIGITS.match(text):
        return None, False
    if lowered in _DENYLIST:
        return None, False
    # Reject very short alphanumeric noise (e.g. "aa", "x1")
    if len(text) <= 1:
        return None, False
    if kind not in ("company", "position"):
        kind = "company"
    return text, True


def display_target_or_fallback(
    value: str | None,
    *,
    kind: str = "company",
    fallback: str = "",
) -> str:
    """Sanitize then fall back to a safe display string (never junk)."""
    cleaned, ok = sanitize_interview_target(value, kind=kind)
    if ok and cleaned:
        return cleaned
    return fallback


__all__ = [
    "display_target_or_fallback",
    "sanitize_interview_target",
]
