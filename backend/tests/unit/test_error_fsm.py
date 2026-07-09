"""024 US4 — Unit tests: error question FSM (archived removed).

Tests:
  1. Valid transitions: fresh→practicing→mastered
  2. Invalid transitions: fresh→archived → 409
  3. Invalid transitions: practicing→fresh → 409 (no reset flag)
  4. masterd→fresh → 409 via PATCH (must use POST /reset)
  5. reduce_status frequency validation
"""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.modules.errors.service import reduce_status


class TestValidTransitions:
    def test_fresh_to_practicing(self):
        status, freq = reduce_status("fresh", "practicing", 3, None)
        assert status == "practicing"
        assert 1 <= freq <= 2

    def test_practicing_to_mastered(self):
        status, freq = reduce_status("practicing", "mastered", 1, None)
        assert status == "mastered"
        assert freq == 0


class TestInvalidTransitions:
    def test_fresh_to_archived_raises(self):
        with pytest.raises(HTTPException) as exc:
            reduce_status("fresh", "archived", 3, None)
        assert exc.value.status_code == 409

    def test_practicing_to_archived_raises(self):
        with pytest.raises(HTTPException) as exc:
            reduce_status("practicing", "archived", 2, None)
        assert exc.value.status_code == 409

    def test_practicing_to_fresh_raises(self):
        """practicing→fresh is not allowed (must go through mastered first)."""
        with pytest.raises(HTTPException) as exc:
            reduce_status("practicing", "fresh", 1, None)
        assert exc.value.status_code == 409

    def test_mastered_to_fresh_raises(self):
        """mastered→fresh via PATCH raises — must use POST /reset endpoint."""
        with pytest.raises(HTTPException) as exc:
            reduce_status("mastered", "fresh", 0, None)
        assert exc.value.status_code == 409

    def test_mastered_to_archived_raises(self):
        with pytest.raises(HTTPException) as exc:
            reduce_status("mastered", "archived", 0, None)
        assert exc.value.status_code == 409


class TestFrequencyValidation:
    def test_practicing_freq_must_be_1_or_2(self):
        status, freq = reduce_status("fresh", "practicing", 3, 1)
        assert status == "practicing"
        assert freq == 1

    def test_practicing_freq_3_raises(self):
        with pytest.raises(HTTPException) as exc:
            reduce_status("fresh", "practicing", 3, 3)
        assert exc.value.status_code == 422
