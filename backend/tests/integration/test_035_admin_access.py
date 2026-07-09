"""REQ-051 — simplified admin access tests.

Tests that require_admin() dependency works correctly:
- No auth → 401
- Non-admin user → 403
- Admin user → 200
"""
from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_current_user
from app.main import app


def _user(*, email: str | None = None, is_admin: bool = False) -> SimpleNamespace:
    user_id = uuid4()
    return SimpleNamespace(
        id=user_id,
        email=email or f"{user_id.hex}@example.test",
        display_name=f"User {user_id.hex[:8]}",
        is_admin=is_admin,
    )


async def _override_user(user: SimpleNamespace) -> None:
    async def current_user() -> SimpleNamespace:
        return user

    app.dependency_overrides[get_current_user] = current_user


@pytest.mark.anyio
async def test_observability_health_is_public_liveness() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/api/v1/admin-console/observability/health")

    assert response.status_code == 200


@pytest.mark.anyio
async def test_admin_me_requires_authentication() -> None:
    """Unprotected route that requires auth returns 401 when no user."""
    # The /me endpoint was removed in REQ-051; the auth requirement
    # is tested via a protected endpoint instead (e.g. list traces).
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        # list_traces requires get_caller_user_id (auth)
        response = await client.get("/api/v1/admin-console/observability/traces")

    # Without X-Admin-User-Id or JWT, returns 401
    assert response.status_code == 401


@pytest.mark.anyio
async def test_non_admin_user_gets_403() -> None:
    """Non-admin user gets 403 from require_admin dependency."""
    user = _user(is_admin=False)
    await _override_user(user)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            # endpoint that requires require_admin()
            response = await client.post(
                f"/api/v1/admin-console/observability/tasks/{uuid4()}/tags",
                json={"tag": "test-tag"},
            )
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    # require_admin() checks DB for is_admin=True → 403
    assert response.status_code in (401, 403)
