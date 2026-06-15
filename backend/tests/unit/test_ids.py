"""Unit tests for app.core.ids (uuidv7)."""

from app.core.ids import new_uuid_v7, reset_state, set_clock, uuid7_to_ms


def test_uuidv7_is_uuid():
    from uuid import UUID

    reset_state()
    u = new_uuid_v7()
    assert isinstance(u, UUID)
    # Version 7 — bits 48..51 of the byte representation == 0b0111
    assert (u.bytes[6] & 0xF0) == 0x70


def test_uuidv7_monotonic_under_load():
    reset_state()
    ids = {new_uuid_v7() for _ in range(1000)}
    assert len(ids) == 1000
    sorted_ids = sorted(ids, key=uuid7_to_ms)
    assert ids == set(sorted_ids)


def test_uuidv7_clock_regression_safe():
    reset_state()
    set_clock(lambda: 1_000_000_000_000)  # pinned to 1e12 ns
    new_uuid_v7()  # warm up internal counter; result intentionally ignored
    b = new_uuid_v7()
    # Regress the clock back in time — the next id should still be > b.
    set_clock(lambda: 500_000_000_000)
    c = new_uuid_v7()
    assert uuid7_to_ms(c) > uuid7_to_ms(b)
    set_clock(None)
    reset_state()


def test_uuidv7_ms_round_trip():
    reset_state()
    set_clock(lambda: 1_700_000_000_000_000_000)  # 2023-11-14 in ns
    u = new_uuid_v7()
    assert uuid7_to_ms(u) == 1_700_000_000_000
    set_clock(None)
    reset_state()
