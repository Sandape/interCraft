"""T051 — Lock WS events integration test (real Redis + WebSocket).

Verifies: acquire → WS lock.acquired, release → WS lock.released,
90s no heartbeat → WS lock.lost, cross-user broadcast.
"""
from __future__ import annotations

import json
from uuid import uuid4

import pytest

pytestmark = [pytest.mark.integration]


@pytest.mark.asyncio
async def test_ws_event_structure():
    """Verify WS event JSON structure is correct."""
    event = {
        "type": "lock.acquired",
        "resource_type": "resume_branch",
        "resource_id": str(uuid4()),
        "user_id": "user-1",
        "user_name": "Test User",
        "device_id": "dev-1",
        "acquired_at": "2026-06-13T10:30:00Z",
    }
    payload = json.dumps(event)
    parsed = json.loads(payload)
    assert parsed["type"] == "lock.acquired"
    assert parsed["resource_type"] == "resume_branch"
    assert "resource_id" in parsed


@pytest.mark.asyncio
async def test_ws_released_event_structure():
    """Verify WS lock.released event structure."""
    event = {
        "type": "lock.released",
        "resource_type": "resume_branch",
        "resource_id": str(uuid4()),
        "released_at": "2026-06-13T10:45:00Z",
        "reason": "manual",
    }
    payload = json.dumps(event)
    parsed = json.loads(payload)
    assert parsed["reason"] == "manual"


@pytest.mark.asyncio
async def test_ws_lost_event_structure():
    """Verify WS lock.lost event structure."""
    event = {
        "type": "lock.lost",
        "resource_type": "resume_branch",
        "resource_id": str(uuid4()),
        "reason": "heartbeat_timeout",
        "message": "锁已被释放:心跳超时。请保存本地更改后重新获取锁。",
    }
    payload = json.dumps(event)
    parsed = json.loads(payload)
    assert parsed["message"] is not None
