"""Unit tests for sanitize_interview_target (REQ-058 T004/T005)."""
from __future__ import annotations

import pytest

from app.agents.interview.placeholders import (
    display_target_or_fallback,
    sanitize_interview_target,
)


@pytest.mark.parametrize(
    "value",
    ["123123", "123456", "000000", "111111", "999"],
)
def test_pure_digit_targets_invalid(value: str) -> None:
    cleaned, ok = sanitize_interview_target(value, kind="company")
    assert ok is False
    assert cleaned is None


@pytest.mark.parametrize("value", [None, "", "   ", "\t"])
def test_empty_targets_invalid(value: str | None) -> None:
    cleaned, ok = sanitize_interview_target(value, kind="position")
    assert ok is False
    assert cleaned is None


@pytest.mark.parametrize(
    "value",
    ["test", "TEST", "xxx", "n/a", "通用公司", "未指定"],
)
def test_denylist_targets_invalid(value: str) -> None:
    cleaned, ok = sanitize_interview_target(value)
    assert ok is False
    assert cleaned is None


@pytest.mark.parametrize(
    "value,kind",
    [
        ("字节跳动", "company"),
        ("后端工程师", "position"),
        ("InterCraft", "company"),
        ("Java 开发", "position"),
    ],
)
def test_valid_jd_names_pass(value: str, kind: str) -> None:
    cleaned, ok = sanitize_interview_target(value, kind=kind)
    assert ok is True
    assert cleaned == value


def test_display_fallback_never_echoes_junk() -> None:
    assert display_target_or_fallback("123123", kind="company", fallback="目标公司") == "目标公司"
    assert display_target_or_fallback("美团", kind="company", fallback="目标公司") == "美团"
