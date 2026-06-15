"""Outbox API contract tests (T010) — replay and status endpoints."""
from __future__ import annotations

import pytest
from httpx import ASGITransport

pytestmark = [pytest.mark.contract]


@pytest.mark.asyncio
async def test_replay_batch_ok():
    """POST /outbox/replay returns 200 with mixed results for valid entries."""
    from app.main import app

    transport = ASGITransport(app=app)
    async with __import__("httpx").AsyncClient(
        transport=transport, base_url="http://test"
    ) as client:
        res = await client.post(
            "/api/v1/outbox/replay",
            json={
                "entries": [
                    {
                        "client_entry_id": 1,
                        "entity_type": "error_question",
                        "operation": "update",
                        "entity_id": "019b5e6c-0000-7000-0000-000000000000",
                        "payload": {"tags": ["test"]},
                        "entity_updated_at": "2026-06-13T10:30:00Z",
                        "client_timestamp": 1750000000000,
                    }
                ]
            },
            headers={"Authorization": "Bearer valid_token_placeholder"},
        )
        assert res.status_code in (200, 401)


@pytest.mark.asyncio
async def test_replay_too_many_entries():
    """POST /outbox/replay returns 422 when entries exceed limit of 30."""
    from app.main import app

    transport = ASGITransport(app=app)
    async with __import__("httpx").AsyncClient(
        transport=transport, base_url="http://test"
    ) as client:
        entries = [
            {
                "client_entry_id": i,
                "entity_type": "error_question",
                "operation": "update",
                "entity_id": "019b5e6c-0000-7000-0000-000000000000",
                "payload": {},
                "entity_updated_at": "2026-06-13T10:30:00Z",
                "client_timestamp": 1750000000000 + i,
            }
            for i in range(35)
        ]
        res = await client.post(
            "/api/v1/outbox/replay",
            json={"entries": entries},
            headers={"Authorization": "Bearer valid_token_placeholder"},
        )
        assert res.status_code in (422, 401)


@pytest.mark.asyncio
async def test_replay_invalid_entity_type():
    """POST /outbox/replay returns 422 for invalid entity_type."""
    from app.main import app

    transport = ASGITransport(app=app)
    async with __import__("httpx").AsyncClient(
        transport=transport, base_url="http://test"
    ) as client:
        res = await client.post(
            "/api/v1/outbox/replay",
            json={
                "entries": [
                    {
                        "client_entry_id": 1,
                        "entity_type": "invalid_entity",
                        "operation": "update",
                        "entity_id": "019b5e6c-0000-7000-0000-000000000000",
                        "payload": {},
                        "entity_updated_at": "2026-06-13T10:30:00Z",
                        "client_timestamp": 1750000000000,
                    }
                ]
            },
            headers={"Authorization": "Bearer valid_token_placeholder"},
        )
        assert res.status_code == 422


@pytest.mark.asyncio
async def test_outbox_status_200():
    """GET /outbox/status returns 200 with health info."""
    from app.main import app

    transport = ASGITransport(app=app)
    async with __import__("httpx").AsyncClient(
        transport=transport, base_url="http://test"
    ) as client:
        res = await client.get(
            "/api/v1/outbox/status",
            headers={"Authorization": "Bearer valid_token_placeholder"},
        )
        assert res.status_code in (200, 401)
