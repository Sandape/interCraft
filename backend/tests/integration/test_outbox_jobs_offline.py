"""024 US2 — Outbox replay for job write operations (integration).

Reproduces the bug where the outbox replay path returned `ok` for job
create / advance-status / delete without actually persisting anything.
After the fix, replaying an outbox entry must call JobService so the
DB reflects the change.
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

import pytest

pytestmark = pytest.mark.integration


def _entry(
    *,
    entity_id: str,
    operation: str,
    payload: dict,
    entity_updated_at: datetime | None = None,
    client_entry_id: int = 1,
) -> dict:
    return {
        "client_entry_id": client_entry_id,
        "entity_type": "job",
        "operation": operation,
        "entity_id": entity_id,
        "payload": payload,
        "entity_updated_at": entity_updated_at.isoformat() if entity_updated_at else None,
        "client_timestamp": 0,
    }


@pytest.mark.asyncio
async def test_replay_create_job_persists_to_db(user_a_headers, client):
    """Replay of a job `create` entry actually inserts a row in the jobs table."""
    from app.modules.outbox.schemas import ReplayInput
    from app.modules.outbox.service import OutboxService

    # Resolve the user_id from the registered auth headers' token
    user_id = await _resolve_user_id(client, user_a_headers)

    temp_id = str(uuid4())
    payload = {
        "company": "OutboxCorp",
        "position": "Backend Engineer",
        "notes_md": "queued offline",
    }
    entry = _entry(entity_id=temp_id, operation="create", payload=payload)

    svc = OutboxService()
    result = await svc.replay_batch(
        ReplayInput(entries=[_replay_entry(entry)]), user_id=str(user_id)
    )

    assert result.summary.ok == 1, f"expected ok=1, got {result.summary}"
    assert result.results[0].status == "ok"
    server_id = result.results[0].server_entity.get("id")
    assert server_id, "server_entity.id must be returned for created job"
    assert server_id != temp_id, (
        "create must allocate a real server-side id; returning the client temp id "
        "indicates the entry was not actually persisted"
    )

    # Verify the job is now visible through the canonical GET /jobs API
    r = await client.get("/api/v1/jobs", headers=user_a_headers)
    assert r.status_code == 200
    ids = [j["id"] for j in r.json()["data"]]
    assert server_id in ids, "job created via outbox must appear in GET /jobs"


@pytest.mark.asyncio
async def test_replay_advance_status_updates_history(user_a_headers, client):
    """Replay of a status-advance entry calls JobService.update_status, which
    appends to status_history and updates `status`."""
    from app.modules.outbox.schemas import ReplayInput
    from app.modules.outbox.service import OutboxService

    user_id = await _resolve_user_id(client, user_a_headers)

    # Seed: create a job through the canonical API
    create_r = await client.post(
        "/api/v1/jobs",
        json={"company": "StatusCorp", "position": "Engineer"},
        headers=user_a_headers,
    )
    assert create_r.status_code == 201
    job_id = create_r.json()["id"]

    # Snapshot pre-replay state
    pre = await client.get(f"/api/v1/jobs/{job_id}", headers=user_a_headers)
    assert pre.status_code == 200
    pre_history_len = len(pre.json()["status_history"])

    # Enqueue an offline status-advance: applied → test
    entry = _entry(
        entity_id=job_id,
        operation="update",
        payload={"to": "test", "note": "phone screen scheduled"},
        entity_updated_at=datetime.fromisoformat(pre.json()["updated_at"].replace("Z", "+00:00")),
    )

    svc = OutboxService()
    result = await svc.replay_batch(
        ReplayInput(entries=[_replay_entry(entry)]), user_id=str(user_id)
    )
    assert result.summary.ok == 1, result.results

    # Verify the status actually advanced on the server
    post = await client.get(f"/api/v1/jobs/{job_id}", headers=user_a_headers)
    assert post.status_code == 200
    assert post.json()["status"] == "test"
    assert len(post.json()["status_history"]) == pre_history_len + 1
    last = post.json()["status_history"][-1]
    assert last["from"] == "applied"
    assert last["to"] == "test"
    assert last["note"] == "phone screen scheduled"


@pytest.mark.asyncio
async def test_replay_delete_job_soft_deletes(user_a_headers, client):
    """Replay of a delete entry soft-deletes the job (deleted_at set, row
    disappears from GET /jobs)."""
    from app.modules.outbox.schemas import ReplayInput
    from app.modules.outbox.service import OutboxService

    user_id = await _resolve_user_id(client, user_a_headers)

    create_r = await client.post(
        "/api/v1/jobs",
        json={"company": "DeleteCorp", "position": "Engineer"},
        headers=user_a_headers,
    )
    assert create_r.status_code == 201
    job_id = create_r.json()["id"]

    entry = _entry(
        entity_id=job_id,
        operation="delete",
        payload={},
    )

    svc = OutboxService()
    result = await svc.replay_batch(
        ReplayInput(entries=[_replay_entry(entry)]), user_id=str(user_id)
    )
    assert result.summary.ok == 1, result.results

    # Job must no longer be visible via the list endpoint
    r = await client.get("/api/v1/jobs", headers=user_a_headers)
    assert r.status_code == 200
    ids = [j["id"] for j in r.json()["data"]]
    assert job_id not in ids, "soft-deleted job must not appear in GET /jobs"


@pytest.mark.asyncio
async def test_replay_update_basic_info_patches_fields(user_a_headers, client):
    """Replay of an update with non-status payload calls JobService.patch."""
    from app.modules.outbox.schemas import ReplayInput
    from app.modules.outbox.service import OutboxService

    user_id = await _resolve_user_id(client, user_a_headers)

    create_r = await client.post(
        "/api/v1/jobs",
        json={"company": "PatchCorp", "position": "Engineer"},
        headers=user_a_headers,
    )
    assert create_r.status_code == 201
    job_id = create_r.json()["id"]

    pre = await client.get(f"/api/v1/jobs/{job_id}", headers=user_a_headers)
    entry = _entry(
        entity_id=job_id,
        operation="update",
        payload={"company": "PatchedCorp", "notes_md": "updated via outbox"},
        entity_updated_at=datetime.fromisoformat(pre.json()["updated_at"].replace("Z", "+00:00")),
    )

    svc = OutboxService()
    result = await svc.replay_batch(
        ReplayInput(entries=[_replay_entry(entry)]), user_id=str(user_id)
    )
    assert result.summary.ok == 1, result.results

    post = await client.get(f"/api/v1/jobs/{job_id}", headers=user_a_headers)
    assert post.status_code == 200
    assert post.json()["company"] == "PatchedCorp"
    assert post.json()["notes_md"] == "updated via outbox"


@pytest.mark.asyncio
async def test_replay_invalid_status_transition_returns_failed(user_a_headers, client):
    """Status advance that violates JOB_TRANSITIONS returns status=failed (not ok).

    `rejected` is a terminal state with no outgoing transitions, so
    `rejected → applied` must fail at the service layer.
    """
    from app.modules.outbox.schemas import ReplayInput
    from app.modules.outbox.service import OutboxService

    user_id = await _resolve_user_id(client, user_a_headers)

    create_r = await client.post(
        "/api/v1/jobs",
        json={"company": "InvalidCorp", "position": "Engineer"},
        headers=user_a_headers,
    )
    assert create_r.status_code == 201
    job_id = create_r.json()["id"]

    # Move the job into the terminal `rejected` state via the canonical API.
    advance_r = await client.patch(
        f"/api/v1/jobs/{job_id}/status",
        json={"to": "rejected"},
        headers=user_a_headers,
    )
    assert advance_r.status_code == 200

    pre = await client.get(f"/api/v1/jobs/{job_id}", headers=user_a_headers)
    entry = _entry(
        entity_id=job_id,
        operation="update",
        payload={"to": "applied", "note": "trying to revive"},
        entity_updated_at=datetime.fromisoformat(pre.json()["updated_at"].replace("Z", "+00:00")),
    )

    svc = OutboxService()
    result = await svc.replay_batch(
        ReplayInput(entries=[_replay_entry(entry)]), user_id=str(user_id)
    )
    assert result.summary.failed == 1, result.results
    assert result.results[0].status == "failed"


async def _resolve_user_id(client, headers) -> UUID:
    """Decode the user_id from the test auth headers by calling /users/me."""
    r = await client.get("/api/v1/users/me", headers=headers)
    assert r.status_code == 200, f"failed to resolve user_id: {r.status_code} {r.text}"
    return UUID(r.json()["id"])


def _replay_entry(entry_dict: dict):
    from app.modules.outbox.schemas import ReplayEntry

    return ReplayEntry(
        client_entry_id=entry_dict["client_entry_id"],
        entity_type=entry_dict["entity_type"],
        operation=entry_dict["operation"],
        entity_id=entry_dict["entity_id"],
        payload=entry_dict["payload"],
        entity_updated_at=entry_dict["entity_updated_at"],
        client_timestamp=entry_dict["client_timestamp"],
    )
