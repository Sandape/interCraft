"""Integration test — JSON Patch parity fixture. Cross-end byte-equal."""
import json
from pathlib import Path

import jsonpatch
import pytest

pytestmark = pytest.mark.integration

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "jsonpatch_cases.json"


def _load_cases():
    with open(FIXTURE, encoding="utf-8") as f:
        return json.load(f)


@pytest.mark.parametrize("case", _load_cases(), ids=[c.get("name", "?") for c in _load_cases()])
def test_patch_apply_matches(case):
    p = jsonpatch.JsonPatch(case["patch"])
    assert p.apply(case["doc"]) == case["expected"]
