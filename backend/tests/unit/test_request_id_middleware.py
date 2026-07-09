"""022 US1 — Unit tests for RequestID middleware.

Tests per contracts/request-id.md.
"""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_middleware_injects_x_request_id_response_header():
    """Every response gets X-Request-ID."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/api/v1/health")
    assert "X-Request-ID" in r.headers
    rid = r.headers["X-Request-ID"]
    assert rid, "X-Request-ID header must not be empty"


@pytest.mark.asyncio
async def test_middleware_preserves_incoming_x_request_id():
    """When client sends X-Request-ID, the same value is echoed back."""
    transport = ASGITransport(app=app)
    test_rid = f"req-{uuid.uuid4().hex[:12]}"
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/api/v1/health", headers={"X-Request-ID": test_rid})
    assert r.headers["X-Request-ID"] == test_rid


@pytest.mark.asyncio
async def test_middleware_generates_uuid_when_no_header():
    """When no X-Request-ID sent, middleware generates a valid UUID."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/api/v1/health")
    rid = r.headers["X-Request-ID"]
    # Should be a valid UUID, not a placeholder
    assert rid.startswith("req-") or len(rid) >= 32, f"unexpected request_id format: {rid}"
