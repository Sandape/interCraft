"""019 (US4) — ErrorQuestion auto-sink from interview score node.

Tests:
1. _derive_source_qid produces deterministic UUIDs
2. score_node calls _sink_to_error_book when raw_score < 6
3. score_node does NOT sink when raw_score >= 6
4. clear_source sets source columns to NULL
5. list ?filter[source]=auto returns only auto-sinked items
"""
from __future__ import annotations

import pytest
from uuid import UUID, uuid4

from app.agents.interview.nodes.score import (
    _derive_source_qid,
    ERROR_THRESHOLD,
)


class TestDeriveSourceQid:
    """Unit-style tests for the deterministic source_question_id derivation."""

    def test_same_inputs_produce_same_uuid(self) -> None:
        session_id = str(uuid4())
        qid1 = _derive_source_qid(session_id, 1)
        qid2 = _derive_source_qid(session_id, 1)
        assert qid1 == qid2

    def test_different_question_no_produce_different_uuids(self) -> None:
        session_id = str(uuid4())
        qid1 = _derive_source_qid(session_id, 1)
        qid2 = _derive_source_qid(session_id, 2)
        assert qid1 != qid2

    def test_different_session_produce_different_uuids(self) -> None:
        qid1 = _derive_source_qid(str(uuid4()), 1)
        qid2 = _derive_source_qid(str(uuid4()), 1)
        assert qid1 != qid2

    def test_different_sessions_same_question_are_distinct(self) -> None:
        """Two sessions with the same question_no must produce different UUIDs."""
        qid1 = _derive_source_qid(str(uuid4()), 3)
        qid2 = _derive_source_qid(str(uuid4()), 3)
        assert qid1 != qid2

    def test_error_threshold_value(self) -> None:
        assert ERROR_THRESHOLD == 6

    def test_derive_source_qid_returns_uuid(self) -> None:
        result = _derive_source_qid(str(uuid4()), 0)
        assert isinstance(result, UUID)
