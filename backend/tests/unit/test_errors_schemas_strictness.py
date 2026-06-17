"""020 (FIX-001) — CreateErrorQuestionInput Pydantic strictness.

D-002: Pydantic v2 silently drops unknown fields by default. The 020
fix is to add `source_session_id` and `source_question_id` to the
write schema so that POST round-trips the values. This test locks
down the fix at two layers:

  1. Pydantic schema accepts the fields and round-trips them in
     `.model_dump()`.
  2. `ErrorService.create` actually passes those fields to the
     `ErrorQuestion` model instance via the repo (mocked).

If Pydantic drops the field at layer 1, layer 2 cannot recover it.
"""
from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from app.modules.errors.schemas import CreateErrorQuestionInput
from app.modules.errors.service import ErrorService


# ---- 1. Schema level ----

class TestCreateErrorQuestionInputSchema:
    """The Pydantic write schema must accept source_* fields."""

    def test_accepts_source_session_id(self) -> None:
        sid = uuid4()
        m = CreateErrorQuestionInput.model_validate({
            "question_text": "请描述 TCP 三次握手",
            "source_session_id": str(sid),
        })
        assert m.source_session_id == sid

    def test_accepts_source_question_id(self) -> None:
        qid = uuid4()
        m = CreateErrorQuestionInput.model_validate({
            "question_text": "请描述 TCP 三次握手",
            "source_question_id": str(qid),
        })
        assert m.source_question_id == qid

    def test_accepts_both_source_fields(self) -> None:
        sid, qid = uuid4(), uuid4()
        m = CreateErrorQuestionInput.model_validate({
            "question_text": "请描述 TCP 三次握手",
            "source_session_id": str(sid),
            "source_question_id": str(qid),
        })
        assert m.source_session_id == sid
        assert m.source_question_id == qid

    def test_source_fields_default_none(self) -> None:
        """Optional fields; default None when omitted."""
        m = CreateErrorQuestionInput.model_validate({
            "question_text": "请描述 TCP 三次握手",
        })
        assert m.source_session_id is None
        assert m.source_question_id is None

    def test_model_dump_round_trips_source_fields(self) -> None:
        sid, qid = uuid4(), uuid4()
        m = CreateErrorQuestionInput.model_validate({
            "question_text": "请描述 TCP 三次握手",
            "source_session_id": str(sid),
            "source_question_id": str(qid),
        })
        dumped = m.model_dump()
        assert dumped["source_session_id"] == sid
        assert dumped["source_question_id"] == qid

    def test_invalid_uuid_rejected(self) -> None:
        """Bad UUID strings should still raise ValidationError (no regression)."""
        with pytest.raises(Exception):
            CreateErrorQuestionInput.model_validate({
                "question_text": "请描述 TCP 三次握手",
                "source_session_id": "not-a-uuid",
            })


# ---- 2. Service level ----

class TestErrorServiceCreatePassesSourceFields:
    """`ErrorService.create` must hand source_* to the ErrorQuestion model."""

    async def test_create_passes_source_session_id_to_model(self) -> None:
        sid = uuid4()
        qid = uuid4()
        captured: dict = {}

        async def fake_create(instance):
            captured["instance"] = instance
            return instance

        repo = AsyncMock()
        repo.create = AsyncMock(side_effect=fake_create)

        svc = ErrorService(repo)
        body = CreateErrorQuestionInput.model_validate({
            "question_text": "请描述 TCP 三次握手",
            "source_session_id": str(sid),
            "source_question_id": str(qid),
        })
        await svc.create(uuid4(), body.model_dump())

        assert captured["instance"].source_session_id == sid
        assert captured["instance"].source_question_id == qid

    async def test_create_with_no_source_fields_succeeds(self) -> None:
        """Backward compat: existing POST calls without source_* still work."""
        captured: dict = {}

        async def fake_create(instance):
            captured["instance"] = instance
            return instance

        repo = AsyncMock()
        repo.create = AsyncMock(side_effect=fake_create)

        svc = ErrorService(repo)
        body = CreateErrorQuestionInput.model_validate({
            "question_text": "no source",
        })
        await svc.create(uuid4(), body.model_dump())

        assert captured["instance"].source_session_id is None
        assert captured["instance"].source_question_id is None