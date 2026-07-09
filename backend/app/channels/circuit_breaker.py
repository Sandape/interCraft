"""Per-user circuit breaker for iLink long-poll fault isolation — REQ-052 T041.

States:
  CLOSED   → normal operation, failures counted
  OPEN     → circuit tripped, no requests allowed
  HALF_OPEN → probing, one success → CLOSED, one failure → OPEN

Config (per spec FR-005):
  max_failures = 10
  window_sec = 300      (5 min sliding window for failure count)
  cooldown_sec = 300    (5 min before half-open probe)
"""

from __future__ import annotations

import asyncio
import time
from enum import Enum
from typing import Awaitable, Callable, Optional


class BreakerState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Per-user circuit breaker with sliding-window failure counting."""

    def __init__(
        self,
        user_id: str = "",
        max_failures: int = 10,
        window_sec: float = 300.0,
        cooldown_sec: float = 300.0,
        on_state_change: Optional[Callable[[str, BreakerState], Awaitable[None] | None]] = None,
    ) -> None:
        self.user_id = user_id
        self.max_failures = max_failures
        self.window_sec = window_sec
        self.cooldown_sec = cooldown_sec
        # Optional callback fired on every state transition. Receives
        # (user_id, new_state). May be sync or async. Used by ilink_pool
        # to mirror breaker state into agents.status (active / degraded).
        self.on_state_change = on_state_change

        self.state: BreakerState = BreakerState.CLOSED
        self._failure_times: list[float] = []  # monotonic timestamps in window
        self._opened_at: float = 0.0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def allow_request(self) -> bool:
        """Return True if a poll request should be attempted."""
        if self.state == BreakerState.CLOSED:
            return True
        if self.state == BreakerState.OPEN:
            # Check if cooldown has passed → transition to HALF_OPEN
            if time.monotonic() - self._opened_at >= self.cooldown_sec:
                self.state = BreakerState.HALF_OPEN
                return True
            return False
        # HALF_OPEN: allow one probe
        return True

    def record_success(self) -> None:
        """Called after a successful getupdates() call."""
        prev = self.state
        if self.state == BreakerState.HALF_OPEN:
            self.state = BreakerState.CLOSED
        # Reset failure history on any success
        self._failure_times.clear()
        self._fire_state_change(prev)

    def record_failure(self) -> None:
        """Called after a failed getupdates() call."""
        prev = self.state
        now = time.monotonic()
        # Prune old failures outside the window
        cutoff = now - self.window_sec
        self._failure_times = [t for t in self._failure_times if t > cutoff]
        self._failure_times.append(now)

        if self.state == BreakerState.HALF_OPEN:
            # Single failure in half-open → back to OPEN
            self.state = BreakerState.OPEN
            self._opened_at = now
        elif self.state == BreakerState.CLOSED and len(self._failure_times) >= self.max_failures:
            self.state = BreakerState.OPEN
            self._opened_at = now
        self._fire_state_change(prev)

    def _fire_state_change(self, prev: BreakerState) -> None:
        """Fire on_state_change callback if the state actually transitioned.

        Supports both sync and async callbacks. Errors in the callback are
        logged but never raise — the breaker must keep working even if the
        callback (e.g. DB write) is failing.
        """
        if self.state == prev or self.on_state_change is None:
            return
        try:
            result = self.on_state_change(self.user_id, self.state)
            if asyncio.iscoroutine(result):
                # Schedule the coroutine on the running loop without
                # blocking the breaker call site. If no loop is running
                # we just create a task; if creation fails (e.g. no loop),
                # we silently drop the notification.
                try:
                    asyncio.get_event_loop().create_task(result)
                except RuntimeError:
                    pass
        except Exception:
            # Swallow — never let callback errors break the breaker.
            import logging
            logging.getLogger(__name__).exception(
                "circuit_breaker_state_change_callback_failed",
                extra={"user_id": self.user_id, "new_state": self.state.value},
            )

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @property
    def failure_count(self) -> int:
        self._prune()
        return len(self._failure_times)

    @property
    def is_open(self) -> bool:
        return self.state == BreakerState.OPEN

    def _prune(self) -> None:
        cutoff = time.monotonic() - self.window_sec
        self._failure_times = [t for t in self._failure_times if t > cutoff]

    def __repr__(self) -> str:
        return (
            f"CircuitBreaker(user={self.user_id}, state={self.state.value}, "
            f"failures={self.failure_count}/{self.max_failures})"
        )


__all__ = ["CircuitBreaker", "BreakerState"]
