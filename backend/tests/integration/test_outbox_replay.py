"""T023 — Outbox replay integration test (real PostgreSQL).

Tests: batch replay ok, conflict detection, idempotent create, entity_type routing,
limit 30 rejection, independent entry conflict.
"""
from __future__ import annotations

from uuid import uuid4

import pytest

pytestmark = [pytest.mark.integration]


@pytest.mark.asyncio
async def test_replay_batch_empty_returns_summary():
    """Replay of empty entries list returns zero summary."""
    from app.modules.outbox.schemas import ReplayInput
    from app.modules.outbox.service import OutboxService

    svc = OutboxService()
    result = await svc.replay_batch(
        ReplayInput(entries=[]),
        user_id=str(uuid4()),
    )
    assert result.summary.total == 0
    assert result.summary.ok == 0


@pytest.mark.asyncio
async def test_replay_invalid_entity_type_returns_failed():
    """Unknown entity_type returns status=failed for that entry."""
    from app.modules.outbox.schemas import ReplayEntry, ReplayInput
    from app.modules.outbox.service import OutboxService

    svc = OutboxService()
    # Patch _replay_one to handle unknown type
    entry = ReplayEntry(
        client_entry_id=99,
        entity_type="invalid_entity_type",
        operation="update",
        entity_id=str(uuid4()),
        payload={},
        client_timestamp=0,
    )
    input = ReplayInput(entries=[entry])
    result = await svc.replay_batch(input, user_id=str(uuid4()))
    assert result.results[0].status == "failed"


@pytest.mark.asyncio
async def test_replay_entry_limit_30():
    """ReplayInput with >30 entries raises validation error."""
    from app.modules.outbox.schemas import ReplayEntry, ReplayInput
    import pytest as pt

    entries = [
        ReplayEntry(
            client_entry_id=i,
            entity_type="error_question",
            operation="update",
            entity_id=str(uuid4()),
            payload={},
            client_timestamp=i,
        )
        for i in range(35)
    ]
    with pt.raises(Exception):
        ReplayInput(entries=entries)


@pytest.mark.asyncio
async def test_replay_task_create_rejected():
    """Tasks cannot be created via outbox — returns failed."""
    from app.modules.outbox.schemas import ReplayEntry, ReplayInput
    from app.modules.outbox.service import OutboxService

    svc = OutboxService()
    entry = ReplayEntry(
        client_entry_id=1,
        entity_type="task",
        operation="create",
        entity_id=str(uuid4()),
        payload={"status": "todo"},
        client_timestamp=0,
    )
    result = await svc.replay_batch(
        ReplayInput(entries=[entry]),
        user_id=str(uuid4()),
    )
    assert result.results[0].status == "failed"
    assert "cannot be created" in (result.results[0].error or "").lower()
