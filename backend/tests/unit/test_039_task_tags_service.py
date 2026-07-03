"""REQ-039 US4 — task_tags service-layer validation tests (FR-018 / E5).

Pure unit tests over :func:`service.validate_tag_text` — no DB
required. Covers:

- Length bounds (1-50 chars; E5).
- Charset regex (letters / digits / _ / - / CJK / space).
- Hard-delete semantics (re-add creates new row) is covered in the
  integration test (test_039_tags_e2e.py).
"""
from __future__ import annotations

import pytest

from app.modules.admin_console.service import validate_tag_text


class TestValidateTagText:
    @pytest.mark.parametrize(
        "tag",
        [
            "needs-fix",
            "needs_fix",
            "needsFix",
            "needs fix",
            "needs123",
            "needs-修复",
            "ABC123",
            "x",
            "a" * 50,
        ],
    )
    def test_valid_tags(self, tag: str) -> None:
        canonical = validate_tag_text(tag)
        assert canonical == tag.strip()

    @pytest.mark.parametrize(
        "tag",
        [
            "",  # empty
            " " * 51,  # too long
            "a" * 51,  # too long
            "needs!fix",  # invalid charset
            "needs@fix",  # invalid charset
            "needs/fix",  # invalid charset
            "needs.fix",  # invalid charset
            "needs+fix",  # invalid charset
            "<script>",  # invalid charset
            "needs\tfix",  # invalid whitespace (\t not allowed)
        ],
    )
    def test_invalid_tags_raise(self, tag: str) -> None:
        with pytest.raises(ValueError):
            validate_tag_text(tag)

    def test_strips_surrounding_whitespace(self) -> None:
        assert validate_tag_text("  needs-fix  ") == "needs-fix"

    def test_unicode_preserved(self) -> None:
        assert validate_tag_text("修复-必填") == "修复-必填"