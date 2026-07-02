"""REQ-039 US2 — replay HTTP E2E tests (FR-006/007/008/010/032).

Integration tests for ``POST /api/v1/admin-console/observability/traces/{id}/replay``.

Coverage:

- Happy path: replay creates new trace with ``replay_of`` pointer and
  identical prompt_version + model + input_payload.
- Missing trace → 404.
- Retired model → 410.
- 6th replay within 60s → 429 with ``retry_after_seconds``.
- Audit log row written with canonical fields.
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
from sqlalchemy.ext.asyncio import create_async_engine

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest_asyncio.fixture
async def bootstrapped_db() -> AsyncIterator[None]:
    """Create the 039 tables directly via metadata.create_all."""
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        pytest.skip("DATABASE_URL not set; integration test needs real Postgres")
    from app.core.config import get_settings
    settings = get_settings()
    from app.core.db import Base
    from app.modules.admin_console.models import AdminAuditLog, TaskTag, Trace

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
            await conn.run_sync(
                lambda sync_conn: Base.metadata.create_all(
                    sync_conn,
                    tables=[
                        TaskTag.__table__,
                        AdminAuditLog.__table__,
                        Trace.__table__,
                    ],
                )
            )
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
        async with eng.begin() as conn:
            for stmt in drop_ddl:
                await conn.exec_driver_sql(stmt)
        await eng.dispose()


@pytest_asyncio.fixture
async def seeded_trace(bootstrapped_db) -> AsyncIterator[tuple[UUID, dict]]:
    """Seed a single trace row and return its id + the row data."""
    from app.core.config import get_settings

    trace_id = uuid.uuid4()
    user_id = uuid.uuid4()
    task_id = uuid.uuid4()
    eng = create_async_engine(get_settings().database_url)
    try:
        async with eng.begin() as conn:
            # Avoid asyncpg's `:bind::cast` parse error by binding the
            # JSON payload via a typed JSONB bind.
            from sqlalchemy.dialects.postgresql import JSONB
            from sqlalchemy import bindparam

            stmt = text(
                """
                INSERT INTO traces (
                    id, task_id, user_id, task_type, prompt_version, model,
                    input_payload, status, replay_of, node_payloads
                ) VALUES (
                    :id, :tid, :uid, 'interview', 'v1.0', 'deepseek-v4-pro',
                    :payload, 'failed', NULL, '{}'::jsonb
                )
                """
            ).bindparams(bindparam("payload", type_=JSONB))
            await conn.execute(
                stmt,
                {
                    "id": str(trace_id),
                    "tid": str(task_id),
                    "uid": str(user_id),
                    "payload": {"messages": [{"role": "user", "content": "hi"}]},
                },
            )
        yield trace_id, {
            "task_id": task_id,
            "user_id": user_id,
            "task_type": "interview",
            "prompt_version": "v1.0",
            "model": "deepseek-v4-pro",
        }
    finally:
        await eng.dispose()


@pytest_asyncio.fixture
async def admin_user(monkeypatch) -> AsyncIterator[UUID]:
    """Provision an admin user (admin role + REPLAY_TRIGGER capability)."""
    from app.modules.admin_console import auth, rate_limit, service

    user_id = uuid.uuid4()
    auth.grant_role(user_id, "admin")
    rate_limit.reset_for_tests()
    service.reset_retired_models()
    yield user_id
    auth.revoke_role(user_id)
    rate_limit.reset_for_tests()
    service.reset_retired_models()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_replay_creates_new_trace_with_replay_of(
    bootstrapped_db, seeded_trace, admin_user
) -> None:
    """Replay creates new trace with replay_of pointer + identical fields."""
    from app.main import create_app

    trace_id, trace_data = seeded_trace
    headers = {"X-Admin-User-Id": str(admin_user)}
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            f"/api/v1/admin-console/observability/traces/{trace_id}/replay",
            headers=headers,
            json={"note": "verifying fix for #1234"},
        )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["replay_of"] == str(trace_id)
    assert body["prompt_version"] == trace_data["prompt_version"]
    assert body["model"] == trace_data["model"]
    assert body["status"] == "pending"
    new_trace_id = body["new_trace_id"]
    assert new_trace_id != str(trace_id)

    # Verify the new trace exists in DB with replay_of set.
    from app.core.config import get_settings

    eng = create_async_engine(get_settings().database_url)
    try:
        async with eng.connect() as conn:
            rows = await conn.execute(
                text(
                    "SELECT replay_of, prompt_version, model FROM traces WHERE id = :id"
                ),
                {"id": new_trace_id},
            )
            row = rows.first()
            assert row is not None
            assert str(row[0]) == str(trace_id)
            assert row[1] == trace_data["prompt_version"]
            assert row[2] == trace_data["model"]
    finally:
        await eng.dispose()


async def test_replay_missing_trace_returns_404(
    bootstrapped_db, admin_user
) -> None:
    """Replay on non-existent trace returns 404."""
    from app.main import create_app

    headers = {"X-Admin-User-Id": str(admin_user)}
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            f"/api/v1/admin-console/observability/traces/{uuid.uuid4()}/replay",
            headers=headers,
        )
    assert resp.status_code == 404
    assert resp.json()["error"] == "TRACE_NOT_FOUND"


async def test_replay_retired_model_returns_410(
    bootstrapped_db, seeded_trace, admin_user
) -> None:
    """Replay against a retired model returns 410."""
    from app.main import create_app
    from app.modules.admin_console import service

    service.set_retired_models({"deepseek-v4-pro"})
    headers = {"X-Admin-User-Id": str(admin_user)}
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            f"/api/v1/admin-console/observability/traces/{seeded_trace[0]}/replay",
            headers=headers,
        )
    assert resp.status_code == 410
    assert resp.json()["error"] == "MODEL_RETIRED"


async def test_replay_6th_call_in_window_returns_429(
    bootstrapped_db, seeded_trace, admin_user
) -> None:
    """6th replay within 60s returns 429 with retry_after_seconds."""
    from app.main import create_app
    from app.modules.admin_console import rate_limit

    rate_limit.reset_for_tests()
    trace_id, _ = seeded_trace
    headers = {"X-Admin-User-Id": str(admin_user)}
    transport = ASGITransport(app=create_app())

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 5 successful replays on the same trace (idempotent — same model,
        # same input_payload — replay_of just points to the original).
        for i in range(5):
            resp = await client.post(
                f"/api/v1/admin-console/observability/traces/{trace_id}/replay",
                headers=headers,
            )
            assert resp.status_code == 201, f"call {i + 1}: {resp.text}"
        # 6th should hit the limit.
        resp = await client.post(
            f"/api/v1/admin-console/observability/traces/{trace_id}/replay",
            headers=headers,
        )
    assert resp.status_code == 429
    body = resp.json()
    assert body["reason"] == "rate_limited"
    assert 1 <= body["retry_after_seconds"] <= 60


async def test_replay_writes_audit_log_row(
    bootstrapped_db, seeded_trace, admin_user
) -> None:
    """Replay appends a row to admin_audit_log (FR-008)."""
    from app.main import create_app
    from app.core.config import get_settings

    trace_id, _ = seeded_trace
    headers = {"X-Admin-User-Id": str(admin_user)}
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            f"/api/v1/admin-console/observability/traces/{trace_id}/replay",
            headers=headers,
        )
    assert resp.status_code == 201
    new_trace_id = resp.json()["new_trace_id"]

    eng = create_async_engine(get_settings().database_url)
    try:
        async with eng.connect() as conn:
            rows = await conn.execute(
                text(
                    "SELECT action, target_kind, target_id, details FROM admin_audit_log "
                    "WHERE user_id = :uid"
                ),
                {"uid": str(admin_user)},
            )
            rows = list(rows)
            assert len(rows) == 1
            action, kind, target_id, details = rows[0]
            assert action == "replay_triggered"
            assert kind == "trace"
            assert str(target_id) == str(trace_id)
            assert details["orig_trace_id"] == str(trace_id)
            assert details["new_trace_id"] == new_trace_id
    finally:
        await eng.dispose()