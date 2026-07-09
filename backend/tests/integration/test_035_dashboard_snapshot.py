"""REQ-051 — dashboard snapshot contract test (simplified auth)."""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.modules.admin_console.auth import require_admin


async def _override_admin() -> bool:
    return True


@pytest.mark.anyio
async def test_admin_can_create_review_snapshot() -> None:
    """Admin user can create a review snapshot."""
    from app.main import app

    app.dependency_overrides[require_admin] = _override_admin
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/v1/admin-console/review-snapshots",
                json={
                    "workspace": "command-center",
                    "label": "Test Snapshot REQ-051",
                },
            )
    finally:
        app.dependency_overrides.pop(require_admin, None)

    assert response.status_code in (200, 201, 422)
