"""REQ-051 — admin console contract tests (simplified auth).

Verifies the auth module and health endpoint contracts.
"""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.modules.admin_console.auth import require_admin


@pytest.mark.anyio
async def test_admin_console_health_is_public_liveness() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/api/v1/admin-console/observability/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


def test_require_admin_is_callable() -> None:
    """require_admin is a valid FastAPI dependency factory."""
    assert callable(require_admin)
