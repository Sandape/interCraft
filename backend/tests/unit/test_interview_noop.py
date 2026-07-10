"""Unit tests for interview noop_state_delta helper."""
from __future__ import annotations

from app.agents.interview.noop import noop_state_delta


def test_noop_prefers_thread_id() -> None:
    assert noop_state_delta({"thread_id": "t1", "user_id": "u1"}) == {"thread_id": "t1"}


def test_noop_falls_back_to_user_id() -> None:
    assert noop_state_delta({"user_id": "u1"}) == {"user_id": "u1"}


def test_noop_falls_back_to_current_question() -> None:
    assert noop_state_delta({}) == {"current_question": 0}
    assert noop_state_delta({"current_question": 3}) == {"current_question": 3}
