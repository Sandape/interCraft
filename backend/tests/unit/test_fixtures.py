"""Unit tests for fractional-indexing parity (Python ↔ JS fixtures).

Compares the output of `python-fractional-indexing` against a small
set of precomputed JavaScript outputs from `fractional-indexing` (npm)
captured in `tests/fixtures/fractional_cases.json`. Phase 1 has 20
hand-curated cases.
"""
import json
from pathlib import Path

import pytest
from fractional_indexing import generate_key_between, generate_n_keys_between

FIXTURE = Path(__file__).resolve().parents[0] / "fixtures" / "fractional_cases.json"


def _load_cases():
    if not FIXTURE.exists():
        return []
    with open(FIXTURE, encoding="utf-8") as f:
        return json.load(f)


CASES = _load_cases()


@pytest.mark.parametrize("case", CASES, ids=[c.get("name", "?") for c in CASES])
def test_fractional_parity(case):
    op = case["op"]
    a, b = case.get("a"), case.get("b")
    n = case.get("n", 1)
    if op == "between":
        out = (
            generate_key_between(a, b)
            if n == 1
            else list(generate_n_keys_between(a, b, n))
        )
        assert out == case["expected"]


def test_fractional_100_random_drags():
    """100 random drags produce stable, monotonically increasing order."""
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
    # All keys unique and string-sortable into the same order.
    assert len(set(keys)) == len(keys)
    assert keys == sorted(keys)
