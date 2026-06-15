"""UUID v7 generator (RFC 9562 §5.7).

Phase 1 DEC-2: hand-rolled to avoid dependencies. The implementation
follows the spec literally: 48-bit unix_ts_ms | 4-bit version=7 |
12 random bits (incl. variant 10) | 62 random bits.

Provides a hook (`set_clock`) so tests can pin time and detect clock
regressions without flakiness.
"""
from __future__ import annotations

import os
import secrets
import threading
import time
from collections.abc import Callable
from uuid import UUID

_lock = threading.Lock()
_last_ms: int = -1
_clock: Callable[[], int] = time.time_ns


def set_clock(fn: Callable[[], int] | None) -> None:
    """Inject a clock returning nanoseconds. Used by tests."""
    global _clock
    _clock = fn or time.time_ns


def reset_state() -> None:
    """Reset monotonic counter. Call between tests that pin the clock."""
    global _last_ms
    with _lock:
        _last_ms = -1


def _now_ms() -> int:
    return _clock() // 1_000_000


def _ensure_monotonic(ts_ms: int) -> int:
    """If clock regresses, bump to last_ms + 1 to preserve monotonicity."""
    global _last_ms
    with _lock:
        if ts_ms <= _last_ms:
            ts_ms = _last_ms + 1
        _last_ms = ts_ms
        return ts_ms


def new_uuid_v7() -> UUID:
    """Generate a fresh UUID v7.

    Layout per RFC 9562 §5.7:
      bits 0..47  unix_ts_ms (big-endian)
      bits 48..51 version = 0b0111 (7)
      bits 52..63 rand_a (12 random bits)
      bits 64..65 variant = 0b10
      bits 66..127 rand_b (62 random bits)
    """
    ts_ms = _ensure_monotonic(_now_ms())
    rand = secrets.token_bytes(10)  # 80 random bits
    b = bytearray(16)
    b[0:6] = ts_ms.to_bytes(6, "big", signed=False)
    b[6] = 0x70 | (rand[0] & 0x0F)  # version 7
    b[7] = rand[1]
    b[8] = 0x80 | (rand[2] & 0x3F)  # variant 10xx
    b[9:16] = rand[3:10]
    return UUID(bytes=bytes(b))


def uuid7_to_ms(u: UUID) -> int:
    """Extract the embedded unix_ts_ms (debugging / tests)."""
    return int.from_bytes(u.bytes[0:6], "big", signed=False)


def uuid7_to_unix(u: UUID) -> float:
    """Extract the embedded unix timestamp as seconds (float)."""
    return uuid7_to_ms(u) / 1000.0


__all__ = ["new_uuid_v7", "set_clock", "uuid7_to_ms", "uuid7_to_unix"]


# Suppress unused-import warning for `os` (kept for future RNG override hook).
_ = os
