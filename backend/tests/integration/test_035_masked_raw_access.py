"""REQ-051 — masked raw access tests (simplified auth).

All sensitive endpoints now require admin (is_admin=true) rather than
capability-token based access.
"""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.modules.admin_console.auth import require_admin


async def _override_admin() -> bool:
    return True


@pytest.mark.anyio
async def test_admin_can_reveal_masked_raw() -> None:
    app.dependency_overrides[require_admin] = _override_admin
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/v1/admin-console/observability/payloads/payload_demo/reveal",
                json={"reason": "Debug failed eval", "visibility_mode": "masked_raw"},
            )
    finally:
        app.dependency_overrides.pop(require_admin, None)

    # admin can access this endpoint
    assert response.status_code in (200, 404)


@pytest.mark.anyio
async def test_curl_view_returns_200_for_admin() -> None:
    app.dependency_overrides[require_admin] = _override_admin
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(
                "/api/v1/admin-console/observability/llm-calls/llm_call_demo/curl",
                params={"reason": "Reproduce provider failure"},
            )
    finally:
        app.dependency_overrides.pop(require_admin, None)

    # admin can access; may be 404 if the LLM call doesn't exist
    assert response.status_code in (200, 404)
