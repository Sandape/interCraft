"""REQ-051 — eval center contract tests (simplified auth)."""
from __future__ import annotations

import pytest

from app.modules.admin_console.auth import require_admin


def test_require_admin_dependency_imports() -> None:
    """Auth module exports require_admin as a callable dependency."""
    assert callable(require_admin)
    assert require_admin.__name__ == "require_admin"


@pytest.mark.anyio
async def test_admin_api_health_endpoint_accessible() -> None:
    """The health endpoint is publicly accessible."""
    from httpx import ASGITransport, AsyncClient
    from app.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.get("/api/v1/admin-console/observability/health")
    assert resp.status_code == 200
