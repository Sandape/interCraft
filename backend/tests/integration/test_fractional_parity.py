"""Integration test — fractional-indexing parity (Python ↔ JS)."""
import json
from pathlib import Path

import pytest
from fractional_indexing import generate_key_between, generate_n_keys_between

pytestmark = pytest.mark.integration

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "fractional_cases.json"


def _load_cases():
    with open(FIXTURE, encoding="utf-8") as f:
        return json.load(f)


@pytest.mark.parametrize("case", _load_cases(), ids=[c.get("name", "?") for c in _load_cases()])
def test_algorithmic_parity(case):
    if case.get("n", 1) == 1:
        out = generate_key_between(case.get("a"), case.get("b"))
    else:
        out = list(generate_n_keys_between(case.get("a"), case.get("b"), case["n"]))
    assert out == case["expected"]


def test_100_random_drags_match_python_sort():
    import random

    keys: list[str] = []
    for _ in range(100):
        if not keys:
            keys.append(generate_key_between(None, None))
        else:
            i = random.randint(0, len(keys) - 1)
            prev = keys[i - 1] if i > 0 else None
            nxt = keys[i] if i < len(keys) else None
            new_key = generate_key_between(prev, nxt)
            keys.insert(i, new_key)
    assert keys == sorted(keys)
