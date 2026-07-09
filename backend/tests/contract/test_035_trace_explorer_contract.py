"""REQ-051 — trace explorer contract tests (simplified auth)."""
from __future__ import annotations

import pytest

from app.modules.admin_console.auth import require_admin


def test_require_admin_is_importable() -> None:
    """Auth module exports require_admin."""
    assert require_admin is not None
    assert callable(require_admin)


@pytest.mark.anyio
async def test_traces_list_endpoint_exists() -> None:
    """The /observability/traces endpoint is registered."""
    from httpx import ASGITransport, AsyncClient
    from app.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.get("/api/v1/admin-console/observability/traces")
    # Requires auth; just verifying endpoint exists (not 404)
    assert resp.status_code != 404
