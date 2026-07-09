"""REQ-039 US3 — diff HTTP E2E tests (FR-011/012/013/014/033).

Integration tests for ``POST /api/v1/admin-console/observability/traces/diff``.

Coverage:

- Same task_type: aligned by node_name with field-level diff.
- Different task_types: 400.
- Missing trace: 404.
- 21st diff call within 60s: 429.
- Audit log row written.
"""
from __future__ import annotations

import os
import uuid
from typing import AsyncIterator
from uuid import UUID

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import create_async_engine

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


# ---------------------------------------------------------------------------
# Shared bootstrap fixtures (re-defined for self-contained test module)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def bootstrapped_db() -> AsyncIterator[None]:
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
async def seeded_pair(bootstrapped_db) -> AsyncIterator[tuple[UUID, UUID, dict, dict]]:
    """Seed two traces with same task_type but different node payloads."""
    from app.core.config import get_settings

    left_id = uuid.uuid4()
    right_id = uuid.uuid4()
    user_id = uuid.uuid4()
    task_id = uuid.uuid4()
    left_payloads = {
        "plan": {"status": "ok", "score": 9, "items": [1, 2, 3]},
        "only_left": {"x": 1},
    }
    right_payloads = {
        "plan": {"status": "ok", "score": 7, "items": [1, 2, 3, 4]},
        "only_right": {"y": 2},
    }

    eng = create_async_engine(get_settings().database_url)
    try:
        async with eng.begin() as conn:
            for trace_id, payloads in (
                (left_id, left_payloads),
                (right_id, right_payloads),
            ):
                stmt = text(
                    """
                    INSERT INTO traces (
                        id, task_id, user_id, task_type, prompt_version, model,
                        input_payload, status, replay_of, node_payloads
                    ) VALUES (
                        :id, :tid, :uid, 'interview', 'v1.0', 'deepseek-v4-pro',
                        '{}'::jsonb, 'success', NULL, :payloads
                    )
                    """
                ).bindparams(bindparam("payloads", type_=JSONB))
                await conn.execute(
                    stmt,
                    {
                        "id": str(trace_id),
                        "tid": str(task_id),
                        "uid": str(user_id),
                        "payloads": payloads,
                    },
                )
        yield left_id, right_id, left_payloads, right_payloads
    finally:
        await eng.dispose()


@pytest_asyncio.fixture
async def admin_user() -> AsyncIterator[UUID]:
    """Provision an admin user by overriding require_admin and resetting rate limits."""
    from app.modules.admin_console import auth, rate_limit

    user_id = uuid.uuid4()

    # REQ-051: override require_admin to return True (no capability matrix)
    async def _admin_override(*args, **kwargs) -> bool:
        return True

    app = None
    try:
        from app.main import app as _app
        app = _app
    except Exception:
        pass
    if app is not None:
        app.dependency_overrides[auth.require_admin] = _admin_override

    rate_limit.reset_for_tests()
    yield user_id
    if app is not None:
        app.dependency_overrides.pop(auth.require_admin, None)
    rate_limit.reset_for_tests()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_diff_same_task_type_aligned_by_node_name(
    bootstrapped_db, seeded_pair, admin_user
) -> None:
    """Same task_type: nodes aligned by name + field-level diff computed."""
    from app.main import create_app

    left_id, right_id, _, _ = seeded_pair
    headers = {"X-Admin-User-Id": str(admin_user)}
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/admin-console/observability/traces/diff",
            json={
                "left_trace_id": str(left_id),
                "right_trace_id": str(right_id),
            },
            headers=headers,
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["task_type"] == "interview"
    assert body["node_count"] == 3  # only_left, only_right, plan
    names = [n["node_name"] for n in body["nodes"]]
    assert names == ["only_left", "only_right", "plan"]
    plan = next(n for n in body["nodes"] if n["node_name"] == "plan")
    assert plan["side"] == "both"
    assert any(f["op"] == "mod" for f in plan["fields"])


async def test_diff_cross_task_type_returns_400(
    bootstrapped_db, admin_user
) -> None:
    """Cross-task-type diff rejected with 400."""
    from app.core.config import get_settings
    from app.main import create_app

    left_id = uuid.uuid4()
    right_id = uuid.uuid4()
    eng = create_async_engine(get_settings().database_url)
    try:
        async with eng.begin() as conn:
            for tid, tt in ((left_id, "interview"), (right_id, "resume")):
                await conn.execute(
                    text(
                        "INSERT INTO traces (id, task_id, user_id, task_type, prompt_version, model, input_payload, status, replay_of, node_payloads) "
                        "VALUES (:id, :tid, :uid, :tt, 'v1', 'm', '{}'::jsonb, 'ok', NULL, '{}'::jsonb)"
                    ),
                    {
                        "id": str(tid),
                        "tid": str(uuid.uuid4()),
                        "uid": str(uuid.uuid4()),
                        "tt": tt,
                    },
                )
    finally:
        await eng.dispose()

    headers = {"X-Admin-User-Id": str(admin_user)}
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/admin-console/observability/traces/diff",
            json={"left_trace_id": str(left_id), "right_trace_id": str(right_id)},
            headers=headers,
        )
    assert resp.status_code == 400
    assert resp.json()["error"] == "CROSS_TASK_TYPE"


async def test_diff_missing_trace_returns_404(
    bootstrapped_db, admin_user
) -> None:
    """Missing trace returns 404."""
    from app.main import create_app

    headers = {"X-Admin-User-Id": str(admin_user)}
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/admin-console/observability/traces/diff",
            json={
                "left_trace_id": str(uuid.uuid4()),
                "right_trace_id": str(uuid.uuid4()),
            },
            headers=headers,
        )
    assert resp.status_code == 404
    assert resp.json()["error"] == "TRACE_NOT_FOUND"


async def test_diff_21st_call_in_window_returns_429(
    bootstrapped_db, seeded_pair, admin_user
) -> None:
    """21st diff within 60s returns 429 with retry_after_seconds."""
    from app.main import create_app

    left_id, right_id, _, _ = seeded_pair
    headers = {"X-Admin-User-Id": str(admin_user)}
    transport = ASGITransport(app=create_app())

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for i in range(20):
            resp = await client.post(
                "/api/v1/admin-console/observability/traces/diff",
                json={
                    "left_trace_id": str(left_id),
                    "right_trace_id": str(right_id),
                },
                headers=headers,
            )
            assert resp.status_code == 200, f"call {i + 1}: {resp.text}"
        # 21st hits the limit.
        resp = await client.post(
            "/api/v1/admin-console/observability/traces/diff",
            json={
                "left_trace_id": str(left_id),
                "right_trace_id": str(right_id),
            },
            headers=headers,
        )
    assert resp.status_code == 429
    body = resp.json()
    assert body["reason"] == "rate_limited"
    assert 1 <= body["retry_after_seconds"] <= 60


async def test_diff_writes_audit_log_row(
    bootstrapped_db, seeded_pair, admin_user
) -> None:
    """Diff appends a row to admin_audit_log (FR-014)."""
    from app.main import create_app
    from app.core.config import get_settings

    left_id, right_id, _, _ = seeded_pair
    headers = {"X-Admin-User-Id": str(admin_user)}
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/admin-console/observability/traces/diff",
            json={
                "left_trace_id": str(left_id),
                "right_trace_id": str(right_id),
            },
            headers=headers,
        )
    assert resp.status_code == 200

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
            assert action == "diff_computed"
            assert kind == "diff"
            assert target_id is None
            assert details["left_trace_id"] == str(left_id)
            assert details["right_trace_id"] == str(right_id)
            assert details["node_count"] == 3
    finally:
        await eng.dispose()