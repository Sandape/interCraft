"""Unit tests for jsonpatch parity (Python ↔ JS, byte-equal on shared fixtures)."""
import json
from pathlib import Path

import jsonpatch
import pytest

FIXTURE = Path(__file__).resolve().parents[0] / "fixtures" / "jsonpatch_cases.json"


def _load_cases():
    if not FIXTURE.exists():
        return []
    with open(FIXTURE, encoding="utf-8") as f:
        return json.load(f)


CASES = _load_cases()


@pytest.mark.parametrize("case", CASES, ids=[c.get("name", "?") for c in CASES])
def test_jsonpatch_parity(case):
    doc = case["doc"]
    patch_ops = case["patch"]
    expected = case["expected"]
    # Build a JSON Patch (RFC 6902) and apply via jsonpatch.
    p = jsonpatch.JsonPatch(patch_ops)
    result = p.apply(doc)
    assert result == expected


def test_make_patch_matches_node():
    a = {"branch": {"name": "a"}, "blocks": [{"id": "1", "title": "x"}]}
    b = {"branch": {"name": "b"}, "blocks": [{"id": "1", "title": "x"}, {"id": "2", "title": "y"}]}
    patch = jsonpatch.make_patch(a, b)
    restored = jsonpatch.apply_patch(a, patch, in_place=False)
    assert restored == b
