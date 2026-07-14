"""PostgreSQL 16 contract for the authoritative REQ-060 Agent task schema.

Verifies the linear chain ``0055_059_ai_resume -> 0056_060_wechat_agent_prod
-> 0057_060_agent_recovery_queue``:

* the fresh PostgreSQL 16 upgrade through 0057 lands the exact shipped Agent,
  inbox/outbox, confirmation, tool-execution, and recovery-queue contracts;
* upgrading a genuine 0055 predecessor preserves representative users,
  credentials, bindings, messages and resume data;
* every tenant table is RLS-ENABLE+FORCE; a non-superuser, non-BYPASSRLS app
  role sees only its own tenant rows and is rejected on cross-tenant writes;
* every SECURITY DEFINER function uses ``pg_catalog, public`` search path,
  the intended privileged owner, has PUBLIC execute revoked, and grants only
  the intended app role;
* the queue trigger enqueues running/waiting_external tasks only when a
  non-null ``claim_until`` is set; ``cancel_requested`` is due immediately;
  null claims never create immediate recovery work;
* recovery discovery is queue-backed, bounded, deterministic and idempotent;
  concurrent claims cannot duplicate recovery, and terminal tasks are removed
  from the queue;
* ``0057 -> 0055 -> 0057`` rehearsal leaves the 0055 schema free of orphan
  table/index/trigger/function/policy artefacts from 0056/0057;
* the ORM models match the live catalog for the REQ-060 consumers;
* the migrations produce exactly one Alembic head.
"""

from __future__ import annotations

import asyncio
import os
import re
import subprocess
import sys
import time
import uuid
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import (
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

pytestmark = pytest.mark.integration

_BACKEND_ROOT = Path(__file__).resolve().parents[3]
_SAFE_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_]{0,62}$")
_TEST_DATABASE = re.compile(r"^req077_(?:(?:upgrade|downgrade|rehearsal)_)?[0-9a-f]{12}$")
_TEST_ROLE = re.compile(r"^req077_role_[0-9a-f]{12}$")
_DDL_OPT_IN = "REQ077_ALLOW_DATABASE_DDL"
_RESERVED_DATABASES = {"postgres", "template0", "template1"}
_OWNED_DATABASES: dict[str, str] = {}
_OWNED_ROLES: dict[str, str] = {}
_PENDING_DATABASES: dict[str, tuple[str, str, str]] = {}
_DDL_TIMEOUT_SECONDS = 45.0
_ALEMBIC_TIMEOUT_SECONDS = 180.0

CONTROL_TABLES: set[str] = {
    "wechat_consumer_leases",
    "wechat_poll_batches",
    "wechat_inbox",
    "agent_tasks",
    "agent_task_events",
    "agent_confirmations",
    "agent_tool_executions",
    "agent_task_recovery_queue",
}

TENANT_TABLES: tuple[str, ...] = (
    "agent_tasks",
    "agent_task_events",
    "agent_tool_executions",
    "agent_confirmations",
    "agent_command_outbox",
)


def _database_url(base_url: str, database: str) -> str:
    return make_url(base_url).set(database=database).render_as_string(hide_password=False)


def _identifier(value: str) -> str:
    if not _SAFE_IDENTIFIER.fullmatch(value):
        raise ValueError(f"unsafe generated PostgreSQL identifier: {value!r}")
    return f'"{value}"'


def _remaining(deadline: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("isolated PostgreSQL operation exceeded its monotonic deadline")
    return remaining


def _assert_database_ddl_allowed(base_url: str, database: str) -> None:
    if os.environ.get(_DDL_OPT_IN) != "1":
        raise RuntimeError(f"database DDL requires explicit {_DDL_OPT_IN}=1")
    if not _TEST_DATABASE.fullmatch(database):
        raise ValueError(f"database is outside the req077 test namespace: {database!r}")
    parsed = make_url(base_url)
    base_database = parsed.database
    if not parsed.drivername.startswith("postgresql"):
        raise ValueError("REQ-060 migration tests require PostgreSQL")
    if not base_database or base_database in _RESERVED_DATABASES:
        raise ValueError("base URL must name a non-reserved isolated test database")
    if database == base_database or database in _RESERVED_DATABASES:
        raise ValueError("refusing DDL against the base or a reserved database")


def _assert_role_ddl_allowed(base_url: str, role: str) -> None:
    if os.environ.get(_DDL_OPT_IN) != "1":
        raise RuntimeError(f"role DDL requires explicit {_DDL_OPT_IN}=1")
    if not _TEST_ROLE.fullmatch(role):
        raise ValueError(f"role is outside the req077 test namespace: {role!r}")
    parsed = make_url(base_url)
    if (
        not parsed.drivername.startswith("postgresql")
        or not parsed.database
        or parsed.database in _RESERVED_DATABASES
    ):
        raise ValueError("role DDL requires a non-reserved PostgreSQL test database URL")


def _run_alembic(url: str, command: str, target: str) -> None:
    deadline = time.monotonic() + _ALEMBIC_TIMEOUT_SECONDS
    proc = subprocess.run(
        ["uv", "run", "alembic", command, target],
        cwd=_BACKEND_ROOT,
        env={**os.environ, "DATABASE_URL": url},
        capture_output=True,
        text=True,
        check=False,
        timeout=_remaining(deadline),
    )
    if proc.returncode != 0:
        details = (proc.stderr or proc.stdout)[-4000:].replace(url, "<database-url>")
        raise AssertionError(
            f"alembic {command} {target!r} failed with rc={proc.returncode}: {details}"
        )


async def _create_database(base_url: str, database: str) -> str:
    _assert_database_ddl_allowed(base_url, database)
    marker = f"intercraft:req077:database:{uuid.uuid4().hex}"
    expected_owner = make_url(base_url).username
    if not expected_owner:
        raise ValueError("database DDL requires an explicit PostgreSQL owner in DATABASE_URL")
    name_nonce = database.rsplit("_", 1)[-1]
    if not re.fullmatch(r"[0-9a-f]{12}", name_nonce):
        raise ValueError("database DDL requires a unique 12-hex name nonce")
    _PENDING_DATABASES[database] = (marker, expected_owner, name_nonce)
    deadline = time.monotonic() + _DDL_TIMEOUT_SECONDS
    engine = create_async_engine(_database_url(base_url, "postgres"), isolation_level="AUTOCOMMIT")
    created = False
    absence_verified = False
    try:
        async with asyncio.timeout(_remaining(deadline)):
            async with engine.connect() as conn:
                existing = await conn.scalar(
                    text("SELECT 1 FROM pg_database WHERE datname = :database"),
                    {"database": database},
                )
                if existing is not None:
                    raise RuntimeError(
                        f"refusing to create an already-existing test database: {database!r}"
                    )
                absence_verified = True
                await conn.execute(text(f"CREATE DATABASE {_identifier(database)}"))
                created = True
                await conn.execute(
                    text(f"COMMENT ON DATABASE {_identifier(database)} IS '{marker}'")
                )
                catalog = (
                    await conn.execute(
                        text(
                            "SELECT pg_get_userbyid(datdba) AS owner, "
                            "shobj_description(oid, 'pg_database') AS marker "
                            "FROM pg_database WHERE datname = :database"
                        ),
                        {"database": database},
                    )
                ).one_or_none()
                if catalog is None or tuple(catalog) != (expected_owner, marker):
                    raise RuntimeError(
                        "created database did not retain the expected owner/catalog marker"
                    )
                _OWNED_DATABASES[database] = marker
                _PENDING_DATABASES.pop(database)
    except BaseException as create_error:
        if created or absence_verified:
            try:
                await _compensate_partial_database(base_url, database)
            except BaseException as cleanup_error:
                cleanup_error.add_note(
                    f"original database creation failure: {type(create_error).__name__}: "
                    f"{create_error}"
                )
                raise
        else:
            _PENDING_DATABASES.pop(database, None)
        raise
    finally:
        await engine.dispose()
    return _database_url(base_url, database)


async def _compensate_partial_database(base_url: str, database: str) -> None:
    _assert_database_ddl_allowed(base_url, database)
    pending = _PENDING_DATABASES.get(database)
    if pending is None:
        raise RuntimeError(f"no pending ownership nonce for partial database: {database!r}")
    expected_marker, expected_owner, name_nonce = pending
    if database.rsplit("_", 1)[-1] != name_nonce:
        raise RuntimeError(f"pending database nonce no longer matches: {database!r}")
    deadline = time.monotonic() + _DDL_TIMEOUT_SECONDS
    engine = create_async_engine(_database_url(base_url, "postgres"), isolation_level="AUTOCOMMIT")
    try:
        async with asyncio.timeout(_remaining(deadline)):
            async with engine.connect() as conn:
                catalog = (
                    await conn.execute(
                        text(
                            "SELECT pg_get_userbyid(datdba) AS owner, "
                            "shobj_description(oid, 'pg_database') AS marker "
                            "FROM pg_database WHERE datname = :database"
                        ),
                        {"database": database},
                    )
                ).one_or_none()
                if catalog is None:
                    _PENDING_DATABASES.pop(database)
                    return
                actual_owner, actual_marker = tuple(catalog)
                if actual_owner != expected_owner or actual_marker not in (
                    None,
                    expected_marker,
                ):
                    raise RuntimeError(
                        "refusing partial-database cleanup without exact owner, namespace, "
                        f"and nonce proof: {database!r}"
                    )
                if actual_marker is None:
                    await conn.execute(
                        text(f"COMMENT ON DATABASE {_identifier(database)} IS '{expected_marker}'")
                    )
                    actual_marker = await conn.scalar(
                        text(
                            "SELECT shobj_description(oid, 'pg_database') "
                            "FROM pg_database WHERE datname = :database"
                        ),
                        {"database": database},
                    )
                if actual_marker != expected_marker:
                    raise RuntimeError(
                        f"refusing cleanup of database without verified nonce: {database!r}"
                    )
                _OWNED_DATABASES[database] = expected_marker
    finally:
        await engine.dispose()

    await _drop_database(base_url, database)
    _PENDING_DATABASES.pop(database, None)


async def _drop_database(base_url: str, database: str) -> None:
    _assert_database_ddl_allowed(base_url, database)
    expected_marker = _OWNED_DATABASES.get(database)
    if expected_marker is None:
        raise RuntimeError(f"refusing to drop unowned test database: {database!r}")
    deadline = time.monotonic() + _DDL_TIMEOUT_SECONDS
    engine = create_async_engine(_database_url(base_url, "postgres"), isolation_level="AUTOCOMMIT")
    try:
        async with asyncio.timeout(_remaining(deadline)):
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
                        "refusing to drop database without the expected catalog "
                        f"ownership marker: {database!r}"
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


async def _cleanup_database_state(base_url: str, database: str) -> None:
    if database in _OWNED_DATABASES:
        await _drop_database(base_url, database)
    elif database in _PENDING_DATABASES:
        await _compensate_partial_database(base_url, database)


async def _create_test_role(base_url: str, role: str) -> None:
    _assert_role_ddl_allowed(base_url, role)
    marker = f"intercraft:req077:role:{uuid.uuid4().hex}"
    deadline = time.monotonic() + _DDL_TIMEOUT_SECONDS
    engine = create_async_engine(_database_url(base_url, "postgres"))
    try:
        async with asyncio.timeout(_remaining(deadline)):
            async with engine.begin() as conn:
                await conn.execute(
                    text(
                        f"CREATE ROLE {_identifier(role)} NOLOGIN NOSUPERUSER "
                        "NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS"
                    )
                )
                await conn.execute(text(f"COMMENT ON ROLE {_identifier(role)} IS '{marker}'"))
                actual_marker = await conn.scalar(
                    text(
                        "SELECT shobj_description(oid, 'pg_authid') FROM pg_roles "
                        "WHERE rolname = :role"
                    ),
                    {"role": role},
                )
                if actual_marker != marker:
                    raise RuntimeError("created role did not retain the ownership marker")
                _OWNED_ROLES[role] = marker
    except BaseException:
        _OWNED_ROLES.pop(role, None)
        raise
    finally:
        await engine.dispose()


async def _drop_test_role(base_url: str, role: str) -> None:
    _assert_role_ddl_allowed(base_url, role)
    expected_marker = _OWNED_ROLES.get(role)
    if expected_marker is None:
        raise RuntimeError(f"refusing to drop unowned test role: {role!r}")
    deadline = time.monotonic() + _DDL_TIMEOUT_SECONDS
    engine = create_async_engine(_database_url(base_url, "postgres"), isolation_level="AUTOCOMMIT")
    try:
        async with asyncio.timeout(_remaining(deadline)):
            async with engine.connect() as conn:
                actual_marker = await conn.scalar(
                    text(
                        "SELECT shobj_description(oid, 'pg_authid') FROM pg_roles "
                        "WHERE rolname = :role"
                    ),
                    {"role": role},
                )
                if actual_marker != expected_marker:
                    raise RuntimeError(
                        "refusing to drop role without the expected catalog ownership "
                        f"marker: {role!r}"
                    )
                await conn.execute(text(f"DROP ROLE {_identifier(role)}"))
                _OWNED_ROLES.pop(role)
    finally:
        await engine.dispose()


@pytest.fixture(scope="module")
def database_url() -> str:
    value = os.environ.get("DATABASE_URL", "")
    if not value or "PLACEHOLDER" in value:
        pytest.fail("BLOCKED_ENVIRONMENT: REQ-060 contract requires a real PostgreSQL URL")
    if os.environ.get(_DDL_OPT_IN) != "1":
        pytest.fail(f"BLOCKED_ENVIRONMENT: set {_DDL_OPT_IN}=1 only in isolated CI")
    parsed = make_url(value)
    if not parsed.database or parsed.database in _RESERVED_DATABASES:
        pytest.fail("BLOCKED_ENVIRONMENT: DATABASE_URL must name a non-reserved test database")
    return value


@pytest_asyncio.fixture(scope="module")
async def fresh_database(
    database_url: str,
) -> AsyncGenerator[tuple[str, str], None]:
    suffix = uuid.uuid4().hex[:12]
    database = f"req077_{suffix}"
    role = f"req077_role_{suffix}"
    url: str | None = None
    try:
        url = await _create_database(database_url, database)
        _run_alembic(url, "upgrade", "0057_060_agent_recovery_queue")
        await _create_test_role(database_url, role)
        engine = create_async_engine(url)
        try:
            async with engine.begin() as conn:
                await conn.execute(text(f"GRANT USAGE ON SCHEMA public TO {_identifier(role)}"))
                for table in TENANT_TABLES:
                    await conn.execute(
                        text(
                            f"GRANT SELECT, INSERT, UPDATE, DELETE ON "
                            f"{_identifier(table)} TO {_identifier(role)}"
                        )
                    )
        finally:
            await engine.dispose()
        yield url, role
    finally:
        try:
            await _cleanup_database_state(database_url, database)
        finally:
            if role in _OWNED_ROLES:
                await _drop_test_role(database_url, role)


async def _seed_user(conn, user_id: uuid.UUID, label: str) -> dict[str, Any]:
    payload = {
        "id": user_id,
        "email": f"req077-{label}-{user_id}@example.test",
        "email_sha256": uuid.uuid4().bytes + uuid.uuid4().bytes,
        "password_hash": f"synthetic-password-hash-{label}",
    }
    await conn.execute(
        text(
            "INSERT INTO users (id, email, email_sha256, password_hash) "
            "VALUES (:id, :email, :email_sha256, :password_hash)"
        ),
        payload,
    )
    return payload


async def _seed_0055_graph(conn, user_id: uuid.UUID, label: str) -> dict[str, uuid.UUID]:
    job_id = uuid.uuid4()
    resume_id = uuid.uuid4()
    run_id = uuid.uuid4()
    credential_id = uuid.uuid4()
    binding_id = uuid.uuid4()
    message_id = uuid.uuid4()
    await conn.execute(
        text(
            "INSERT INTO jobs (id, user_id, company, position, status, status_history, "
            "base_location, employment_type, notes_md) VALUES "
            "(:id, :user_id, :company, :position, 'applied', '[]'::jsonb, "
            "'remote', 'full_time', :notes)"
        ),
        {
            "id": job_id,
            "user_id": user_id,
            "company": f"Company {label}",
            "position": f"Position {label}",
            "notes": f"preserve-job-{label}",
        },
    )
    await conn.execute(
        text(
            "INSERT INTO resumes_v2 (id, user_id, name, slug, tags, is_public, "
            "is_locked, data, version, resume_kind, derive_meta) VALUES "
            "(:id, :user_id, :name, :slug, ARRAY[:tag]::text[], false, false, "
            '\'{"marker": "req077"}\'::jsonb, 7, \'root\', \'{"source": "0055"}\'::jsonb)'
        ),
        {
            "id": resume_id,
            "user_id": user_id,
            "name": f"Resume {label}",
            "slug": f"req077-{label}-{resume_id.hex[:8]}",
            "tag": label,
        },
    )
    await conn.execute(
        text(
            "INSERT INTO resume_derive_runs (id, user_id, job_id, root_resume_id, "
            "root_version, target_page_count, template_id, status, phase, "
            "calibrate_round, progress_pct, artifacts) VALUES "
            "(:id, :user_id, :job_id, :resume_id, 7, 2, :template_id, 'pending', "
            "'parse_jd', 3, 11, '{\"preserve\": true}'::jsonb)"
        ),
        {
            "id": run_id,
            "user_id": user_id,
            "job_id": job_id,
            "resume_id": resume_id,
            "template_id": f"template-{label}",
        },
    )
    await conn.execute(
        text(
            "INSERT INTO wechat_credentials (id, user_id, bot_token_encrypted, base_url, "
            "cursor, status, last_polled_at, created_at, updated_at) VALUES "
            "(:id, :user_id, NULL, 'https://ilinkai.weixin.qq.com', '', 'active', NULL, "
            "now(), now())"
        ),
        {"id": credential_id, "user_id": user_id},
    )
    await conn.execute(
        text(
            "INSERT INTO wechat_bindings (id, user_id, wechat_uin, bound_at) VALUES "
            "(:id, :user_id, :uin, now())"
        ),
        {"id": binding_id, "user_id": user_id, "uin": f"uin-{label}-{user_id.hex[:8]}"},
    )
    await conn.execute(
        text(
            "INSERT INTO agent_messages (id, user_id, direction, content, message_type, "
            "status, wechat_msg_id, context_token, client_id, segments_total, "
            "segment_index, received_at, sent_at, error_message, "
            "created_at) VALUES "
            "(:id, :user_id, 'inbound', :content, 'text', 'received', :external_id, "
            "NULL, NULL, NULL, NULL, now(), NULL, NULL, now())"
        ),
        {
            "id": message_id,
            "user_id": user_id,
            "content": f"preserve-message-{label}",
            "external_id": f"msg-{label}-{user_id.hex[:8]}",
        },
    )
    return {
        "job_id": job_id,
        "resume_id": resume_id,
        "run_id": run_id,
        "credential_id": credential_id,
        "binding_id": binding_id,
        "message_id": message_id,
    }


async def _set_tenant_role(conn, role: str, user_id: uuid.UUID) -> None:
    await conn.execute(text(f"SET LOCAL ROLE {_identifier(role)}"))
    await conn.execute(
        text("SELECT set_config('app.user_id', :user_id, true)"),
        {"user_id": str(user_id)},
    )


async def _assert_cross_tenant_rejected(
    engine: AsyncEngine,
    role: str,
    user_id: uuid.UUID,
    statement: Any,
    parameters: dict[str, Any],
    expected_constraint: str,
) -> None:
    async with engine.connect() as conn:
        transaction = await conn.begin()
        try:
            await _set_tenant_role(conn, role, user_id)
            with pytest.raises(DBAPIError) as captured:
                await conn.execute(statement, parameters)
            sqlstate, constraint_name = _postgres_error_identity(captured.value)
            assert sqlstate == "23503"
            assert constraint_name == expected_constraint
        finally:
            await transaction.rollback()


async def _assert_same_tenant_succeeds(
    engine: AsyncEngine,
    role: str,
    user_id: uuid.UUID,
    statement: Any,
    parameters: dict[str, Any],
) -> None:
    """Prove INSERT succeeds when all FK targets belong to the same tenant."""
    async with engine.connect() as conn:
        transaction = await conn.begin()
        try:
            await _set_tenant_role(conn, role, user_id)
            await conn.execute(statement, parameters)
        finally:
            await transaction.rollback()


async def _assert_privileged_same_tenant_succeeds(
    engine: AsyncEngine,
    statement: Any,
    parameters: dict[str, Any],
) -> None:
    """Prove a non-RLS child write succeeds, then roll back its isolated transaction."""
    async with engine.connect() as conn:
        transaction = await conn.begin()
        try:
            await conn.execute(statement, parameters)
        finally:
            await transaction.rollback()


async def _assert_privileged_cross_tenant_rejected(
    engine: AsyncEngine,
    statement: Any,
    parameters: dict[str, Any],
    expected_constraint: str,
) -> None:
    """Assert an exact composite-FK rejection without poisoning another probe."""
    async with engine.connect() as conn:
        transaction = await conn.begin()
        try:
            with pytest.raises(DBAPIError) as captured:
                await conn.execute(statement, parameters)
            sqlstate, constraint_name = _postgres_error_identity(captured.value)
            assert sqlstate == "23503"
            assert constraint_name == expected_constraint
        finally:
            await transaction.rollback()


def _postgres_error_identity(error: DBAPIError) -> tuple[str | None, str | None]:
    sqlstate: str | None = None
    constraint_name: str | None = None
    pending: list[BaseException | Any] = [error.orig]
    seen: set[int] = set()
    while pending:
        current = pending.pop(0)
        if current is None or id(current) in seen:
            continue
        seen.add(id(current))
        sqlstate = (
            sqlstate or getattr(current, "sqlstate", None) or getattr(current, "pgcode", None)
        )
        diagnostic = getattr(current, "diag", None)
        constraint_name = (
            constraint_name
            or getattr(current, "constraint_name", None)
            or getattr(diagnostic, "constraint_name", None)
        )
        pending.extend(
            candidate
            for candidate in (
                getattr(current, "__cause__", None),
                getattr(current, "__context__", None),
            )
            if candidate is not None
        )
    return sqlstate, constraint_name


async def _table_columns(conn, table: str) -> dict[str, tuple[str, str, str | None]]:
    rows = (
        await conn.execute(
            text(
                "SELECT column_name, data_type, is_nullable, column_default "
                "FROM information_schema.columns WHERE table_schema = 'public' "
                "AND table_name = :table"
            ),
            {"table": table},
        )
    ).all()
    return {row.column_name: (row.data_type, row.is_nullable, row.column_default) for row in rows}


async def _table_catalog_columns(conn, table: str) -> dict[str, tuple[str, str | None]]:
    rows = (
        await conn.execute(
            text(
                "SELECT attribute.attname AS column_name, "
                "format_type(attribute.atttypid, attribute.atttypmod) AS type_sql, "
                "pg_get_expr(default_value.adbin, default_value.adrelid) AS default_sql "
                "FROM pg_attribute AS attribute "
                "LEFT JOIN pg_attrdef AS default_value "
                "ON default_value.adrelid = attribute.attrelid "
                "AND default_value.adnum = attribute.attnum "
                "WHERE attribute.attrelid = to_regclass(:table) "
                "AND attribute.attnum > 0 AND NOT attribute.attisdropped"
            ),
            {"table": f"public.{table}"},
        )
    ).all()
    return {row.column_name: (row.type_sql, row.default_sql) for row in rows}


def _normalize_catalog_sql(value: str | None) -> str | None:
    return None if value is None else re.sub(r"\s+", "", value).lower()


async def _rehearsal_database(database_url: str) -> tuple[str, uuid.UUID]:
    database = f"req077_rehearsal_{uuid.uuid4().hex[:12]}"
    url = await _create_database(database_url, database)
    user_id = uuid.uuid4()
    _run_alembic(url, "upgrade", "0055_059_ai_resume")
    engine = create_async_engine(url)
    try:
        async with engine.begin() as conn:
            await _seed_user(conn, user_id, "rehearsal")
            await _seed_0055_graph(conn, user_id, "rehearsal")
    finally:
        await engine.dispose()
    _run_alembic(url, "upgrade", "0057_060_agent_recovery_queue")
    _run_alembic(url, "downgrade", "0055_059_ai_resume")
    return url, user_id


async def test_ddl_guards_fail_closed_without_explicit_isolated_namespace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base = "postgresql+asyncpg://user:password@localhost:5432/intercraft_test"
    monkeypatch.delenv(_DDL_OPT_IN, raising=False)
    with pytest.raises(RuntimeError, match=_DDL_OPT_IN):
        _assert_database_ddl_allowed(base, "req077_0123456789ab")
    with pytest.raises(RuntimeError, match=_DDL_OPT_IN):
        _assert_role_ddl_allowed(base, "req077_role_0123456789ab")

    monkeypatch.setenv(_DDL_OPT_IN, "1")
    for unsafe in ("intercraft_test", "postgres", "req072_0123456789ab", "req077_bad"):
        with pytest.raises(ValueError):
            _assert_database_ddl_allowed(base, unsafe)
    with pytest.raises(ValueError):
        _assert_role_ddl_allowed(base, "appuser")

    class _ConnectionContext:
        def __init__(self, connection: Any) -> None:
            self.connection = connection

        async def __aenter__(self) -> Any:
            return self.connection

        async def __aexit__(self, *_: Any) -> None:
            return None

    class _FailingCommentConnection:
        def __init__(self, comment_prefix: str) -> None:
            self.comment_prefix = comment_prefix
            self.commands: list[str] = []

        async def execute(self, statement: Any, *_: Any, **__: Any) -> Any:
            command = str(statement)
            self.commands.append(command)
            if command.startswith(self.comment_prefix):
                raise TimeoutError("simulated COMMENT timeout")
            return object()

        async def scalar(self, *_: Any, **__: Any) -> None:
            return None

    class _ConnectEngine:
        def __init__(self, connection: Any) -> None:
            self.connection = connection
            self.disposed = False

        def connect(self) -> _ConnectionContext:
            return _ConnectionContext(self.connection)

        async def dispose(self) -> None:
            self.disposed = True

    database = "req077_0123456789ab"
    database_connection = _FailingCommentConnection("COMMENT ON DATABASE")
    database_engine = _ConnectEngine(database_connection)
    dropped: list[str] = []

    class _CatalogResult:
        def __init__(self, marker: str | None) -> None:
            self.marker = marker

        def one_or_none(self) -> tuple[str, str | None]:
            return ("user", self.marker)

    class _CompensationConnection:
        def __init__(self, catalog_marker: str | None = None) -> None:
            self.commands: list[str] = []
            self.catalog_marker = catalog_marker

        async def execute(self, statement: Any, *_: Any, **__: Any) -> Any:
            command = str(statement)
            self.commands.append(command)
            if "SELECT pg_get_userbyid" in command:
                return _CatalogResult(self.catalog_marker)
            return object()

        async def scalar(self, *_: Any, **__: Any) -> str:
            return _PENDING_DATABASES[database][0]

    compensation_connection = _CompensationConnection()
    compensation_engine = _ConnectEngine(compensation_connection)
    engines = iter((database_engine, compensation_engine))

    async def drop_owned_database(_: str, name: str) -> None:
        assert _OWNED_DATABASES[name] == _PENDING_DATABASES[name][0]
        dropped.append(name)
        _OWNED_DATABASES.pop(name)

    monkeypatch.setattr(
        sys.modules[__name__], "create_async_engine", lambda *_a, **_k: next(engines)
    )
    monkeypatch.setattr(sys.modules[__name__], "_drop_database", drop_owned_database)
    with pytest.raises(TimeoutError, match="COMMENT"):
        await _create_database(base, database)
    assert dropped == [database]
    assert database not in _PENDING_DATABASES
    assert database not in _OWNED_DATABASES
    assert database_engine.disposed is True
    assert compensation_engine.disposed is True
    assert any(command.startswith("CREATE DATABASE") for command in database_connection.commands)
    assert any(
        command.startswith("COMMENT ON DATABASE") for command in compensation_connection.commands
    )

    uncertain_database = "req077_abcdef012345"
    _PENDING_DATABASES[uncertain_database] = (
        "intercraft:req077:database:expected",
        "user",
        "abcdef012345",
    )
    uncertain_engine = _ConnectEngine(_CompensationConnection("foreign-marker"))
    monkeypatch.setattr(
        sys.modules[__name__], "create_async_engine", lambda *_a, **_k: uncertain_engine
    )
    with pytest.raises(RuntimeError, match="refusing partial-database cleanup"):
        await _compensate_partial_database(base, uncertain_database)
    assert uncertain_database in _PENDING_DATABASES
    assert uncertain_database not in _OWNED_DATABASES
    assert dropped == [database]
    assert uncertain_engine.disposed is True
    _PENDING_DATABASES.pop(uncertain_database)

    class _BeginContext(_ConnectionContext):
        def __init__(self, connection: Any) -> None:
            super().__init__(connection)
            self.rolled_back = False

        async def __aexit__(self, exc_type: Any, *_: Any) -> None:
            self.rolled_back = exc_type is not None
            return None

    class _BeginEngine(_ConnectEngine):
        def __init__(self, connection: Any) -> None:
            super().__init__(connection)
            self.transaction = _BeginContext(connection)

        def begin(self) -> _BeginContext:
            return self.transaction

    role = "req077_role_0123456789ab"
    role_connection = _FailingCommentConnection("COMMENT ON ROLE")
    role_engine = _BeginEngine(role_connection)
    monkeypatch.setattr(sys.modules[__name__], "create_async_engine", lambda *_a, **_k: role_engine)
    with pytest.raises(TimeoutError, match="COMMENT"):
        await _create_test_role(base, role)
    assert role not in _OWNED_ROLES
    assert role_engine.transaction.rolled_back is True
    assert role_engine.disposed is True
    assert role_connection.commands[0].startswith("CREATE ROLE")


async def test_fresh_upgrade_has_exact_schema_rls_orm_and_recovery_contract(
    fresh_database: tuple[str, str],
) -> None:
    url, _role = fresh_database
    engine = create_async_engine(url)
    try:
        async with engine.connect() as conn:
            server_version_num = int(await conn.scalar(text("SHOW server_version_num")))
            assert 160000 <= server_version_num < 170000
            assert (
                await conn.scalar(text("SELECT version_num FROM alembic_version"))
                == "0057_060_agent_recovery_queue"
            )

            tables = set(
                (
                    await conn.execute(
                        text(
                            "SELECT table_name FROM information_schema.tables "
                            "WHERE table_schema = 'public'"
                        )
                    )
                ).scalars()
            )
            assert tables >= CONTROL_TABLES
            assert (
                await conn.scalar(text("SELECT to_regclass('public.agent_task_recovery_queue')"))
                == "agent_task_recovery_queue"
            )

            expected_control_columns: dict[str, dict[str, tuple[str, str]]] = {
                "wechat_consumer_leases": {
                    "consumer_key": ("text", "NO"),
                    "owner_id": ("uuid", "YES"),
                    "fencing_token": ("bigint", "NO"),
                    "lease_until": ("timestamp with time zone", "YES"),
                    "heartbeat_at": ("timestamp with time zone", "YES"),
                    "acquired_at": ("timestamp with time zone", "YES"),
                    "metadata_json": ("jsonb", "NO"),
                },
                "wechat_poll_batches": {
                    "id": ("uuid", "NO"),
                    "consumer_key": ("text", "NO"),
                    "credential_id": ("uuid", "NO"),
                    "cursor_before_hash": ("text", "YES"),
                    "cursor_after_hash": ("text", "YES"),
                    "fencing_token": ("bigint", "NO"),
                    "item_count": ("integer", "NO"),
                    "persisted_count": ("integer", "NO"),
                    "status": ("text", "NO"),
                    "received_at": ("timestamp with time zone", "NO"),
                    "persisted_at": ("timestamp with time zone", "YES"),
                },
                "wechat_inbox": {
                    "id": ("uuid", "NO"),
                    "batch_id": ("uuid", "NO"),
                    "external_message_id": ("text", "YES"),
                    "dedupe_key": ("text", "NO"),
                    "sender_ref_hash": ("text", "NO"),
                    "credential_id": ("uuid", "NO"),
                    "binding_id": ("uuid", "YES"),
                    "user_id": ("uuid", "YES"),
                    "binding_epoch": ("bigint", "YES"),
                    "payload_encrypted": ("bytea", "YES"),
                    "parse_status": ("text", "NO"),
                    "processing_status": ("text", "NO"),
                    "claim_owner": ("uuid", "YES"),
                    "claim_until": ("timestamp with time zone", "YES"),
                    "attempt_count": ("integer", "NO"),
                    "next_attempt_at": ("timestamp with time zone", "YES"),
                    "error_category": ("text", "YES"),
                    "error_detail_redacted": ("text", "YES"),
                    "created_at": ("timestamp with time zone", "NO"),
                    "processed_at": ("timestamp with time zone", "YES"),
                },
                "agent_tasks": {
                    "id": ("uuid", "NO"),
                    "user_id": ("uuid", "NO"),
                    "source_message_id": ("uuid", "YES"),
                    "thread_id": ("text", "NO"),
                    "kind": ("text", "NO"),
                    "status": ("text", "NO"),
                    "stage": ("text", "NO"),
                    "progress_percent": ("smallint", "YES"),
                    "summary": ("text", "NO"),
                    "context_json": ("jsonb", "NO"),
                    "result_json": ("jsonb", "YES"),
                    "error_category": ("text", "YES"),
                    "error_detail_redacted": ("text", "YES"),
                    "cancel_requested_at": ("timestamp with time zone", "YES"),
                    "resume_from_task_id": ("uuid", "YES"),
                    "prompt_version": ("text", "NO"),
                    "tool_registry_version": ("text", "NO"),
                    "schema_version": ("text", "NO"),
                    "binding_id": ("uuid", "NO"),
                    "binding_epoch": ("bigint", "NO"),
                    "claim_owner": ("uuid", "YES"),
                    "claim_until": ("timestamp with time zone", "YES"),
                    "claim_generation": ("bigint", "NO"),
                    "version": ("integer", "NO"),
                    "created_at": ("timestamp with time zone", "NO"),
                    "updated_at": ("timestamp with time zone", "NO"),
                    "completed_at": ("timestamp with time zone", "YES"),
                },
                "agent_task_events": {
                    "id": ("uuid", "NO"),
                    "task_id": ("uuid", "NO"),
                    "user_id": ("uuid", "NO"),
                    "sequence": ("integer", "NO"),
                    "status": ("text", "NO"),
                    "stage": ("text", "NO"),
                    "percent": ("smallint", "YES"),
                    "message": ("text", "NO"),
                    "delivery_message_id": ("uuid", "YES"),
                    "occurred_at": ("timestamp with time zone", "NO"),
                },
                "agent_confirmations": {
                    "id": ("uuid", "NO"),
                    "user_id": ("uuid", "NO"),
                    "task_id": ("uuid", "NO"),
                    "tool_execution_id": ("uuid", "NO"),
                    "args_hash": ("text", "NO"),
                    "token_hash": ("bytea", "NO"),
                    "token_hint": ("text", "NO"),
                    "binding_id": ("uuid", "NO"),
                    "binding_epoch": ("bigint", "NO"),
                    "decision": ("text", "YES"),
                    "edited_args_json": ("jsonb", "YES"),
                    "status": ("text", "NO"),
                    "expires_at": ("timestamp with time zone", "NO"),
                    "decided_at": ("timestamp with time zone", "YES"),
                    "consumed_at": ("timestamp with time zone", "YES"),
                    "source_message_id": ("uuid", "YES"),
                    "version": ("integer", "NO"),
                },
                "agent_tool_executions": {
                    "id": ("uuid", "NO"),
                    "task_id": ("uuid", "NO"),
                    "user_id": ("uuid", "NO"),
                    "tool_call_id": ("text", "NO"),
                    "tool_name": ("text", "NO"),
                    "tool_version": ("text", "NO"),
                    "args_hash": ("text", "NO"),
                    "args_json": ("jsonb", "NO"),
                    "idempotency_key": ("text", "NO"),
                    "side_effect": ("text", "NO"),
                    "atomicity": ("text", "NO"),
                    "status": ("text", "NO"),
                    "attempt_count": ("integer", "NO"),
                    "claim_owner": ("uuid", "YES"),
                    "claim_until": ("timestamp with time zone", "YES"),
                    "claim_generation": ("bigint", "NO"),
                    "binding_id": ("uuid", "NO"),
                    "binding_epoch": ("bigint", "NO"),
                    "provider_operation_id": ("text", "YES"),
                    "result_json": ("jsonb", "YES"),
                    "resource_type": ("text", "YES"),
                    "resource_id": ("uuid", "YES"),
                    "error_category": ("text", "YES"),
                    "started_at": ("timestamp with time zone", "YES"),
                    "committed_at": ("timestamp with time zone", "YES"),
                    "finished_at": ("timestamp with time zone", "YES"),
                },
                "agent_task_recovery_queue": {
                    "task_id": ("uuid", "NO"),
                    "user_id": ("uuid", "NO"),
                    "next_check_at": ("timestamp with time zone", "NO"),
                    "updated_at": ("timestamp with time zone", "NO"),
                },
            }
            for table, expected in expected_control_columns.items():
                columns = await _table_columns(conn, table)
                assert set(columns) == set(expected)
                assert {
                    name: (definition[0], definition[1]) for name, definition in columns.items()
                } == expected

            expected_defaults = {
                "wechat_consumer_leases": {"fencing_token": "0", "metadata_json": "{}"},
                "wechat_poll_batches": {
                    "persisted_count": "0",
                    "status": "received",
                    "received_at": "now()",
                },
                "wechat_inbox": {
                    "processing_status": "received",
                    "attempt_count": "0",
                    "created_at": "now()",
                },
                "agent_tasks": {
                    "status": "received",
                    "stage": "received",
                    "summary": "''",
                    "context_json": "{}",
                    "schema_version": "agent-task.v1",
                    "claim_generation": "0",
                    "version": "1",
                    "created_at": "now()",
                    "updated_at": "now()",
                },
                "agent_task_events": {"occurred_at": "now()"},
                "agent_tool_executions": {
                    "args_json": "{}",
                    "status": "proposed",
                    "attempt_count": "0",
                    "claim_generation": "0",
                },
                "agent_confirmations": {
                    "status": "pending",
                    "version": "1",
                },
                "agent_task_recovery_queue": {"updated_at": "now()"},
            }
            for table, defaults in expected_defaults.items():
                columns = await _table_columns(conn, table)
                defaulted = {name: (columns[name][2] or "") for name in defaults}
                assert set(defaulted) == set(defaults)
                for name, fragment in defaults.items():
                    assert fragment in defaulted[name], (table, name)

            indexes = {
                row.indexname: row.indexdef.lower()
                for row in (
                    await conn.execute(
                        text(
                            "SELECT indexname, indexdef FROM pg_indexes WHERE schemaname = 'public'"
                        )
                    )
                )
            }
            expected_index_fragments = {
                "uq_wechat_inbox_dedupe": ("unique", "dedupe_key"),
                "uq_agent_task_source_message": (
                    "unique",
                    "source_message_id",
                    "where",
                    "is not null",
                ),
                "uq_agent_task_event_sequence": (
                    "unique",
                    "task_id",
                    "sequence",
                ),
                "uq_agent_tool_execution_idempotency": (
                    "unique",
                    "user_id",
                    "idempotency_key",
                ),
                "uq_agent_tool_execution_call": (
                    "unique",
                    "task_id",
                    "tool_call_id",
                ),
                "uq_agent_message_inbound_dedupe": (
                    "unique",
                    "channel",
                    "user_id",
                    "dedupe_key",
                    "where",
                    "direction",
                    "inbound",
                ),
                "uq_agent_confirmation_token": (
                    "unique",
                    "user_id",
                    "token_hash",
                ),
                "uq_agent_tasks_resume_from": (
                    "unique",
                    "resume_from_task_id",
                    "where",
                    "is not null",
                ),
                "idx_agent_task_recovery_due": (
                    "next_check_at",
                    "task_id",
                ),
            }
            for name, fragments in expected_index_fragments.items():
                assert name in indexes
                assert all(fragment in indexes[name] for fragment in fragments), (
                    name,
                    indexes[name],
                )

            for table in TENANT_TABLES:
                rls = (
                    await conn.execute(
                        text(
                            "SELECT relrowsecurity, relforcerowsecurity FROM pg_class "
                            "WHERE oid = to_regclass(:table)"
                        ),
                        {"table": f"public.{table}"},
                    )
                ).one()
                assert tuple(rls) == (True, True)
                policies = (
                    await conn.execute(
                        text(
                            "SELECT policyname, qual, with_check FROM pg_policies "
                            "WHERE schemaname = 'public' AND tablename = :table"
                        ),
                        {"table": table},
                    )
                ).all()
                assert len(policies) == 1
                assert policies[0].policyname == f"{table}_tenant_isolation"
                assert policies[0].qual == policies[0].with_check
                for expression in (policies[0].qual, policies[0].with_check):
                    assert "user_id" in expression
                    assert "app.user_id" in expression
                    assert "current_setting" in expression
                    assert "NULLIF" in expression.upper()

            function_query = (
                await conn.execute(
                    text(
                        "SELECT p.proname, p.prosecdef, "
                        "pg_get_function_identity_arguments(p.oid) AS identity_args, "
                        "pg_get_function_result(p.oid) AS result_signature, "
                        "pg_get_userbyid(p.proowner) AS owner, "
                        "ARRAY(SELECT pg_get_userbyid(grantee.oid) FROM "
                        "aclexplode(p.proacl) AS ac LEFT JOIN pg_roles grantee ON "
                        "grantee.oid = ac.grantee WHERE ac.grantee <> 0) AS grantees, "
                        "ARRAY(SELECT privilege_type FROM "
                        "aclexplode(p.proacl) AS ac WHERE ac.grantee <> 0) AS grant_privs "
                        "FROM pg_proc p WHERE p.proname IN "
                        "('sync_agent_task_recovery_queue', "
                        "'get_agent_task_recovery_candidates')"
                    )
                )
            ).all()
            by_name = {row.proname: row for row in function_query}
            assert set(by_name) == {
                "sync_agent_task_recovery_queue",
                "get_agent_task_recovery_candidates",
            }
            for proname, row in by_name.items():
                assert row.prosecdef is True, proname
                assert row.owner == "postgres", proname

            config_query = (
                await conn.execute(
                    text(
                        "SELECT p.proname, p.proconfig FROM pg_proc p "
                        "WHERE p.proname IN "
                        "('sync_agent_task_recovery_queue', "
                        "'get_agent_task_recovery_candidates')"
                    )
                )
            ).all()
            for row in config_query:
                assert "search_path=pg_catalog, public" in (row.proconfig or []), (
                    row.proname,
                    row.proconfig,
                )

            grants = (
                await conn.execute(
                    text(
                        "SELECT routine_name, grantee, privilege_type FROM "
                        "information_schema.routine_privileges "
                        "WHERE routine_schema = 'public' AND routine_name IN "
                        "('sync_agent_task_recovery_queue', "
                        "'get_agent_task_recovery_candidates')"
                    )
                )
            ).all()
            granted_to = {(row.routine_name, row.grantee): row.privilege_type for row in grants}
            assert granted_to[("get_agent_task_recovery_candidates", "appuser")] == "EXECUTE"
            assert (
                "get_agent_task_recovery_candidates",
                "PUBLIC",
            ) not in granted_to
            assert ("sync_agent_task_recovery_queue", "PUBLIC") not in granted_to
            assert ("sync_agent_task_recovery_queue", "appuser") not in granted_to

            trigger = await conn.scalar(
                text(
                    "SELECT EXISTS (SELECT 1 FROM pg_trigger "
                    "WHERE tgname = 'trg_agent_task_recovery_queue' AND NOT tgisinternal)"
                )
            )
            assert trigger is True

            trigger_columns = (
                await conn.execute(
                    text(
                        "SELECT tgrelid::regclass::text, "
                        "ARRAY(SELECT attname FROM pg_attribute "
                        "WHERE attrelid = tgrelid AND attnum = ANY(tgattr)) AS cols "
                        "FROM pg_trigger "
                        "WHERE tgname = 'trg_agent_task_recovery_queue' AND NOT tgisinternal"
                    )
                )
            ).one()
            assert trigger_columns.tgrelid == "agent_tasks"
            assert set(trigger_columns.cols) == {
                "status",
                "claim_until",
                "user_id",
            }

            user_id_a = uuid.uuid4()
            user_id_b = uuid.uuid4()
            await conn.execute(text("ALTER TABLE wechat_credentials DISABLE ROW LEVEL SECURITY"))
            await conn.execute(text("ALTER TABLE wechat_credentials NO FORCE ROW LEVEL SECURITY"))
            await conn.execute(text("COMMIT"))
        async with engine.begin() as conn:
            await _seed_user(conn, user_id_a, "tenant-a")
            await _seed_user(conn, user_id_b, "tenant-b")
            for user_id in (user_id_a, user_id_b):
                binding_id = uuid.uuid4()
                credential_id = uuid.uuid4()
                await conn.execute(
                    text(
                        "INSERT INTO wechat_bindings (id, user_id, wechat_uin, bound_at) "
                        "VALUES (:id, :user_id, :uin, now())"
                    ),
                    {
                        "id": binding_id,
                        "user_id": user_id,
                        "uin": f"recovery-uin-{user_id.hex[:8]}",
                    },
                )
                await conn.execute(
                    text(
                        "INSERT INTO wechat_credentials (id, user_id, base_url, cursor, "
                        "status, last_polled_at, created_at, updated_at) VALUES "
                        "(:id, :user_id, 'https://ilinkai.weixin.qq.com', '', 'active', "
                        "NULL, now(), now())"
                    ),
                    {"id": credential_id, "user_id": user_id},
                )

        async with engine.connect() as conn:
            conn = await conn.execution_options(isolation_level="AUTOCOMMIT")
            await conn.execute(text("ALTER TABLE wechat_credentials ENABLE ROW LEVEL SECURITY"))
            await conn.execute(text("ALTER TABLE wechat_credentials FORCE ROW LEVEL SECURITY"))

            await conn.execute(
                text(
                    "INSERT INTO agent_tasks (id, user_id, source_message_id, thread_id, "
                    "kind, status, stage, progress_percent, summary, context_json, "
                    "result_json, error_category, error_detail_redacted, "
                    "cancel_requested_at, resume_from_task_id, prompt_version, "
                    "tool_registry_version, schema_version, binding_id, binding_epoch, "
                    "claim_owner, claim_until, claim_generation, version, created_at, "
                    "updated_at, completed_at) VALUES "
                    "(:id, :user_id, NULL, :thread, :kind, 'running', 'running', NULL, "
                    "'preserve', '{}'::jsonb, NULL, NULL, NULL, NULL, NULL, "
                    "'wechat-agent.v2', 'intercraft-agent-tools.v1', 'agent-task.v1', "
                    ":binding_id, 1, NULL, now() + interval '60 seconds', 0, 1, now(), "
                    "now(), NULL)"
                ),
                {
                    "id": uuid.uuid4(),
                    "user_id": user_id_a,
                    "thread": "t-running",
                    "kind": "wechat",
                    "binding_id": (
                        await conn.scalar(
                            text("SELECT id FROM wechat_bindings WHERE user_id = :u LIMIT 1"),
                            {"u": user_id_a},
                        )
                    ),
                },
            )
            await conn.execute(
                text(
                    "INSERT INTO agent_tasks (id, user_id, source_message_id, thread_id, "
                    "kind, status, stage, progress_percent, summary, context_json, "
                    "result_json, error_category, error_detail_redacted, "
                    "cancel_requested_at, resume_from_task_id, prompt_version, "
                    "tool_registry_version, schema_version, binding_id, binding_epoch, "
                    "claim_owner, claim_until, claim_generation, version, created_at, "
                    "updated_at, completed_at) VALUES "
                    "(:id, :user_id, NULL, :thread, :kind, 'running', 'running', NULL, "
                    "'null-claim', '{}'::jsonb, NULL, NULL, NULL, NULL, NULL, "
                    "'wechat-agent.v2', 'intercraft-agent-tools.v1', 'agent-task.v1', "
                    ":binding_id, 1, NULL, NULL, 0, 1, now(), now(), NULL)"
                ),
                {
                    "id": uuid.uuid4(),
                    "user_id": user_id_a,
                    "thread": "t-null-claim",
                    "kind": "wechat",
                    "binding_id": (
                        await conn.scalar(
                            text("SELECT id FROM wechat_bindings WHERE user_id = :u LIMIT 1"),
                            {"u": user_id_a},
                        )
                    ),
                },
            )
            await conn.execute(
                text(
                    "INSERT INTO agent_tasks (id, user_id, source_message_id, thread_id, "
                    "kind, status, stage, progress_percent, summary, context_json, "
                    "result_json, error_category, error_detail_redacted, "
                    "cancel_requested_at, resume_from_task_id, prompt_version, "
                    "tool_registry_version, schema_version, binding_id, binding_epoch, "
                    "claim_owner, claim_until, claim_generation, version, created_at, "
                    "updated_at, completed_at) VALUES "
                    "(:id, :user_id, NULL, :thread, :kind, 'cancel_requested', "
                    "'cancel_requested', NULL, 'cancel', '{}'::jsonb, NULL, NULL, NULL, "
                    "now(), NULL, 'wechat-agent.v2', 'intercraft-agent-tools.v1', "
                    "'agent-task.v1', :binding_id, 1, NULL, NULL, 0, 1, now(), now(), "
                    "NULL)"
                ),
                {
                    "id": uuid.uuid4(),
                    "user_id": user_id_a,
                    "thread": "t-cancel",
                    "kind": "wechat",
                    "binding_id": (
                        await conn.scalar(
                            text("SELECT id FROM wechat_bindings WHERE user_id = :u LIMIT 1"),
                            {"u": user_id_a},
                        )
                    ),
                },
            )
            await conn.execute(
                text(
                    "INSERT INTO agent_tasks (id, user_id, source_message_id, thread_id, "
                    "kind, status, stage, progress_percent, summary, context_json, "
                    "result_json, error_category, error_detail_redacted, "
                    "cancel_requested_at, resume_from_task_id, prompt_version, "
                    "tool_registry_version, schema_version, binding_id, binding_epoch, "
                    "claim_owner, claim_until, claim_generation, version, created_at, "
                    "updated_at, completed_at) VALUES "
                    "(:id, :user_id, NULL, :thread, :kind, 'succeeded', 'succeeded', 100, "
                    "'done', '{}'::jsonb, NULL, NULL, NULL, NULL, NULL, "
                    "'wechat-agent.v2', 'intercraft-agent-tools.v1', 'agent-task.v1', "
                    ":binding_id, 1, NULL, NULL, 0, 1, now(), now(), now())"
                ),
                {
                    "id": uuid.uuid4(),
                    "user_id": user_id_a,
                    "thread": "t-done",
                    "kind": "wechat",
                    "binding_id": (
                        await conn.scalar(
                            text("SELECT id FROM wechat_bindings WHERE user_id = :u LIMIT 1"),
                            {"u": user_id_a},
                        )
                    ),
                },
            )

            due_ids = [
                row.task_id
                for row in (
                    await conn.execute(
                        text(
                            "SELECT task_id, next_check_at FROM agent_task_recovery_queue "
                            "WHERE next_check_at <= now()"
                        )
                    )
                )
            ]
            assert len(due_ids) == 2, due_ids

            null_claim_due = (
                await conn.execute(
                    text(
                        "SELECT EXISTS (SELECT 1 FROM agent_task_recovery_queue "
                        "WHERE next_check_at <= now() AND user_id = :user_id "
                        "AND task_id IN (SELECT id FROM agent_tasks "
                        "WHERE status = 'running' AND claim_until IS NULL))"
                    ),
                    {"user_id": user_id_a},
                )
            ).scalar()
            assert null_claim_due is False

            cancel_id = await conn.scalar(
                text(
                    "SELECT task_id FROM agent_task_recovery_queue "
                    "WHERE user_id = :user_id "
                    "AND task_id IN (SELECT id FROM agent_tasks "
                    "WHERE status = 'cancel_requested')"
                ),
                {"user_id": user_id_a},
            )
            assert cancel_id is not None

            done_in_queue = (
                await conn.execute(
                    text("SELECT COUNT(*) FROM agent_task_recovery_queue WHERE user_id = :u"),
                    {"u": user_id_a},
                )
            ).scalar()
            assert done_in_queue == 2

            async with conn.begin():
                first = await conn.execute(
                    text("SELECT task_id FROM get_agent_task_recovery_candidates(:n)"),
                    {"n": 1},
                )
                first_ids = [row.task_id for row in first]
                second = await conn.execute(
                    text("SELECT task_id FROM get_agent_task_recovery_candidates(:n)"),
                    {"n": 1},
                )
                second_ids = [row.task_id for row in second]
                assert first_ids == second_ids

                queue_count = (
                    await conn.execute(
                        text(
                            "SELECT COUNT(*) FROM agent_task_recovery_queue "
                            "WHERE task_id = ANY(:ids)"
                        ),
                        {"ids": first_ids},
                    )
                ).scalar()
                assert queue_count == len(first_ids)
    finally:
        await engine.dispose()


async def test_genuine_0055_upgrade_preserves_users_resumes_jobs_messages(
    database_url: str,
) -> None:
    database = f"req077_upgrade_{uuid.uuid4().hex[:12]}"
    url: str | None = None
    user_id = uuid.uuid4()
    try:
        url = await _create_database(database_url, database)
        _run_alembic(url, "upgrade", "0055_059_ai_resume")
        engine = create_async_engine(url)
        try:
            async with engine.begin() as conn:
                seeded = await _seed_user(conn, user_id, "upgrade")
                graph = await _seed_0055_graph(conn, user_id, "upgrade")
        finally:
            await engine.dispose()

        _run_alembic(url, "upgrade", "0057_060_agent_recovery_queue")
        engine = create_async_engine(url)
        try:
            async with engine.connect() as conn:
                preserved_user = (
                    await conn.execute(
                        text(
                            "SELECT id, email, email_sha256, password_hash FROM users WHERE id = :id"
                        ),
                        {"id": user_id},
                    )
                ).one()
                assert tuple(preserved_user) == (
                    seeded["id"],
                    seeded["email"],
                    seeded["email_sha256"],
                    seeded["password_hash"],
                )
                assert (
                    await conn.execute(
                        text("SELECT company, position, notes_md FROM jobs WHERE id = :id"),
                        {"id": graph["job_id"]},
                    )
                ).one() == ("Company upgrade", "Position upgrade", "preserve-job-upgrade")
                assert (
                    await conn.execute(
                        text(
                            "SELECT name, version, data, derive_meta FROM resumes_v2 WHERE id = :id"
                        ),
                        {"id": graph["resume_id"]},
                    )
                ).one() == (
                    "Resume upgrade",
                    7,
                    {"marker": "req077"},
                    {"source": "0055"},
                )
                preserved_message = (
                    await conn.execute(
                        text(
                            "SELECT direction, content, channel FROM agent_messages WHERE id = :id"
                        ),
                        {"id": graph["message_id"]},
                    )
                ).one()
                assert preserved_message == (
                    "inbound",
                    "preserve-message-upgrade",
                    "wechat",
                )
                preserved_binding = (
                    await conn.execute(
                        text(
                            "SELECT wechat_uin, bound_at IS NOT NULL FROM wechat_bindings WHERE id = :id"
                        ),
                        {"id": graph["binding_id"]},
                    )
                ).one()
                assert preserved_binding[0] == f"uin-upgrade-{user_id.hex[:8]}"
                assert preserved_binding[1] is True
                assert (
                    await conn.scalar(text("SELECT version_num FROM alembic_version"))
                    == "0057_060_agent_recovery_queue"
                )
                assert (
                    await conn.scalar(
                        text("SELECT to_regclass('public.agent_task_recovery_queue')")
                    )
                    == "agent_task_recovery_queue"
                )
        finally:
            await engine.dispose()
    finally:
        await _cleanup_database_state(database_url, database)


async def test_non_bypass_role_enforces_two_tenant_crud_and_queue_visibility(
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
            for user_id in (user_a, user_b):
                binding_id = uuid.uuid4()
                credential_id = uuid.uuid4()
                await conn.execute(
                    text(
                        "INSERT INTO wechat_bindings (id, user_id, wechat_uin, bound_at) "
                        "VALUES (:id, :user_id, :uin, now())"
                    ),
                    {
                        "id": binding_id,
                        "user_id": user_id,
                        "uin": f"isolation-uin-{user_id.hex[:8]}",
                    },
                )
                await conn.execute(
                    text(
                        "INSERT INTO wechat_credentials (id, user_id, base_url, cursor, "
                        "status, last_polled_at, created_at, updated_at) VALUES "
                        "(:id, :user_id, 'https://ilinkai.weixin.qq.com', '', 'active', "
                        "NULL, now(), now())"
                    ),
                    {"id": credential_id, "user_id": user_id},
                )
                if user_id == user_a:
                    binding_a = binding_id
                    credential_a = credential_id
                else:
                    binding_b = binding_id
                    credential_b = credential_id
                task_id = uuid.uuid4()
                await conn.execute(
                    text(
                        "INSERT INTO agent_tasks (id, user_id, source_message_id, "
                        "thread_id, kind, status, stage, progress_percent, summary, "
                        "context_json, result_json, error_category, "
                        "error_detail_redacted, cancel_requested_at, "
                        "resume_from_task_id, prompt_version, tool_registry_version, "
                        "schema_version, binding_id, binding_epoch, claim_owner, "
                        "claim_until, claim_generation, version, created_at, "
                        "updated_at, completed_at) VALUES "
                        "(:id, :user_id, NULL, :thread, 'wechat', 'running', "
                        "'running', NULL, 'isolation', '{}'::jsonb, NULL, NULL, "
                        "NULL, NULL, NULL, 'wechat-agent.v2', "
                        "'intercraft-agent-tools.v1', 'agent-task.v1', "
                        ":binding_id, 1, NULL, now() - interval '5 seconds', 0, 1, "
                        "now(), now(), NULL)"
                    ),
                    {
                        "id": task_id,
                        "user_id": user_id,
                        "thread": f"t-{user_id.hex[:8]}",
                        "binding_id": binding_id,
                    },
                )

        async with engine.connect() as conn:
            transaction = await conn.begin()
            try:
                await conn.execute(text(f"SET LOCAL ROLE {_identifier(role)}"))
                for table in TENANT_TABLES:
                    assert (
                        await conn.scalar(text(f"SELECT count(*) FROM {_identifier(table)}")) == 0
                    )
                with pytest.raises(DBAPIError):
                    await conn.execute(
                        text(
                            "INSERT INTO agent_task_events (id, task_id, user_id, "
                            "sequence, status, stage, percent, message, "
                            "delivery_message_id, occurred_at) VALUES "
                            "(:id, :task_id, :user_id, 1, 'running', 'running', NULL, "
                            "'cross', NULL, now())"
                        ),
                        {
                            "id": uuid.uuid4(),
                            "task_id": uuid.uuid4(),
                            "user_id": user_a,
                        },
                    )
            finally:
                await transaction.rollback()

        async with engine.begin() as conn:
            await _set_tenant_role(conn, role, user_a)
            assert (
                await conn.scalar(
                    text("SELECT rolbypassrls FROM pg_roles WHERE rolname = current_user")
                )
                is False
            )
            assert (
                await conn.scalar(
                    text("SELECT count(*) FROM agent_tasks WHERE user_id = :u"),
                    {"u": user_a},
                )
                == 1
            )
            # Ordinary tenant role is denied direct access to the recovery
            # queue table; queue-backed discovery is the only legal route.
            # The 42501 error must NOT poison the outer transaction. Catch the
            # exception OUTSIDE the nested transaction context so the savepoint
            # exits on exception (rollback), not on RELEASE.
            with pytest.raises(DBAPIError) as direct_access:
                async with conn.begin_nested():
                    await conn.execute(
                        text("SELECT count(*) FROM agent_task_recovery_queue WHERE user_id = :u"),
                        {"u": user_a},
                    )
            assert direct_access.value.orig.sqlstate == "42501"

            # After SAVEPOINT rollback, the outer transaction is still usable.
            user_a_task_id = await conn.scalar(
                text("SELECT id FROM agent_tasks WHERE user_id = :u"),
                {"u": user_a},
            )
            # The random NOINHERIT tenant role does NOT have EXECUTE on
            # get_agent_task_recovery_candidates (only appuser does).  Both
            # function calls must be denied with 42501 inside savepoints.
            for n_val in (50, 0):
                with pytest.raises(DBAPIError) as denied:
                    async with conn.begin_nested():
                        await conn.execute(
                            text("SELECT task_id FROM get_agent_task_recovery_candidates(:n)"),
                            {"n": n_val},
                        )
                assert denied.value.orig.sqlstate == "42501"

            # Use a privileged (non-tenant-role) connection to assert the
            # pg_proc-level ACL. Normal tenants cannot see these rows through
            # information_schema, so we read directly from pg_catalog.
            # Only get_agent_task_recovery_candidates is granted to appuser;
            # sync_agent_task_recovery_queue is not granted to any non-owner.
            async with engine.connect() as priv_conn:
                # Deterministic row-per-(proname, grantee, privilege) using
                # LATERAL aclexplode so the pairing is never ambiguous.
                acl_rows = (
                    await priv_conn.execute(
                        text(
                            "SELECT p.proname, "
                            "pg_get_userbyid(ac.grantee) AS grantee, "
                            "ac.privilege_type AS priv "
                            "FROM pg_proc p, "
                            "LATERAL aclexplode(p.proacl) AS ac "
                            "WHERE p.proname IN "
                            "('sync_agent_task_recovery_queue', "
                            "'get_agent_task_recovery_candidates') "
                            "AND ac.grantee <> 0 "
                            "ORDER BY p.proname, ac.grantee"
                        )
                    )
                ).all()
                acl_by_pair = {(row.proname, row.grantee): row.priv for row in acl_rows}
                assert (
                    acl_by_pair.get(("get_agent_task_recovery_candidates", "appuser")) == "EXECUTE"
                ), "appuser must have EXECUTE on get_agent_task_recovery_candidates"
                assert (
                    "sync_agent_task_recovery_queue",
                    "appuser",
                ) not in acl_by_pair, (
                    "appuser must NOT have any grant on sync_agent_task_recovery_queue"
                )

            # Prove the appuser role can discover via the SECURITY DEFINER
            # function in a fresh transaction with SET LOCAL ROLE appuser.
            async with engine.begin() as app_conn:
                await app_conn.execute(text("SET LOCAL ROLE appuser"))
                app_candidates = {
                    row.task_id
                    for row in (
                        await app_conn.execute(
                            text("SELECT task_id FROM get_agent_task_recovery_candidates(:n)"),
                            {"n": 50},
                        )
                    )
                }
            assert user_a_task_id in app_candidates, (
                "appuser-driven recovery discovery should see user_a's task"
            )

        # ── Create and commit parent fixtures for both tenants ──────────
        # binding_a / binding_b / credential_a / credential_b were already
        # created in the initial setup above; re-use them here.
        task_a = uuid.uuid4()
        task_b = uuid.uuid4()
        msg_a = uuid.uuid4()
        msg_b = uuid.uuid4()
        async with engine.begin() as conn:
            for mid, uid in ((msg_a, user_a), (msg_b, user_b)):
                await conn.execute(
                    text(
                        "INSERT INTO agent_messages (id, user_id, direction, content, "
                        "message_type, status, channel, created_at) VALUES "
                        "(:id, :user_id, 'inbound', 'probe-msg', 'text', 'received', "
                        "'wechat', now())"
                    ),
                    {"id": mid, "user_id": uid},
                )
            for tid, uid, binding_id in (
                (task_a, user_a, binding_a),
                (task_b, user_b, binding_b),
            ):
                await conn.execute(
                    text(
                        "INSERT INTO agent_tasks (id, user_id, source_message_id, "
                        "thread_id, kind, status, stage, progress_percent, summary, "
                        "context_json, result_json, error_category, "
                        "error_detail_redacted, cancel_requested_at, "
                        "resume_from_task_id, prompt_version, tool_registry_version, "
                        "schema_version, binding_id, binding_epoch, claim_owner, "
                        "claim_until, claim_generation, version, created_at, "
                        "updated_at, completed_at) VALUES "
                        "(:id, :user_id, NULL, :thread, 'wechat', 'running', "
                        "'running', NULL, 'probe', '{}'::jsonb, NULL, NULL, "
                        "NULL, NULL, NULL, 'wechat-agent.v2', "
                        "'intercraft-agent-tools.v1', 'agent-task.v1', "
                        ":binding_id, 1, NULL, now() + interval '60 seconds', "
                        "0, 1, now(), now(), NULL)"
                    ),
                    {
                        "id": tid,
                        "user_id": uid,
                        "thread": f"probe-{uid.hex[:8]}",
                        "binding_id": binding_id,
                    },
                )

                # ── Same-tenant success + cross-tenant rejection probes ────────
        # Each pair: same-tenant succeeds (all FK targets = tenant A),
        # then cross-tenant rejected where only target parent = tenant B.
        task_insert = (
            "INSERT INTO agent_tasks (id, user_id, source_message_id, "
            "thread_id, kind, status, stage, progress_percent, summary, "
            "context_json, result_json, error_category, "
            "error_detail_redacted, cancel_requested_at, "
            "resume_from_task_id, prompt_version, tool_registry_version, "
            "schema_version, binding_id, binding_epoch, claim_owner, "
            "claim_until, claim_generation, version, created_at, "
            "updated_at, completed_at) VALUES "
            "(:id, :user_id, :source_message_id, :thread, 'wechat', 'running', "
            "'running', NULL, 'probe', '{}'::jsonb, NULL, NULL, "
            "NULL, NULL, :resume_from_task_id, 'wechat-agent.v2', "
            "'intercraft-agent-tools.v1', 'agent-task.v1', "
            ":binding_id, 1, NULL, now() + interval '60 seconds', "
            "0, 1, now(), now(), NULL)"
        )
        tool_insert = (
            "INSERT INTO agent_tool_executions (id, task_id, user_id, "
            "tool_call_id, tool_name, tool_version, args_hash, "
            "args_json, idempotency_key, side_effect, atomicity, "
            "status, attempt_count, claim_generation, "
            "binding_id, binding_epoch) VALUES "
            "(:id, :task_id, :user_id, :tool_call_id, 'test_tool', 'v1', 'abc123', "
            "'{}'::jsonb, :idem_key, 'read', 'local_transaction', "
            "'proposed', 0, 0, :binding_id, 1)"
        )
        conf_insert = (
            "INSERT INTO agent_confirmations (id, user_id, task_id, "
            "tool_execution_id, args_hash, token_hash, token_hint, "
            "binding_id, binding_epoch, status, expires_at, "
            "source_message_id, version) VALUES "
            "(:id, :user_id, :task_id, :tool_execution_id, 'abc123', "
            "'\\x00000000000000000000000000000000'::bytea, 'hint1234abcd', "
            ":binding_id, 1, 'pending', now() + interval '1 hour', "
            ":source_message_id, 1)"
        )

        # Additional parents (committed)
        tool_a = uuid.uuid4()
        tool_b = uuid.uuid4()
        msg_src_a = uuid.uuid4()
        msg_src_b = uuid.uuid4()
        task_resume_target = uuid.uuid4()
        outbox_a = uuid.uuid4()
        outbox_b = uuid.uuid4()
        async with engine.begin() as conn:
            for teid, uid, tid, bid in (
                (tool_a, user_a, task_a, binding_a),
                (tool_b, user_b, task_b, binding_b),
            ):
                await conn.execute(
                    text(tool_insert),
                    {
                        "id": teid,
                        "task_id": tid,
                        "user_id": uid,
                        "tool_call_id": f"probe-tc-{teid.hex}",
                        "idem_key": f"te-{teid.hex}",
                        "binding_id": bid,
                    },
                )
            for mid, uid in ((msg_src_a, user_a), (msg_src_b, user_b)):
                await conn.execute(
                    text(
                        "INSERT INTO agent_messages (id, user_id, direction, content, "
                        "message_type, status, channel, created_at) VALUES "
                        "(:id, :user_id, 'inbound', 'src-msg', 'text', "
                        "'received', 'wechat', now())"
                    ),
                    {"id": mid, "user_id": uid},
                )
            await conn.execute(
                text(task_insert),
                {
                    "id": task_resume_target,
                    "user_id": user_a,
                    "source_message_id": None,
                    "thread": f"resume-target-{task_resume_target.hex[:8]}",
                    "resume_from_task_id": None,
                    "binding_id": binding_a,
                },
            )
            for oid, uid in ((outbox_a, user_a), (outbox_b, user_b)):
                await conn.execute(
                    text(
                        "INSERT INTO agent_command_outbox (id, user_id, command_type, "
                        "aggregate_id, idempotency_key, payload_json, status, "
                        "attempt_count) VALUES "
                        "(:id, :user_id, 'cmd', :agg_id, :idem_key, "
                        "'{}'::jsonb, 'pending', 0)"
                    ),
                    {
                        "id": oid,
                        "user_id": uid,
                        "agg_id": uuid.uuid4(),
                        "idem_key": f"obox-{oid.hex[:8]}",
                    },
                )

        # 1. agent_tasks -> agent_messages (source_message_id)
        await _assert_same_tenant_succeeds(
            engine,
            role,
            user_a,
            text(task_insert),
            {
                "id": uuid.uuid4(),
                "user_id": user_a,
                "source_message_id": msg_src_a,
                "thread": f"st-ok-src-{uuid.uuid4().hex[:8]}",
                "resume_from_task_id": None,
                "binding_id": binding_a,
            },
        )
        await _assert_cross_tenant_rejected(
            engine,
            role,
            user_a,
            text(task_insert),
            {
                "id": uuid.uuid4(),
                "user_id": user_a,
                "source_message_id": msg_src_b,
                "thread": f"st-cross-src-{uuid.uuid4().hex[:8]}",
                "resume_from_task_id": None,
                "binding_id": binding_a,
            },
            "fk_agent_tasks_source_message_user",
        )

        # 2. agent_tasks -> agent_tasks (resume_from_task_id)
        await _assert_same_tenant_succeeds(
            engine,
            role,
            user_a,
            text(task_insert),
            {
                "id": uuid.uuid4(),
                "user_id": user_a,
                "source_message_id": None,
                "thread": f"st-ok-resume-{uuid.uuid4().hex[:8]}",
                "resume_from_task_id": task_resume_target,
                "binding_id": binding_a,
            },
        )
        await _assert_cross_tenant_rejected(
            engine,
            role,
            user_a,
            text(task_insert),
            {
                "id": uuid.uuid4(),
                "user_id": user_a,
                "source_message_id": None,
                "thread": f"st-cross-resume-{uuid.uuid4().hex[:8]}",
                "resume_from_task_id": task_b,
                "binding_id": binding_a,
            },
            "fk_agent_tasks_resume_from_user",
        )

        # 3. agent_tasks -> wechat_bindings (binding_id)
        await _assert_same_tenant_succeeds(
            engine,
            role,
            user_a,
            text(task_insert),
            {
                "id": uuid.uuid4(),
                "user_id": user_a,
                "source_message_id": None,
                "thread": f"st-ok-binding-{uuid.uuid4().hex[:8]}",
                "resume_from_task_id": None,
                "binding_id": binding_a,
            },
        )
        await _assert_cross_tenant_rejected(
            engine,
            role,
            user_a,
            text(task_insert),
            {
                "id": uuid.uuid4(),
                "user_id": user_a,
                "source_message_id": None,
                "thread": f"st-cross-binding-{uuid.uuid4().hex[:8]}",
                "resume_from_task_id": None,
                "binding_id": binding_b,
            },
            "fk_agent_tasks_binding_user",
        )

        # 4-5. agent_task_events -> task / delivery_message
        await _assert_same_tenant_succeeds(
            engine,
            role,
            user_a,
            text(
                "INSERT INTO agent_task_events (id, task_id, user_id, "
                "sequence, status, stage, percent, message, "
                "delivery_message_id, occurred_at) VALUES "
                "(:id, :task_id, :user_id, 1, 'running', 'running', "
                "NULL, 'st-ok', NULL, now())"
            ),
            {"id": uuid.uuid4(), "task_id": task_a, "user_id": user_a},
        )
        await _assert_cross_tenant_rejected(
            engine,
            role,
            user_a,
            text(
                "INSERT INTO agent_task_events (id, task_id, user_id, "
                "sequence, status, stage, percent, message, "
                "delivery_message_id, occurred_at) VALUES "
                "(:id, :task_id, :user_id, 1, 'running', 'running', "
                "NULL, 'cross-task', NULL, now())"
            ),
            {"id": uuid.uuid4(), "task_id": task_b, "user_id": user_a},
            "fk_agent_task_events_task_user",
        )
        await _assert_same_tenant_succeeds(
            engine,
            role,
            user_a,
            text(
                "INSERT INTO agent_task_events (id, task_id, user_id, "
                "sequence, status, stage, percent, message, "
                "delivery_message_id, occurred_at) VALUES "
                "(:id, :task_id, :user_id, 2, 'running', 'running', "
                "NULL, 'st-ok-msg', :msg_id, now())"
            ),
            {"id": uuid.uuid4(), "task_id": task_a, "user_id": user_a, "msg_id": msg_src_a},
        )
        await _assert_cross_tenant_rejected(
            engine,
            role,
            user_a,
            text(
                "INSERT INTO agent_task_events (id, task_id, user_id, "
                "sequence, status, stage, percent, message, "
                "delivery_message_id, occurred_at) VALUES "
                "(:id, :task_id, :user_id, 2, 'running', 'running', "
                "NULL, 'cross-msg', :msg_id, now())"
            ),
            {"id": uuid.uuid4(), "task_id": task_a, "user_id": user_a, "msg_id": msg_src_b},
            "fk_agent_task_events_delivery_message_user",
        )

        # 6-7. agent_tool_executions -> task / binding
        for _suffix, tid, bid, expect_reject, cname in (
            ("task", task_a, binding_a, False, None),
            ("task", task_b, binding_a, True, "fk_agent_tool_executions_task_user"),
            ("binding", task_a, binding_a, False, None),
            ("binding", task_a, binding_b, True, "fk_agent_tool_executions_binding_user"),
        ):
            fn = _assert_cross_tenant_rejected if expect_reject else _assert_same_tenant_succeeds
            kw = {
                "id": uuid.uuid4(),
                "task_id": tid,
                "user_id": user_a,
                "tool_call_id": f"probe-tc-{uuid.uuid4().hex}",
                "idem_key": f"te-probe-{uuid.uuid4().hex}",
                "binding_id": bid,
            }
            if expect_reject:
                await fn(engine, role, user_a, text(tool_insert), kw, cname)
            else:
                await fn(engine, role, user_a, text(tool_insert), kw)

        # 8-11. agent_confirmations -> task / tool / binding / source_message
        for _label, tid, teid, bid, smid, expect_reject, cname in (
            ("task", task_a, tool_a, binding_a, None, False, None),
            ("task", task_b, tool_a, binding_a, None, True, "fk_agent_confirmations_task_user"),
            ("tool", task_a, tool_b, binding_a, None, True, "fk_agent_confirmations_tool_user"),
            (
                "binding",
                task_a,
                tool_a,
                binding_b,
                None,
                True,
                "fk_agent_confirmations_binding_user",
            ),
            ("srcmsg", task_a, tool_a, binding_a, msg_src_a, False, None),
            (
                "srcmsg",
                task_a,
                tool_a,
                binding_a,
                msg_src_b,
                True,
                "fk_agent_confirmations_source_message_user",
            ),
        ):
            fn = _assert_cross_tenant_rejected if expect_reject else _assert_same_tenant_succeeds
            kw = {
                "id": uuid.uuid4(),
                "user_id": user_a,
                "task_id": tid,
                "tool_execution_id": teid,
                "binding_id": bid,
                "source_message_id": smid,
            }
            if expect_reject:
                await fn(engine, role, user_a, text(conf_insert), kw, cname)
            else:
                await fn(engine, role, user_a, text(conf_insert), kw)

        # ── Privileged composite FK probes (non-tenant tables) ──────────
        # These relations are not writable by the tenant role, so each
        # same-tenant success and cross-tenant rejection runs in its own
        # privileged transaction. A rejected write can never poison the next
        # relation's probe.
        priv_lease = uuid.uuid4().hex[:20]
        priv_batch = uuid.uuid4()
        queue_task_a = uuid.uuid4()
        queue_task_b = uuid.uuid4()
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO wechat_consumer_leases (consumer_key, fencing_token) "
                    "VALUES (:key, 0)"
                ),
                {"key": priv_lease},
            )
            await conn.execute(
                text(
                    "INSERT INTO wechat_poll_batches (id, consumer_key, credential_id, "
                    "fencing_token, item_count) VALUES (:id, :key, :cid, 0, 0)"
                ),
                {"id": priv_batch, "key": priv_lease, "cid": credential_a},
            )
            for queue_task_id, queue_user_id, queue_binding_id in (
                (queue_task_a, user_a, binding_a),
                (queue_task_b, user_b, binding_b),
            ):
                await conn.execute(
                    text(task_insert),
                    {
                        "id": queue_task_id,
                        "user_id": queue_user_id,
                        "source_message_id": None,
                        "thread": f"queue-fk-{queue_task_id.hex[:8]}",
                        "resume_from_task_id": None,
                        "binding_id": queue_binding_id,
                    },
                )
            # task_insert initially enqueues both running tasks. Setting the
            # claims to NULL fires the recovery trigger's delete branch, so the
            # later exact-FK probe cannot be masked by the queue task_id PK.
            await conn.execute(
                text("UPDATE agent_tasks SET claim_until = NULL WHERE id IN (:task_a, :task_b)"),
                {"task_a": queue_task_a, "task_b": queue_task_b},
            )
            assert (
                await conn.scalar(
                    text(
                        "SELECT count(*) FROM agent_task_recovery_queue "
                        "WHERE task_id IN (:task_a, :task_b)"
                    ),
                    {"task_a": queue_task_a, "task_b": queue_task_b},
                )
                == 0
            )

        registration_insert = text(
            "INSERT INTO wechat_consumer_registrations (user_id, credential_id, "
            "cursor, active, updated_at) VALUES (:uid, :cid, '', true, now())"
        )
        await _assert_privileged_same_tenant_succeeds(
            engine,
            registration_insert,
            {"uid": user_a, "cid": credential_a},
        )
        await _assert_privileged_cross_tenant_rejected(
            engine,
            registration_insert,
            {"uid": user_a, "cid": credential_b},
            "fk_wechat_consumer_registrations_credential_user",
        )

        inbox_insert = text(
            "INSERT INTO wechat_inbox (id, batch_id, dedupe_key, sender_ref_hash, "
            "credential_id, binding_id, user_id, parse_status, created_at) VALUES "
            "(:id, :batch_id, :dedupe, 'priv-ref', :credential_id, :binding_id, "
            ":user_id, 'valid', now())"
        )
        await _assert_privileged_same_tenant_succeeds(
            engine,
            inbox_insert,
            {
                "id": uuid.uuid4(),
                "batch_id": priv_batch,
                "dedupe": f"priv-same-cred-{uuid.uuid4().hex}",
                "credential_id": credential_a,
                "binding_id": binding_a,
                "user_id": user_a,
            },
        )
        await _assert_privileged_cross_tenant_rejected(
            engine,
            inbox_insert,
            {
                "id": uuid.uuid4(),
                "batch_id": priv_batch,
                "dedupe": f"priv-cross-cred-{uuid.uuid4().hex}",
                "credential_id": credential_b,
                "binding_id": binding_a,
                "user_id": user_a,
            },
            "fk_wechat_inbox_credential_user",
        )
        await _assert_privileged_same_tenant_succeeds(
            engine,
            inbox_insert,
            {
                "id": uuid.uuid4(),
                "batch_id": priv_batch,
                "dedupe": f"priv-same-binding-{uuid.uuid4().hex}",
                "credential_id": credential_a,
                "binding_id": binding_a,
                "user_id": user_a,
            },
        )
        await _assert_privileged_cross_tenant_rejected(
            engine,
            inbox_insert,
            {
                "id": uuid.uuid4(),
                "batch_id": priv_batch,
                "dedupe": f"priv-cross-binding-{uuid.uuid4().hex}",
                "credential_id": credential_a,
                "binding_id": binding_b,
                "user_id": user_a,
            },
            "fk_wechat_inbox_binding_user",
        )

        message_insert = text(
            "INSERT INTO agent_messages (id, user_id, direction, content, message_type, "
            "status, channel, created_at, task_id) VALUES "
            "(:id, :user_id, 'inbound', 'priv-msg', 'text', 'received', "
            "'wechat', now(), :task_id)"
        )
        await _assert_privileged_same_tenant_succeeds(
            engine,
            message_insert,
            {"id": uuid.uuid4(), "user_id": user_a, "task_id": task_a},
        )
        await _assert_privileged_cross_tenant_rejected(
            engine,
            message_insert,
            {"id": uuid.uuid4(), "user_id": user_a, "task_id": task_b},
            "fk_agent_messages_task_user",
        )

        dispatch_insert = text(
            "INSERT INTO agent_command_dispatch_queue (outbox_id, user_id, "
            "available_at, created_at) VALUES (:outbox_id, :user_id, now(), now())"
        )
        await _assert_privileged_same_tenant_succeeds(
            engine,
            dispatch_insert,
            {"outbox_id": outbox_a, "user_id": user_a},
        )
        await _assert_privileged_cross_tenant_rejected(
            engine,
            dispatch_insert,
            {"outbox_id": outbox_b, "user_id": user_a},
            "fk_agent_command_dispatch_queue_outbox_user",
        )

        recovery_queue_insert = text(
            "INSERT INTO agent_task_recovery_queue (task_id, user_id, "
            "next_check_at, updated_at) VALUES (:task_id, :user_id, now(), now())"
        )
        await _assert_privileged_same_tenant_succeeds(
            engine,
            recovery_queue_insert,
            {"task_id": queue_task_a, "user_id": user_a},
        )
        await _assert_privileged_cross_tenant_rejected(
            engine,
            recovery_queue_insert,
            {"task_id": queue_task_b, "user_id": user_a},
            "fk_agent_task_recovery_queue_task_user",
        )

        # ── PG16 column-specific SET NULL delete probes ──────────────────
        # Verify deleting parent only nulls the FK column; user_id survives.
        async with engine.begin() as conn:
            # 1. agent_tasks(source_message_id) -> agent_messages
            d1_msg = uuid.uuid4()
            d1_task = uuid.uuid4()
            await conn.execute(
                text(
                    "INSERT INTO agent_messages (id, user_id, direction, content, "
                    "message_type, status, channel, created_at) VALUES "
                    "(:id, :user_id, 'inbound', 'd1', 'text', "
                    "'received', 'wechat', now())"
                ),
                {"id": d1_msg, "user_id": user_a},
            )
            await conn.execute(
                text(task_insert),
                {
                    "id": d1_task,
                    "user_id": user_a,
                    "source_message_id": d1_msg,
                    "thread": f"d1-{d1_task.hex[:8]}",
                    "resume_from_task_id": None,
                    "binding_id": binding_a,
                },
            )
            await conn.execute(text("DELETE FROM agent_messages WHERE id = :id"), {"id": d1_msg})
            r = (
                await conn.execute(
                    text("SELECT source_message_id, user_id FROM agent_tasks WHERE id = :id"),
                    {"id": d1_task},
                )
            ).one()
            assert r.source_message_id is None, "source_message_id should be NULL"
            assert r.user_id == user_a, "user_id must survive"

            # 2. agent_tasks(resume_from_task_id) -> agent_tasks
            d2_parent = uuid.uuid4()
            d2_child = uuid.uuid4()
            await conn.execute(
                text(task_insert),
                {
                    "id": d2_parent,
                    "user_id": user_a,
                    "source_message_id": None,
                    "thread": f"d2p-{d2_parent.hex[:8]}",
                    "resume_from_task_id": None,
                    "binding_id": binding_a,
                },
            )
            await conn.execute(
                text(task_insert),
                {
                    "id": d2_child,
                    "user_id": user_a,
                    "source_message_id": None,
                    "thread": f"d2c-{d2_child.hex[:8]}",
                    "resume_from_task_id": d2_parent,
                    "binding_id": binding_a,
                },
            )
            await conn.execute(text("DELETE FROM agent_tasks WHERE id = :id"), {"id": d2_parent})
            r = (
                await conn.execute(
                    text("SELECT resume_from_task_id, user_id FROM agent_tasks WHERE id = :id"),
                    {"id": d2_child},
                )
            ).one()
            assert r.resume_from_task_id is None, "resume_from_task_id should be NULL"
            assert r.user_id == user_a, "user_id must survive"

            # 3. agent_messages(task_id) -> agent_tasks
            d3_task = uuid.uuid4()
            d3_msg = uuid.uuid4()
            await conn.execute(
                text(task_insert),
                {
                    "id": d3_task,
                    "user_id": user_a,
                    "source_message_id": None,
                    "thread": f"d3-{d3_task.hex[:8]}",
                    "resume_from_task_id": None,
                    "binding_id": binding_a,
                },
            )
            await conn.execute(
                text(
                    "INSERT INTO agent_messages (id, user_id, direction, content, "
                    "message_type, status, channel, created_at) VALUES "
                    "(:id, :user_id, 'inbound', 'd3', 'text', "
                    "'received', 'wechat', now())"
                ),
                {"id": d3_msg, "user_id": user_a},
            )
            # Set task_id to d3_task via update (since messages are not TENANT_TABLES)
            await conn.execute(
                text("UPDATE agent_messages SET task_id = :tid WHERE id = :id"),
                {"tid": d3_task, "id": d3_msg},
            )
            await conn.execute(text("DELETE FROM agent_tasks WHERE id = :id"), {"id": d3_task})
            r = (
                await conn.execute(
                    text("SELECT task_id, user_id FROM agent_messages WHERE id = :id"),
                    {"id": d3_msg},
                )
            ).one()
            assert r.task_id is None, "task_id should be NULL"
            assert r.user_id == user_a, "user_id must survive"

            # 4. agent_task_events(delivery_message_id) -> agent_messages
            d4_msg = uuid.uuid4()
            d4_ev = uuid.uuid4()
            await conn.execute(
                text(
                    "INSERT INTO agent_messages (id, user_id, direction, content, "
                    "message_type, status, channel, created_at) VALUES "
                    "(:id, :user_id, 'inbound', 'd4', 'text', "
                    "'received', 'wechat', now())"
                ),
                {"id": d4_msg, "user_id": user_a},
            )
            await conn.execute(
                text(
                    "INSERT INTO agent_task_events (id, task_id, user_id, "
                    "sequence, status, stage, percent, message, "
                    "delivery_message_id, occurred_at) VALUES "
                    "(:id, :task_id, :user_id, 1, 'running', 'running', "
                    "NULL, 'd4', :delivery_message_id, now())"
                ),
                {"id": d4_ev, "task_id": task_a, "user_id": user_a, "delivery_message_id": d4_msg},
            )
            await conn.execute(text("DELETE FROM agent_messages WHERE id = :id"), {"id": d4_msg})
            r = (
                await conn.execute(
                    text(
                        "SELECT delivery_message_id, user_id FROM agent_task_events WHERE id = :id"
                    ),
                    {"id": d4_ev},
                )
            ).one()
            assert r.delivery_message_id is None, "delivery_message_id should be NULL"
            assert r.user_id == user_a, "user_id must survive"

            # 5. agent_confirmations(source_message_id) -> agent_messages
            d5_msg = uuid.uuid4()
            d5_cf = uuid.uuid4()
            await conn.execute(
                text(
                    "INSERT INTO agent_messages (id, user_id, direction, content, "
                    "message_type, status, channel, created_at) VALUES "
                    "(:id, :user_id, 'inbound', 'd5', 'text', "
                    "'received', 'wechat', now())"
                ),
                {"id": d5_msg, "user_id": user_a},
            )
            await conn.execute(
                text(conf_insert),
                {
                    "id": d5_cf,
                    "user_id": user_a,
                    "task_id": task_a,
                    "tool_execution_id": tool_a,
                    "binding_id": binding_a,
                    "source_message_id": d5_msg,
                },
            )
            await conn.execute(text("DELETE FROM agent_messages WHERE id = :id"), {"id": d5_msg})
            r = (
                await conn.execute(
                    text(
                        "SELECT source_message_id, user_id FROM agent_confirmations WHERE id = :id"
                    ),
                    {"id": d5_cf},
                )
            ).one()
            assert r.source_message_id is None, "source_message_id should be NULL"
            assert r.user_id == user_a, "user_id must survive"

            # 6. wechat_inbox(binding_id) -> wechat_bindings
            # Use a fresh user to avoid UNIQUE conflicts on existing bindings.
            user_c = uuid.uuid4()
            await _seed_user(conn, user_c, "del-inbox")
            d6_binding = uuid.uuid4()
            d6_cred = uuid.uuid4()
            d6_lease_key = uuid.uuid4().hex[:20]
            d6_batch = uuid.uuid4()
            d6_inbox = uuid.uuid4()
            await conn.execute(
                text(
                    "INSERT INTO wechat_bindings (id, user_id, wechat_uin, bound_at) "
                    "VALUES (:id, :user_id, :uin, now())"
                ),
                {"id": d6_binding, "user_id": user_c, "uin": f"d6-{uuid.uuid4().hex[:8]}"},
            )
            await conn.execute(
                text(
                    "INSERT INTO wechat_credentials (id, user_id, base_url, cursor, "
                    "status, last_polled_at, created_at, updated_at) VALUES "
                    "(:id, :user_id, 'https://ilinkai.weixin.qq.com', '', 'active', "
                    "NULL, now(), now())"
                ),
                {"id": d6_cred, "user_id": user_c},
            )
            await conn.execute(
                text(
                    "INSERT INTO wechat_consumer_leases (consumer_key, fencing_token) "
                    "VALUES (:key, 0)"
                ),
                {"key": d6_lease_key},
            )
            await conn.execute(
                text(
                    "INSERT INTO wechat_poll_batches (id, consumer_key, credential_id, "
                    "fencing_token, item_count) VALUES "
                    "(:id, :key, :credential_id, 0, 0)"
                ),
                {"id": d6_batch, "key": d6_lease_key, "credential_id": d6_cred},
            )
            await conn.execute(
                text(
                    "INSERT INTO wechat_inbox (id, batch_id, dedupe_key, sender_ref_hash, "
                    "credential_id, binding_id, user_id, parse_status, created_at) VALUES "
                    "(:id, :batch_id, 'd6-dedupe', 'd6-ref', "
                    ":credential_id, :binding_id, :user_id, 'valid', now())"
                ),
                {
                    "id": d6_inbox,
                    "batch_id": d6_batch,
                    "credential_id": d6_cred,
                    "binding_id": d6_binding,
                    "user_id": user_c,
                },
            )
            await conn.execute(
                text("DELETE FROM wechat_bindings WHERE id = :id"),
                {"id": d6_binding},
            )
            r = (
                await conn.execute(
                    text("SELECT binding_id, user_id FROM wechat_inbox WHERE id = :id"),
                    {"id": d6_inbox},
                )
            ).one()
            assert r.binding_id is None, "binding_id should be NULL"
            assert r.user_id == user_c, "user_id must survive"
    finally:
        await engine.dispose()


async def test_zero_skip_0057_rehearsal_leaves_clean_0055_catalog(
    database_url: str,
) -> None:
    database = f"req077_downgrade_{uuid.uuid4().hex[:12]}"
    url: str | None = None
    try:
        url, _ = await _rehearsal_database(database_url)
        engine = create_async_engine(url)
        try:
            async with engine.connect() as conn:
                assert (
                    await conn.scalar(text("SELECT version_num FROM alembic_version"))
                    == "0055_059_ai_resume"
                )
                for forbidden in (
                    "agent_task_recovery_queue",
                    "agent_tasks",
                    "agent_task_events",
                    "agent_tool_executions",
                    "agent_confirmations",
                    "agent_command_outbox",
                    "agent_command_dispatch_queue",
                    "wechat_consumer_leases",
                    "wechat_poll_batches",
                    "wechat_inbox",
                    "wechat_consumer_registrations",
                ):
                    assert (
                        await conn.scalar(
                            text("SELECT to_regclass(:table)"),
                            {"table": f"public.{forbidden}"},
                        )
                        is None
                    ), forbidden
                assert (
                    await conn.scalar(
                        text(
                            "SELECT EXISTS (SELECT 1 FROM pg_trigger "
                            "WHERE tgname = 'trg_agent_task_recovery_queue')"
                        )
                    )
                    is False
                )
                assert (
                    await conn.scalar(
                        text(
                            "SELECT EXISTS (SELECT 1 FROM pg_proc "
                            "WHERE proname = 'get_agent_task_recovery_candidates')"
                        )
                    )
                    is False
                )
                assert (
                    await conn.scalar(
                        text(
                            "SELECT EXISTS (SELECT 1 FROM pg_proc "
                            "WHERE proname = 'sync_agent_task_recovery_queue')"
                        )
                    )
                    is False
                )
                assert (
                    await conn.scalar(
                        text(
                            "SELECT EXISTS (SELECT 1 FROM pg_indexes "
                            "WHERE schemaname = 'public' "
                            "AND indexname = 'uq_agent_tasks_resume_from')"
                        )
                    )
                    is False
                )
        finally:
            await engine.dispose()

        _run_alembic(url, "upgrade", "0057_060_agent_recovery_queue")
        engine = create_async_engine(url)
        try:
            async with engine.connect() as conn:
                assert (
                    await conn.scalar(text("SELECT version_num FROM alembic_version"))
                    == "0057_060_agent_recovery_queue"
                )
                assert (
                    await conn.scalar(
                        text("SELECT to_regclass('public.agent_task_recovery_queue')")
                    )
                    == "agent_task_recovery_queue"
                )
                assert (
                    await conn.scalar(
                        text(
                            "SELECT EXISTS (SELECT 1 FROM pg_proc "
                            "WHERE proname = 'sync_agent_task_recovery_queue')"
                        )
                    )
                    is True
                )
        finally:
            await engine.dispose()
    finally:
        await _cleanup_database_state(database_url, database)


def test_alembic_chain_has_exactly_one_head_and_shipped_models_registered() -> None:
    from alembic.script import ScriptDirectory

    from app.core.db import Base
    from app.modules.resume_derive.models import ResumeDeriveRun  # noqa: F401
    from app.modules.resumes_v2.models import ResumeV2  # noqa: F401

    env_source = (_BACKEND_ROOT / "migrations" / "env.py").read_text(encoding="utf-8")
    expected_imports = (
        "from app.modules.agent.models import (",
        "from app.modules.resume_derive.models import ResumeDeriveRun",
        "from app.modules.resumes_v2.models import ResumeV2",
    )
    for expected in expected_imports:
        assert expected in env_source, expected

    for model in (
        "AgentTask",
        "AgentTaskEvent",
        "AgentTaskRecoveryQueue",
        "AgentToolExecution",
        "AgentConfirmation",
        "AgentCommandOutbox",
        "AgentCommandDispatchQueue",
        "WeChatInbox",
        "WeChatPollBatch",
        "WeChatConsumerRegistration",
    ):
        assert model in env_source, model

    # Use Alembic's ScriptDirectory so we do NOT impose a declaration style on
    # any old revision file. The graph is canonical regardless of whether each
    # revision uses ``revision: str = "..."`` or plain ``revision = "..."``.
    script_directory = ScriptDirectory(str(_BACKEND_ROOT / "migrations"))
    assert script_directory.get_heads() == ["0057_060_agent_recovery_queue"]

    rev55 = script_directory.get_revision("0055_059_ai_resume")
    rev56 = script_directory.get_revision("0056_060_wechat_agent_prod")
    rev57 = script_directory.get_revision("0057_060_agent_recovery_queue")
    assert isinstance(rev56.down_revision, str) and rev56.down_revision == rev55.revision
    assert isinstance(rev57.down_revision, str) and rev57.down_revision == rev56.revision

    task = Base.metadata.tables["agent_tasks"]
    assert isinstance(task.c.id.type, PG_UUID)
    assert isinstance(task.c.schema_version.type, Text)
    assert task.c.schema_version.nullable is False
    assert any(
        server_default is not None and "agent-task.v1" in str(server_default.arg)
        for server_default in [task.c.schema_version.server_default]
    )
    assert any(index.name == "uq_agent_tasks_resume_from" for index in task.indexes)
    assert any(constraint.name == "uq_agent_tasks_id_user" for constraint in task.constraints)
    assert "ResumeDeriveRun" in env_source
    assert "ResumeV2" in env_source

    exported = set(Base.metadata.tables)
    assert {
        "agent_tasks",
        "agent_task_events",
        "agent_tool_executions",
        "agent_confirmations",
        "agent_command_outbox",
        "agent_command_dispatch_queue",
        "agent_task_recovery_queue",
        "wechat_consumer_leases",
        "wechat_consumer_registrations",
        "wechat_poll_batches",
        "wechat_inbox",
    } <= exported
