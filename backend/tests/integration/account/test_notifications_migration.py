"""PostgreSQL contract tests for the account notifications migration."""

from __future__ import annotations

import os
import re
import subprocess
import uuid
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import Boolean, DateTime, Text, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import create_async_engine

pytestmark = pytest.mark.integration

_BACKEND_ROOT = Path(__file__).resolve().parents[3]
_SAFE_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_]{0,62}$")
_TEST_DATABASE = re.compile(r"^req072_(?:upgrade_)?[0-9a-f]{12}$")
_TEST_ROLE = re.compile(r"^req072_role_[0-9a-f]{12}$")
_DDL_OPT_IN = "REQ072_ALLOW_DATABASE_DDL"
_RESERVED_DATABASES = {"postgres", "template0", "template1"}
_OWNED_DATABASES: dict[str, str] = {}
_OWNED_ROLES: set[str] = set()


def _database_url(base_url: str, database: str) -> str:
    """Replace only the database component while preserving driver/options."""
    return make_url(base_url).set(database=database).render_as_string(hide_password=False)


def _identifier(value: str) -> str:
    if not _SAFE_IDENTIFIER.fullmatch(value):
        raise ValueError(f"unsafe generated PostgreSQL identifier: {value!r}")
    return f'"{value}"'


def _assert_database_ddl_allowed(base_url: str, database: str) -> None:
    """Fail closed before connecting to PostgreSQL or terminating sessions."""
    if os.environ.get(_DDL_OPT_IN) != "1":
        raise RuntimeError(f"database DDL requires explicit {_DDL_OPT_IN}=1")
    if not _TEST_DATABASE.fullmatch(database):
        raise ValueError(f"database is outside the req072 test namespace: {database!r}")

    parsed = make_url(base_url)
    base_database = parsed.database
    if not parsed.drivername.startswith("postgresql"):
        raise ValueError("notification migration tests require PostgreSQL")
    if not base_database or base_database in _RESERVED_DATABASES:
        raise ValueError("base URL must name a non-reserved test database")
    if database == base_database or database in _RESERVED_DATABASES:
        raise ValueError("refusing DDL against the base or a reserved database")


def _assert_role_ddl_allowed(base_url: str, role: str) -> None:
    if os.environ.get(_DDL_OPT_IN) != "1":
        raise RuntimeError(f"role DDL requires explicit {_DDL_OPT_IN}=1")
    if not _TEST_ROLE.fullmatch(role):
        raise ValueError(f"role is outside the req072 test namespace: {role!r}")
    parsed = make_url(base_url)
    if not parsed.drivername.startswith("postgresql") or not parsed.database:
        raise ValueError("role DDL requires a PostgreSQL test database URL")


def _run_alembic(url: str, target: str) -> None:
    proc = subprocess.run(
        ["uv", "run", "alembic", "upgrade", target],
        cwd=_BACKEND_ROOT,
        env={**os.environ, "DATABASE_URL": url},
        capture_output=True,
        text=True,
        check=False,
        timeout=180,
    )
    if proc.returncode != 0:
        details = (proc.stderr or proc.stdout)[-4000:].replace(url, "<database-url>")
        raise AssertionError(
            f"alembic upgrade {target!r} failed with rc={proc.returncode}: {details}"
        )


async def _create_database(base_url: str, database: str) -> str:
    _assert_database_ddl_allowed(base_url, database)
    marker = f"intercraft:req072:{uuid.uuid4().hex}"
    admin_url = _database_url(base_url, "postgres")
    engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        async with engine.connect() as conn:
            await conn.execute(text(f"CREATE DATABASE {_identifier(database)}"))
            await conn.execute(text(f"COMMENT ON DATABASE {_identifier(database)} IS '{marker}'"))
            _OWNED_DATABASES[database] = marker
    finally:
        await engine.dispose()
    return _database_url(base_url, database)


async def _drop_database(base_url: str, database: str) -> None:
    """Drop only a generated database whose catalog marker proves ownership."""
    _assert_database_ddl_allowed(base_url, database)
    expected_marker = _OWNED_DATABASES.get(database)
    if expected_marker is None:
        raise RuntimeError(f"refusing to drop unowned test database: {database!r}")

    admin_url = _database_url(base_url, "postgres")
    engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        async with engine.connect() as conn:
            actual_marker = await conn.scalar(
                text(
                    "SELECT shobj_description(oid, 'pg_database') FROM pg_database "
                    "WHERE datname = :database"
                ),
                {"database": database},
            )
            if actual_marker != expected_marker:
                raise RuntimeError(
                    f"refusing to drop database without the expected ownership marker: {database!r}"
                )
            await conn.execute(
                text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = :database AND pid <> pg_backend_pid()"
                ),
                {"database": database},
            )
            await conn.execute(text(f"DROP DATABASE {_identifier(database)}"))
            _OWNED_DATABASES.pop(database)
    finally:
        await engine.dispose()


async def _create_test_role(base_url: str, role: str) -> None:
    _assert_role_ddl_allowed(base_url, role)
    admin_url = _database_url(base_url, "postgres")
    engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        async with engine.connect() as conn:
            await conn.execute(
                text(
                    f"CREATE ROLE {_identifier(role)} NOLOGIN NOSUPERUSER "
                    "NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS"
                )
            )
            _OWNED_ROLES.add(role)
    finally:
        await engine.dispose()


async def _drop_test_role(base_url: str, role: str) -> None:
    _assert_role_ddl_allowed(base_url, role)
    if role not in _OWNED_ROLES:
        raise RuntimeError(f"refusing to drop unowned test role: {role!r}")
    admin_url = _database_url(base_url, "postgres")
    engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        async with engine.connect() as conn:
            await conn.execute(text(f"DROP ROLE {_identifier(role)}"))
            _OWNED_ROLES.remove(role)
    finally:
        await engine.dispose()


@pytest.fixture(scope="module")
def database_url() -> str:
    value = os.environ.get("DATABASE_URL", "")
    if not value or "PLACEHOLDER" in value:
        pytest.fail(
            "BLOCKED_ENVIRONMENT: notification migration contract requires a real PostgreSQL URL"
        )
    if os.environ.get(_DDL_OPT_IN) != "1":
        pytest.fail(f"BLOCKED_ENVIRONMENT: set {_DDL_OPT_IN}=1 only in an isolated CI database")
    parsed = make_url(value)
    if not parsed.database or parsed.database in _RESERVED_DATABASES:
        pytest.fail("BLOCKED_ENVIRONMENT: DATABASE_URL must name a non-reserved test database")
    return value


@pytest_asyncio.fixture(scope="module")
async def fresh_database(
    database_url: str,
) -> AsyncGenerator[tuple[str, str], None]:
    suffix = uuid.uuid4().hex[:12]
    database = f"req072_{suffix}"
    role = f"req072_role_{suffix}"
    url = await _create_database(database_url, database)
    try:
        _run_alembic(url, "0054_account_notifications")
        await _create_test_role(database_url, role)
        engine = create_async_engine(url)
        try:
            async with engine.begin() as conn:
                await conn.execute(text(f"GRANT USAGE ON SCHEMA public TO {_identifier(role)}"))
                await conn.execute(
                    text(
                        "GRANT SELECT, INSERT, UPDATE, DELETE ON notifications "
                        f"TO {_identifier(role)}"
                    )
                )
        finally:
            await engine.dispose()
        yield url, role
    finally:
        await _drop_database(database_url, database)
        await _drop_test_role(database_url, role)


async def _seed_user(conn, user_id: uuid.UUID, label: str) -> dict[str, object]:
    payload: dict[str, object] = {
        "id": user_id,
        "email": f"req072-{label}-{user_id}@example.test",
        "email_sha256": uuid.uuid4().bytes + uuid.uuid4().bytes,
        "password_hash": "synthetic-password-hash",
    }
    await conn.execute(
        text(
            "INSERT INTO users (id, email, email_sha256, password_hash) "
            "VALUES (:id, :email, :email_sha256, :password_hash)"
        ),
        payload,
    )
    return payload


async def _set_tenant_role(conn, role: str, user_id: uuid.UUID) -> None:
    await conn.execute(text(f"SET LOCAL ROLE {_identifier(role)}"))
    await conn.execute(
        text("SELECT set_config('app.user_id', :user_id, true)"),
        {"user_id": str(user_id)},
    )


async def test_fresh_upgrade_has_exact_notification_schema(
    fresh_database: tuple[str, str],
) -> None:
    url, _ = fresh_database
    engine = create_async_engine(url)
    try:
        async with engine.connect() as conn:
            version = await conn.scalar(text("SELECT version_num FROM alembic_version"))
            assert version == "0054_account_notifications"

            columns = {
                row.column_name: (row.data_type, row.is_nullable, row.column_default)
                for row in (
                    await conn.execute(
                        text(
                            "SELECT column_name, data_type, is_nullable, column_default "
                            "FROM information_schema.columns "
                            "WHERE table_schema = 'public' AND table_name = 'notifications'"
                        )
                    )
                )
            }
            assert set(columns) == {
                "id",
                "user_id",
                "type",
                "title",
                "message",
                "related_task_id",
                "is_read",
                "created_at",
            }
            assert columns["id"][0:2] == ("uuid", "NO")
            assert "gen_random_uuid" in (columns["id"][2] or "")
            assert columns["user_id"] == ("uuid", "NO", None)
            assert columns["related_task_id"] == ("uuid", "YES", None)
            assert columns["is_read"][0:2] == ("boolean", "NO")
            assert "false" in (columns["is_read"][2] or "").lower()
            assert columns["created_at"][0:2] == (
                "timestamp with time zone",
                "NO",
            )

            indexes = {
                row.indexname: row.indexdef
                for row in (
                    await conn.execute(
                        text(
                            "SELECT indexname, indexdef FROM pg_indexes "
                            "WHERE schemaname = 'public' AND tablename = 'notifications'"
                        )
                    )
                )
            }
            assert "notifications_pkey" in indexes
            assert "ix_notifications_user_id" in indexes
            unread = indexes["ix_notifications_user_unread_recent"].lower()
            assert "user_id" in unread and "created_at desc" in unread
            assert "where" in unread and "is_read" in unread and "false" in unread

            rls = (
                await conn.execute(
                    text(
                        "SELECT relrowsecurity, relforcerowsecurity FROM pg_class "
                        "WHERE oid = 'public.notifications'::regclass"
                    )
                )
            ).one()
            assert tuple(rls) == (True, True)

            policy = (
                await conn.execute(
                    text(
                        "SELECT policyname, qual, with_check FROM pg_policies "
                        "WHERE schemaname = 'public' AND tablename = 'notifications'"
                    )
                )
            ).one()
            assert policy.policyname == "notifications_user_isolation"
            for expression in (policy.qual, policy.with_check):
                assert "user_id" in expression
                assert "app.user_id" in expression
                assert "current_setting" in expression
                assert "NULLIF" in expression.upper()

            foreign_key = (
                await conn.execute(
                    text(
                        "SELECT confrelid::regclass::text AS target, confdeltype::text AS confdeltype "
                        "FROM pg_constraint "
                        "WHERE conname = 'notifications_user_id_fkey'"
                    )
                )
            ).one()
            assert foreign_key.target == "users"
            assert foreign_key.confdeltype == "c"
    finally:
        await engine.dispose()


async def test_genuine_0053_upgrade_preserves_existing_users(database_url: str) -> None:
    database = f"req072_upgrade_{uuid.uuid4().hex[:12]}"
    url = await _create_database(database_url, database)
    user_id = uuid.uuid4()
    try:
        _run_alembic(url, "0053_jobs_branch_v2")
        engine = create_async_engine(url)
        try:
            async with engine.begin() as conn:
                seeded = await _seed_user(conn, user_id, "upgrade")
        finally:
            await engine.dispose()

        _run_alembic(url, "0054_account_notifications")
        engine = create_async_engine(url)
        try:
            async with engine.connect() as conn:
                preserved = (
                    await conn.execute(
                        text(
                            "SELECT id, email, email_sha256, password_hash FROM users "
                            "WHERE id = :id"
                        ),
                        {"id": user_id},
                    )
                ).one()
                assert preserved.id == seeded["id"]
                assert preserved.email == seeded["email"]
                assert preserved.email_sha256 == seeded["email_sha256"]
                assert preserved.password_hash == seeded["password_hash"]
                assert (
                    await conn.scalar(text("SELECT to_regclass('public.notifications')"))
                    == "notifications"
                )
                assert (
                    await conn.scalar(text("SELECT version_num FROM alembic_version"))
                    == "0054_account_notifications"
                )
        finally:
            await engine.dispose()
    finally:
        await _drop_database(database_url, database)


async def test_two_tenant_crud_and_rls(
    fresh_database: tuple[str, str],
) -> None:
    url, role = fresh_database
    user_a = uuid.uuid4()
    user_b = uuid.uuid4()
    engine = create_async_engine(url)
    try:
        async with engine.begin() as conn:
            await _seed_user(conn, user_a, "tenant-a")
            await _seed_user(conn, user_b, "tenant-b")
            await conn.execute(
                text(
                    "INSERT INTO notifications (user_id, type, title, message) "
                    "VALUES (:user_id, 'seed', 'tenant-b', 'tenant-b')"
                ),
                {"user_id": user_b},
            )

        async with engine.begin() as conn:
            await _set_tenant_role(conn, role, user_a)
            assert (
                await conn.scalar(
                    text("SELECT rolbypassrls FROM pg_roles WHERE rolname = current_user")
                )
                is False
            )
            await conn.execute(
                text(
                    "INSERT INTO notifications (user_id, type, title, message) "
                    "VALUES (:user_id, 'created', 'tenant-a', 'tenant-a')"
                ),
                {"user_id": user_a},
            )
            rows = (
                await conn.execute(
                    text("SELECT user_id, is_read FROM notifications ORDER BY created_at")
                )
            ).all()
            assert rows == [(user_a, False)]
            assert (
                await conn.scalar(text("SELECT count(*) FROM notifications WHERE is_read = FALSE"))
                == 1
            )
            result = await conn.execute(
                text("UPDATE notifications SET is_read = TRUE WHERE user_id = :user_id"),
                {"user_id": user_a},
            )
            assert result.rowcount == 1

        async with engine.connect() as conn:
            transaction = await conn.begin()
            try:
                await _set_tenant_role(conn, role, user_a)
                with pytest.raises(DBAPIError):
                    await conn.execute(
                        text(
                            "INSERT INTO notifications "
                            "(user_id, type, title, message) "
                            "VALUES (:user_id, 'cross', 'cross', 'cross')"
                        ),
                        {"user_id": user_b},
                    )
            finally:
                await transaction.rollback()

        async with engine.begin() as conn:
            await _set_tenant_role(conn, role, user_a)
            result = await conn.execute(
                text("UPDATE notifications SET is_read = TRUE WHERE user_id = :user_id"),
                {"user_id": user_b},
            )
            assert result.rowcount == 0
    finally:
        await engine.dispose()


def test_notification_model_is_registered_for_alembic() -> None:
    from app.core.db import Base
    from app.modules.account.notification import Notification  # noqa: F401

    table = Base.metadata.tables["notifications"]
    columns = {column.name: column for column in table.columns}
    assert set(columns) == {
        "id",
        "user_id",
        "type",
        "title",
        "message",
        "related_task_id",
        "is_read",
        "created_at",
    }
    assert {foreign_key.target_fullname for foreign_key in table.foreign_keys} == {"users.id"}
    assert isinstance(columns["id"].type, PG_UUID)
    assert isinstance(columns["user_id"].type, PG_UUID)
    assert isinstance(columns["related_task_id"].type, PG_UUID)
    assert all(isinstance(columns[name].type, Text) for name in ("type", "title", "message"))
    assert isinstance(columns["is_read"].type, Boolean)
    assert isinstance(columns["created_at"].type, DateTime)
    assert columns["created_at"].type.timezone is True
    assert {name: column.nullable for name, column in columns.items()} == {
        "id": False,
        "user_id": False,
        "type": False,
        "title": False,
        "message": False,
        "related_task_id": True,
        "is_read": False,
        "created_at": False,
    }
    assert "gen_random_uuid" in str(columns["id"].server_default.arg)
    assert columns["is_read"].default.arg is False
    assert "now" in str(columns["created_at"].server_default.arg).lower()

    env_source = (_BACKEND_ROOT / "migrations" / "env.py").read_text(encoding="utf-8")
    assert "from app.modules.account.notification import Notification" in env_source
