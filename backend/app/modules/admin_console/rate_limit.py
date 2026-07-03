"""REQ-039 B1 — admin_console rate limiter.

In-process sliding-window rate limiter for the two write endpoints:

- Replay: ≤ 5 calls / minute / user (FR-032)
- Diff: ≤ 20 calls / minute / user (FR-033)

The 6th Replay (or 21st Diff) within the window raises
:class:`RateLimitedError` which the API layer maps to HTTP 429 with
``retry_after_seconds``.

Storage: process-local ``dict[key, deque[float]]``. Not Redis-backed —
the admin console traffic is low and per-process enforcement is
sufficient for MVP. When the user count grows, swap in a Redis-backed
implementation behind the same public API.
"""
from __future__ import annotations

import threading
import time
from collections import deque
from typing import Deque


class RateLimitedError(Exception):
    """Raised when a user exceeds the configured per-minute window."""

    def __init__(self, *, retry_after_seconds: int, action: str) -> None:
        super().__init__(
            f"{action} rate limit exceeded; retry after {retry_after_seconds}s"
        )
        self.retry_after_seconds = retry_after_seconds
        self.action = action


class SlidingWindowLimiter:
    """Sliding window (60s) counter per (action, user_id) tuple.

    Thread-safe via a single ``threading.Lock``. Async-safe in the
    FastAPI worker (no event loop contention since the lock is short).
    """

    WINDOW_SECONDS = 60

    def __init__(self) -> None:
        self._buckets: dict[tuple[str, str], Deque[float]] = {}
        self._lock = threading.Lock()

    def check_and_record(
        self, *, action: str, user_id: str, limit_per_window: int
    ) -> None:
        """Record a hit; raise :class:`RateLimitedError` if over the limit.

        The hit is recorded only on success — failed (over-limit) checks
        do NOT consume a slot, so a misbehaving client cannot be locked
        out by its own 429s.
        """
        if limit_per_window <= 0:
            return  # limiter disabled
        now = time.monotonic()
        cutoff = now - self.WINDOW_SECONDS
        key = (action, user_id)
        with self._lock:
            bucket = self._buckets.setdefault(key, deque())
            # Evict entries older than the window.
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= limit_per_window:
                # retry_after = window_seconds - (now - oldest_hit)
                oldest = bucket[0]
                retry_after = max(1, int(self.WINDOW_SECONDS - (now - oldest)) + 1)
                # Clamp to WINDOW_SECONDS so the value stays inside the
                # documented 1..60 range (otherwise, when the caller
                # hits exactly at the window boundary, we can return 61).
                retry_after = min(retry_after, self.WINDOW_SECONDS)
                raise RateLimitedError(
                    retry_after_seconds=retry_after, action=action
                )
            bucket.append(now)

    def reset(self, *, action: str | None = None, user_id: str | None = None) -> None:
        """Clear buckets (test helper)."""
        with self._lock:
            if action is None and user_id is None:
                self._buckets.clear()
                return
            keys_to_drop = [
                k
                for k in self._buckets
                if (action is None or k[0] == action)
                and (user_id is None or k[1] == user_id)
            ]
            for k in keys_to_drop:
                del self._buckets[k]

    def current_count(self, *, action: str, user_id: str) -> int:
        """Return the number of hits in the current window (test helper)."""
        now = time.monotonic()
        cutoff = now - self.WINDOW_SECONDS
        key = (action, user_id)
        with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None:
                return 0
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            return len(bucket)


# Module-level singleton — both endpoints share the same in-process state.
_limiter = SlidingWindowLimiter()


def replay_limiter(user_id: str) -> None:
    """Apply the Replay rate limit (≤5/min, FR-032)."""
    _limiter.check_and_record(
        action="replay", user_id=user_id, limit_per_window=5
    )


def diff_limiter(user_id: str) -> None:
    """Apply the Diff rate limit (≤20/min, FR-033)."""
    _limiter.check_and_record(
        action="diff", user_id=user_id, limit_per_window=20
    )


def reset_for_tests() -> None:
    """Clear all limiter state. Used by unit tests."""
    _limiter.reset()


__all__ = [
    "RateLimitedError",
    "SlidingWindowLimiter",
    "diff_limiter",
    "replay_limiter",
    "reset_for_tests",
]