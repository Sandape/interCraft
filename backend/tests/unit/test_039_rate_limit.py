"""REQ-039 US2 / US3 — rate limit unit tests (FR-032 / FR-033).

Coverage:

- Replay: 6th call within 60s raises RateLimitedError with retry_after_seconds.
- Diff: 21st call within 60s raises RateLimitedError with retry_after_seconds.
- Different users do not share buckets.
- reset_for_tests clears all state.
"""
from __future__ import annotations

import time

import pytest

from app.modules.admin_console import rate_limit
from app.modules.admin_console.rate_limit import (
    RateLimitedError,
    SlidingWindowLimiter,
    diff_limiter,
    replay_limiter,
    reset_for_tests,
)


@pytest.fixture(autouse=True)
def _clear_limiter():
    reset_for_tests()
    yield
    reset_for_tests()


class TestReplayLimiter:
    def test_5_calls_pass(self) -> None:
        for _ in range(5):
            replay_limiter("user-a")
        assert rate_limit._limiter.current_count(action="replay", user_id="user-a") == 5

    def test_6th_call_raises(self) -> None:
        for _ in range(5):
            replay_limiter("user-a")
        with pytest.raises(RateLimitedError) as exc:
            replay_limiter("user-a")
        assert exc.value.retry_after_seconds >= 1
        assert exc.value.retry_after_seconds <= 60
        assert exc.value.action == "replay"

    def test_different_users_independent(self) -> None:
        for _ in range(5):
            replay_limiter("user-a")
        # user-b should still have full quota.
        for _ in range(5):
            replay_limiter("user-b")
        with pytest.raises(RateLimitedError):
            replay_limiter("user-a")
        with pytest.raises(RateLimitedError):
            replay_limiter("user-b")


class TestDiffLimiter:
    def test_20_calls_pass(self) -> None:
        for _ in range(20):
            diff_limiter("user-a")
        assert rate_limit._limiter.current_count(action="diff", user_id="user-a") == 20

    def test_21st_call_raises(self) -> None:
        for _ in range(20):
            diff_limiter("user-a")
        with pytest.raises(RateLimitedError) as exc:
            diff_limiter("user-a")
        assert exc.value.action == "diff"
        assert 1 <= exc.value.retry_after_seconds <= 60


class TestSlidingWindowSemantics:
    """Direct tests against the limiter class (no rate-limit factory wrappers)."""

    def test_window_eviction(self) -> None:
        lim = SlidingWindowLimiter()
        # Force 1 hit then advance the wall clock past the window.
        lim.check_and_record(action="replay", user_id="u", limit_per_window=2)
        # Simulate clock advance by clearing bucket + sleeping briefly.
        # The internal clock is monotonic — to test eviction we cheat
        # by reaching into the bucket and aging one entry.
        with lim._lock:
            bucket = lim._buckets[("replay", "u")]
            bucket[0] = time.monotonic() - 70  # 70s in the past
        # Should now allow a fresh slot.
        lim.check_and_record(action="replay", user_id="u", limit_per_window=2)
        assert lim.current_count(action="replay", user_id="u") == 1

    def test_reset(self) -> None:
        lim = SlidingWindowLimiter()
        lim.check_and_record(action="diff", user_id="u", limit_per_window=10)
        lim.reset()
        assert lim.current_count(action="diff", user_id="u") == 0

    def test_limit_zero_disables(self) -> None:
        lim = SlidingWindowLimiter()
        for _ in range(100):
            lim.check_and_record(action="diff", user_id="u", limit_per_window=0)
        assert lim.current_count(action="diff", user_id="u") == 0

    def test_failed_check_does_not_consume_slot(self) -> None:
        """A 429 over-limit check MUST NOT add a slot — otherwise a
        misbehaving client could lock itself out."""
        lim = SlidingWindowLimiter()
        for _ in range(3):
            lim.check_and_record(action="diff", user_id="u", limit_per_window=3)
        # Three over-limit attempts should not change the bucket size.
        for _ in range(3):
            with pytest.raises(RateLimitedError):
                lim.check_and_record(action="diff", user_id="u", limit_per_window=3)
        assert lim.current_count(action="diff", user_id="u") == 3