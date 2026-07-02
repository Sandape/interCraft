"""[ac-completed: AC-006b] — error category classification.

Each subclass of StructuredOutputError must pin its `category` field
so callers can rely on `exc.value.category` without string sniffing.
"""
from __future__ import annotations

import pytest

from app.agents.structured_output.errors import (
    OutOfBounds,
    ParseFail,
    Quota,
    SchemaInvalid,
    StructuredOutputError,
    Timeout,
)


def test_schema_invalid_category():
    with pytest.raises(StructuredOutputError) as exc:
        raise SchemaInvalid("bad schema")
    assert exc.value.category == "schema_invalid"


def test_parse_fail_category():
    with pytest.raises(StructuredOutputError) as exc:
        raise ParseFail("not json")
    assert exc.value.category == "parse_fail"


def test_timeout_category():
    with pytest.raises(StructuredOutputError) as exc:
        raise Timeout("slow")
    assert exc.value.category == "timeout"


def test_quota_category():
    with pytest.raises(StructuredOutputError) as exc:
        raise Quota(used=500_000, quota=500_000, estimated=1)
    assert exc.value.category == "quota"


def test_out_of_bounds_category():
    with pytest.raises(StructuredOutputError) as exc:
        raise OutOfBounds("score=200 > le=100")
    assert exc.value.category == "oob"


def test_all_subclasses_inherit_category_field():
    """Each subclass should expose category as a class attribute."""
    expected = {
        SchemaInvalid: "schema_invalid",
        ParseFail: "parse_fail",
        Timeout: "timeout",
        Quota: "quota",
        OutOfBounds: "oob",
    }
    for cls, cat in expected.items():
        assert cls.category == cat, f"{cls.__name__}.category != {cat}"