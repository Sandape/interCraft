"""[ac-completed: AC-008] — category taxonomy is locked.

Reject:
    - camelCase (SchemaInvalid, ParseFail, Timeout, Quota, OutOfBounds)
    - kebab-case (parse-fail, schema-invalid)
    - spaced (Schema Invalid, parse fail)

Allow exactly 5 strings:
    schema_invalid, parse_fail, quota, timeout, oob

We assert this at two levels:
    1. Imports of StructuredOutputError subclasses never leak camelCase strings
       as category values.
    2. Fixture alias list is empty.
"""
from __future__ import annotations

import json
from pathlib import Path

from app.agents.structured_output.errors import (
    CategoryType,
    OutOfBounds,
    ParseFail,
    Quota,
    SchemaInvalid,
    Timeout,
)


CANONICAL = {"schema_invalid", "parse_fail", "quota", "timeout", "oob"}


def test_category_literal_matches_canonical():
    """Each subclass category must be in the canonical 5-string set."""
    actual = {
        SchemaInvalid.category,
        ParseFail.category,
        Timeout.category,
        Quota.category,
        OutOfBounds.category,
    }
    assert actual == CANONICAL, f"categories drift: {actual - CANONICAL} | {CANONICAL - actual}"


def test_categorytype_is_literal():
    """CategoryType must be the Literal alias (typing_Literal in runtime)."""
    import typing

    assert typing.get_args(CategoryType) == (
        "schema_invalid",
        "parse_fail",
        "quota",
        "timeout",
        "oob",
    )


def test_fixture_alias_strings_empty():
    """test_case_strings.json must have alias_strings == []."""
    p = Path(__file__).parent / "fixtures" / "structured_output" / "test_case_strings.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data.get("alias_strings") == []
    assert sorted(data.get("valid_categories", [])) == sorted(CANONICAL)