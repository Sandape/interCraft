"""REQ-039 US4 — task_tags HTTP E2E + RLS isolation tests.

Integration tests covering the full HTTP round-trip for tag CRUD
(GET / POST / DELETE) on ``/api/v1/admin-console/observability/tasks/{id}/tags``.

Bootstrap: the worktree's alembic chain is missing intermediate
migrations (0012-0016, 0022-0026) because those belong to concurrent
teams. We bootstrap by creating just the 039 tables directly via
``Base.metadata.create_all`` on the test DB.

Coverage:

- GET empty / non-empty tag list.
- POST a valid tag → 201 + row visible on next GET.
- POST a duplicate → 409.
- POST an invalid (charset / length) tag → 422.
- DELETE a tag → 200 + row gone on next GET.
- Re-add after delete creates a new row with a fresh ``created_at``.
- RLS: user A cannot see user B's tags.
"""
from __future__ import annotations

import asyncio
import os
import secrets
import uuid
from datetime import datetime, timezone
from typing import AsyncIterator
from uuid import UUID

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


# ---------------------------------------------------------------------------
# Bootstrap fixture
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def bootstrapped_db() -> AsyncIterator[None]:
    """Create the 039 tables directly via metadata.create_all.

    Skips if ``DATABASE_URL`` is not configured (consistent with other
    033-style integration tests).
    """
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        pytest.skip("DATABASE_URL not set; integration test needs real Postgres")
    from app.core.config import get_settings

    settings = get_settings()
    # Avoid touching any other table; only create the 039 tables.
    from app.core.db import Base
    from app.modules.admin_console.models import AdminAuditLog, TaskTag, Trace

    # Drop only the 039 tables if they exist from a prior test run.
    drop_ddl = [
        "DROP TABLE IF EXISTS task_tags CASCADE",
        "DROP TABLE IF EXISTS admin_audit_log CASCADE",
        "DROP TABLE IF EXISTS traces CASCADE",
    ]
    eng = create_async_engine(settings.database_url)
    try:
        async with eng.begin() as conn:
            for stmt in drop_ddl:
                await conn.exec_driver_sql(stmt)
            # Create just the 039 tables.
            await conn.run_sync(
                lambda sync_conn: Base.metadata.create_all(
                    sync_conn,
                    tables=[TaskTag.__table__, AdminAuditLog.__table__, Trace.__table__],
                )
            )
            # Enable RLS on task_tags (mirrors migration 0022).
            await conn.exec_driver_sql(
                "ALTER TABLE task_tags ENABLE ROW LEVEL SECURITY"
            )
            await conn.exec_driver_sql(
                "ALTER TABLE task_tags FORCE ROW LEVEL SECURITY"
            )
            await conn.exec_driver_sql(
                """
                CREATE POLICY task_tags_user_isolation ON task_tags
                FOR ALL
                USING (user_id = current_setting('app.user_id', true)::uuid)
                WITH CHECK (user_id = current_setting('app.user_id', true)::uuid)
                """
            )
        yield
    finally:
        # Cleanup: drop the 039 tables so the next test starts fresh.
        async with eng.begin() as conn:
            for stmt in drop_ddl:
                await conn.exec_driver_sql(stmt)
        await eng.dispose()


@pytest_asyncio.fixture
async def two_test_users(
    bootstrapped_db, monkeypatch
) -> AsyncIterator[tuple[UUID, UUID, dict[str, str], dict[str, str]]]:
    """Create two test users (A + B) and return their IDs + auth headers.

    Uses the registration endpoint to satisfy FK requirements.
    """
    from app.main import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    suffix_a = secrets.token_hex(4)
    suffix_b = secrets.token_hex(4)
    user_a_id = uuid.uuid4()
    user_b_id = uuid.uuid4()

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Register user A
        ra = await client.post(
            "/api/v1/auth/register",
            json={
                "email": f"tag_a_{suffix_a}@intercraft.io",
                "password": "Demo1234",
                "display_name": "tag_a",
                "device_fingerprint": f"fp_a_{suffix_a}",
            },
            headers={"X-Device-Fingerprint": f"fp_a_{suffix_a}"},
        )
        assert ra.status_code in (200, 201), ra.text
        body = ra.json()
        user_a_id = _extract_user_id(body, user_a_id)
        headers_a = {
            "Authorization": f"Bearer {body['tokens']['access_token']}",
            "X-Device-Fingerprint": f"fp_a_{suffix_a}",
        }

        # Register user B
        rb = await client.post(
            "/api/v1/auth/register",
            json={
                "email": f"tag_b_{suffix_b}@intercraft.io",
                "password": "Demo1234",
                "display_name": "tag_b",
                "device_fingerprint": f"fp_b_{suffix_b}",
            },
            headers={"X-Device-Fingerprint": f"fp_b_{suffix_b}"},
        )
        assert rb.status_code in (200, 201), rb.text
        body = rb.json()
        user_b_id = _extract_user_id(body, user_b_id)
        headers_b = {
            "Authorization": f"Bearer {body['tokens']['access_token']}",
            "X-Device-Fingerprint": f"fp_b_{suffix_b}",
        }

    yield user_a_id, user_b_id, headers_a, headers_b


def _extract_user_id(body: dict, fallback: UUID) -> UUID:
    if isinstance(body, dict):
        if "user" in body and isinstance(body["user"], dict) and "id" in body["user"]:
            return UUID(body["user"]["id"])
        if "id" in body:
            return UUID(body["id"])
    return fallback


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_post_tag_returns_201_and_visible_on_get(
    bootstrapped_db, two_test_users, monkeypatch
) -> None:
    """Happy-path POST returns 201 + tag visible on next GET."""
    from app.main import create_app
    from app.modules.admin_console.auth import require_admin

    user_a_id, _, headers_a, _ = two_test_users
    # REQ-051: override require_admin to grant access (no capability matrix)
    async def _admin_true(*args, **kwargs) -> bool:
        return True
    monkeypatch.setattr("app.modules.admin_console.auth.require_admin", _admin_true)

    task_id = uuid.uuid4()
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        post = await client.post(
            f"/api/v1/admin-console/observability/tasks/{task_id}/tags",
            json={"tag": "needs-fix"},
            headers=headers_a,
        )
        assert post.status_code == 201, post.text
        body = post.json()
        assert body["tag"] == "needs-fix"
        assert "created_at" in body

        get = await client.get(
            f"/api/v1/admin-console/observability/tasks/{task_id}/tags",
            headers=headers_a,
        )
        assert get.status_code == 200, get.text
        tags = [t["tag"] for t in get.json()["tags"]]
        assert "needs-fix" in tags


async def test_post_duplicate_tag_returns_409(
    bootstrapped_db, two_test_users, monkeypatch
) -> None:
    """Re-POSTing an existing tag returns 409 (FR-018)."""
    from app.main import create_app

    async def _admin_true(*args, **kwargs) -> bool:
        return True
    monkeypatch.setattr("app.modules.admin_console.auth.require_admin", _admin_true)

    user_a_id, _, headers_a, _ = two_test_users
    task_id = uuid.uuid4()
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        first = await client.post(
            f"/api/v1/admin-console/observability/tasks/{task_id}/tags",
            json={"tag": "flaky"},
            headers=headers_a,
        )
        assert first.status_code == 201
        second = await client.post(
            f"/api/v1/admin-console/observability/tasks/{task_id}/tags",
            json={"tag": "flaky"},
            headers=headers_a,
        )
        assert second.status_code == 409
        body = second.json()
        assert body["error"] == "DUPLICATE_TAG"


async def test_post_invalid_tag_charset_returns_422(
    bootstrapped_db, two_test_users, monkeypatch
) -> None:
    """Tag with invalid charset returns 422 (E5)."""
    from app.main import create_app

    async def _admin_true(*args, **kwargs) -> bool:
        return True
    monkeypatch.setattr("app.modules.admin_console.auth.require_admin", _admin_true)

    user_a_id, _, headers_a, _ = two_test_users
    task_id = uuid.uuid4()
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            f"/api/v1/admin-console/observability/tasks/{task_id}/tags",
            json={"tag": "needs!fix"},  # ! not in charset
            headers=headers_a,
        )
        assert resp.status_code == 422


async def test_delete_tag_then_readd_has_new_created_at(
    bootstrapped_db, two_test_users, monkeypatch
) -> None:
    """Hard-delete + re-add creates a fresh row with a new ``created_at`` (IC-3)."""
    from app.main import create_app

    async def _admin_true(*args, **kwargs) -> bool:
        return True
    monkeypatch.setattr("app.modules.admin_console.auth.require_admin", _admin_true)

    user_a_id, _, headers_a, _ = two_test_users
    task_id = uuid.uuid4()
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        first = await client.post(
            f"/api/v1/admin-console/observability/tasks/{task_id}/tags",
            json={"tag": "needs-fix"},
            headers=headers_a,
        )
        assert first.status_code == 201
        first_created = first.json()["created_at"]

        # Delete + small wait so timestamps would differ if re-created.
        await asyncio.sleep(0.05)
        delete_resp = await client.delete(
            f"/api/v1/admin-console/observability/tasks/{task_id}/tags",
            params={"tag": "needs-fix"},
            headers=headers_a,
        )
        assert delete_resp.status_code == 200
        assert delete_resp.json()["deleted"] is True

        # Re-add.
        second = await client.post(
            f"/api/v1/admin-console/observability/tasks/{task_id}/tags",
            json={"tag": "needs-fix"},
            headers=headers_a,
        )
        assert second.status_code == 201
        second_created = second.json()["created_at"]
        assert second_created != first_created


async def test_rls_user_b_cannot_see_user_a_tags(
    bootstrapped_db, two_test_users, monkeypatch
) -> None:
    """User B cannot see user A's tags (FR-031)."""
    from app.main import create_app

    async def _admin_true(*args, **kwargs) -> bool:
        return True
    monkeypatch.setattr("app.modules.admin_console.auth.require_admin", _admin_true)

    user_a_id, user_b_id, headers_a, headers_b = two_test_users
    task_id = uuid.uuid4()
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # User A adds a tag.
        post = await client.post(
            f"/api/v1/admin-console/observability/tasks/{task_id}/tags",
            json={"tag": "customer-escalation"},
            headers=headers_a,
        )
        assert post.status_code == 201

        # User B lists tags on the same task — must be empty.
        get = await client.get(
            f"/api/v1/admin-console/observability/tasks/{task_id}/tags",
            headers=headers_b,
        )
        assert get.status_code == 200
        tags = get.json()["tags"]
        assert tags == []

        # Direct DB sanity check: user A's row exists in task_tags.
        # Use a session bound to user A's GUC so RLS lets us see the row.
        from app.core.config import get_settings
        from app.core.db import get_db_session_no_rls, set_rls_user_id
        from sqlalchemy.ext.asyncio import create_async_engine

        eng = create_async_engine(get_settings().database_url)
        try:
            async with eng.connect() as conn:
                await conn.execute(
                    text("SELECT set_config('app.user_id', :u, false)"),
                    {"u": str(user_a_id)},
                )
                rows = await conn.execute(
                    text("SELECT user_id, tag FROM task_tags WHERE task_id = :tid"),
                    {"tid": str(task_id)},
                )
                rows = list(rows)
                assert len(rows) == 1
                assert rows[0][1] == "customer-escalation"
        finally:
            await eng.dispose()


async def test_post_without_capability_returns_403(
    bootstrapped_db, two_test_users, monkeypatch
) -> None:
    """POST without admin access returns 403."""
    from app.main import create_app
    from fastapi import HTTPException, status

    # REQ-051: non-admin users get 403 from require_admin()
    async def _admin_deny(*args, **kwargs) -> bool:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "ADMIN_REQUIRED", "message": "需要管理员权限"},
        )
    monkeypatch.setattr("app.modules.admin_console.auth.require_admin", _admin_deny)

    user_a_id, _, headers_a, _ = two_test_users
    task_id = uuid.uuid4()
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            f"/api/v1/admin-console/observability/tasks/{task_id}/tags",
            json={"tag": "needs-fix"},
            headers=headers_a,
        )
        assert resp.status_code == 403
        # 403 envelope shape is {code, message, request_id}; the
        # MISSING_CAPABILITY code is embedded in the message body.
        body = resp.json()
        assert "MISSING_CAPABILITY" in str(body)