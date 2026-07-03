"""019 (US4) — ErrorQuestion auto-sink unit tests.

Tests:
1. _derive_source_qid produces deterministic UUIDs
2. ERROR_THRESHOLD = 60 (REQ-040 US2 R4'' 修订 — was 6 in 019 US4, now 60
   to match the 0-100 score scale used by the LLM score prompt)
"""
from __future__ import annotations

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
        # REQ-040 US2 R4'' 修订：0-100 scale, was 6 (0-10 scale)
        assert ERROR_THRESHOLD == 60

    def test_derive_source_qid_returns_uuid(self) -> None:
        result = _derive_source_qid(str(uuid4()), 0)
        assert isinstance(result, UUID)
