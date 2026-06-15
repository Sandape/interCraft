"""Unit tests for resume block ordering helpers (no DB)."""
from fractional_indexing import generate_key_between


def test_order_index_helper_returns_string():
    last = generate_key_between(None, None)
    nxt = generate_key_between(last, None)
    assert isinstance(nxt, str)
    assert nxt > last
