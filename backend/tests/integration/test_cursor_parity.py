"""Cross-end cursor parity test — DEC-P2-1.

Verifies that backend cursor encode/decode produces the same format
that the frontend cursor.ts expects.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import UUID, uuid4

from app.domain.pagination import decode_activity_cursor, encode_activity_cursor


def test_round_trip() -> None:
    ts = datetime(2026, 6, 13, 12, 0, 0, tzinfo=timezone.utc)
    id = uuid4()
    opaque = encode_activity_cursor(ts, id)
    decoded_ts, decoded_id = decode_activity_cursor(opaque)

    assert decoded_ts == ts
    assert decoded_id == id


def test_opaque_is_base64url_safe() -> None:
    opaque = encode_activity_cursor(
        datetime(2026, 6, 13, 12, 0, 0, tzinfo=timezone.utc),
        UUID("ffffffff-ffff-7fff-8000-000000000000"),
    )
    assert "+" not in opaque
    assert "/" not in opaque
    assert "=" not in opaque


def test_multiple_cursors_unique() -> None:
    ts = datetime(2026, 6, 13, 12, 0, 0, tzinfo=timezone.utc)
    seen: set[str] = set()
    for _ in range(100):
        opaque = encode_activity_cursor(ts, uuid4())
        assert opaque not in seen
        seen.add(opaque)
        decoded_ts, _ = decode_activity_cursor(opaque)
        assert decoded_ts == ts


def test_frontend_parity_shape() -> None:
    """Verify the encoded payload has the {ts, id} shape frontend expects."""
    ts = datetime(2026, 6, 13, 12, 0, 0, tzinfo=timezone.utc)
    id = UUID("018f8a3c-0000-7000-8000-000000000001")
    opaque = encode_activity_cursor(ts, id)

    # Decode manually to verify shape
    from app.domain.pagination import decode_cursor

    payload = decode_cursor(opaque)
    assert isinstance(payload, dict)
    assert set(payload.keys()) == {"ts", "id"}
    assert payload["ts"] == "2026-06-13T12:00:00+00:00"
    assert payload["id"] == str(id)
