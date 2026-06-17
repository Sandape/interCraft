"""020 (FIX-003, D-013) — clear-source must be idempotent.

Per the 019 Constitution principle IV, write paths must be idempotent.
The current implementation returns 200 on every call; the second call
should return 400 with the typed error code `source_already_cleared`
because there is nothing to clear.

Strong idempotency table (from contracts/error-questions-source.md §3.2):

| State before call                                | Response | DB after        |
|--------------------------------------------------|----------|-----------------|
| source_session_id OR source_question_id non-NULL | 200 OK   | both NULL       |
| Both source_session_id AND source_question_id NULL| 400      | unchanged       |
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

from app.modules.errors.service import ErrorService


def _eq(source_session_id=None, source_question_id=None) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        source_session_id=source_session_id,
        source_question_id=source_question_id,
    )


class TestClearSourceIdempotency:
    async def test_first_call_with_source_returns_200(self) -> None:
        """When source is set, clearing succeeds (returns the cleared row)."""
        sid, qid = uuid4(), uuid4()
        current = _eq(source_session_id=sid, source_question_id=qid)
        cleared = _eq(source_session_id=None, source_question_id=None)

        repo = AsyncMock()
        repo.get = AsyncMock(return_value=current)
        repo.clear_source = AsyncMock(return_value=cleared)

        svc = ErrorService(repo)
        result = await svc.clear_source(current.id, uuid4())
        assert result.source_session_id is None
        assert result.source_question_id is None

    async def test_second_call_already_cleared_returns_400(self) -> None:
        """When both source_* are already NULL, return 400 source_already_cleared."""
        current = _eq(source_session_id=None, source_question_id=None)

        repo = AsyncMock()
        repo.get = AsyncMock(return_value=current)
        repo.clear_source = AsyncMock(return_value=None)  # never reached

        svc = ErrorService(repo)
        with pytest.raises(HTTPException) as exc_info:
            await svc.clear_source(current.id, uuid4())

        assert exc_info.value.status_code == 400
        # The detail must carry the typed error code so clients can branch.
        detail = exc_info.value.detail
        assert isinstance(detail, dict)
        assert detail["error"]["code"] == "source_already_cleared"

    async def test_second_call_does_not_touch_repo(self) -> None:
        """The 400 path must short-circuit BEFORE the repo UPDATE runs."""
        current = _eq(source_session_id=None, source_question_id=None)

        repo = AsyncMock()
        repo.get = AsyncMock(return_value=current)
        repo.clear_source = AsyncMock(return_value=None)

        svc = ErrorService(repo)
        with pytest.raises(HTTPException):
            await svc.clear_source(current.id, uuid4())

        repo.clear_source.assert_not_called()

    async def test_missing_record_returns_404(self) -> None:
        """Non-existent id is still 404, not 400."""
        repo = AsyncMock()
        repo.get = AsyncMock(return_value=None)

        svc = ErrorService(repo)
        with pytest.raises(HTTPException) as exc_info:
            await svc.clear_source(uuid4(), uuid4())

        assert exc_info.value.status_code == 404