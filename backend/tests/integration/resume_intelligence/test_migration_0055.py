"""Live PostgreSQL contract for the authoritative REQ-059 migration."""

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
    CheckConstraint,
    DateTime,
    Integer,
    Numeric,
    SmallInteger,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

pytestmark = pytest.mark.integration

_BACKEND_ROOT = Path(__file__).resolve().parents[3]
_SAFE_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_]{0,62}$")
_TEST_DATABASE = re.compile(r"^req076_(?:(?:upgrade|downgrade)_)?[0-9a-f]{12}$")
_TEST_ROLE = re.compile(r"^req076_role_[0-9a-f]{12}$")
_DDL_OPT_IN = "REQ076_ALLOW_DATABASE_DDL"
_RESERVED_DATABASES = {"postgres", "template0", "template1"}
_OWNED_DATABASES: dict[str, str] = {}
_OWNED_ROLES: dict[str, str] = {}
_PENDING_DATABASES: dict[str, tuple[str, str, str]] = {}
_DDL_TIMEOUT_SECONDS = 45.0
_ALEMBIC_TIMEOUT_SECONDS = 180.0

_NEW_TABLES = {
    "resume_fit_analyses",
    "resume_ai_suggestions",
    "resume_ai_change_sets",
    "resume_ai_feedback",
}
_TENANT_TABLES = ("resume_derive_runs", *sorted(_NEW_TABLES))


def _database_url(base_url: str, database: str) -> str:
    """Replace only the database component while preserving driver/options."""
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
    """Fail closed before any connection, terminate, or database DDL."""
    if os.environ.get(_DDL_OPT_IN) != "1":
        raise RuntimeError(f"database DDL requires explicit {_DDL_OPT_IN}=1")
    if not _TEST_DATABASE.fullmatch(database):
        raise ValueError(f"database is outside the req076 test namespace: {database!r}")

    parsed = make_url(base_url)
    base_database = parsed.database
    if not parsed.drivername.startswith("postgresql"):
        raise ValueError("REQ-059 migration tests require PostgreSQL")
    if not base_database or base_database in _RESERVED_DATABASES:
        raise ValueError("base URL must name a non-reserved isolated test database")
    if database == base_database or database in _RESERVED_DATABASES:
        raise ValueError("refusing DDL against the base or a reserved database")


def _assert_role_ddl_allowed(base_url: str, role: str) -> None:
    if os.environ.get(_DDL_OPT_IN) != "1":
        raise RuntimeError(f"role DDL requires explicit {_DDL_OPT_IN}=1")
    if not _TEST_ROLE.fullmatch(role):
        raise ValueError(f"role is outside the req076 test namespace: {role!r}")
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
    marker = f"intercraft:req076:database:{uuid.uuid4().hex}"
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
    """Mark and remove only the exact database created by this invocation."""
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
    """Drop only a generated database with matching in-memory and catalog ownership."""
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
    marker = f"intercraft:req076:role:{uuid.uuid4().hex}"
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
        pytest.fail("BLOCKED_ENVIRONMENT: REQ-059 contract requires a real PostgreSQL URL")
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
    database = f"req076_{suffix}"
    role = f"req076_role_{suffix}"
    url: str | None = None
    try:
        url = await _create_database(database_url, database)
        _run_alembic(url, "upgrade", "0055_059_ai_resume")
        await _create_test_role(database_url, role)
        engine = create_async_engine(url)
        try:
            async with engine.begin() as conn:
                await conn.execute(text(f"GRANT USAGE ON SCHEMA public TO {_identifier(role)}"))
                await conn.execute(
                    text(
                        "GRANT SELECT, INSERT, UPDATE, DELETE ON "
                        + ", ".join(_identifier(table) for table in _TENANT_TABLES)
                        + f" TO {_identifier(role)}"
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
        "email": f"req076-{label}-{user_id}@example.test",
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


async def _seed_0054_graph(conn, user_id: uuid.UUID, label: str) -> dict[str, uuid.UUID]:
    job_id = uuid.uuid4()
    resume_id = uuid.uuid4()
    run_id = uuid.uuid4()
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
            '\'{"marker": "req076"}\'::jsonb, 7, \'root\', \'{"source": "0054"}\'::jsonb)'
        ),
        {
            "id": resume_id,
            "user_id": user_id,
            "name": f"Resume {label}",
            "slug": f"req076-{label}-{resume_id.hex[:8]}",
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
    return {"job_id": job_id, "resume_id": resume_id, "run_id": run_id}


async def _seed_intelligence_graph(
    conn,
    user_id: uuid.UUID,
    graph: dict[str, uuid.UUID],
    label: str,
) -> dict[str, uuid.UUID]:
    analysis_id = uuid.uuid4()
    suggestion_id = uuid.uuid4()
    change_set_id = uuid.uuid4()
    feedback_id = uuid.uuid4()
    await conn.execute(
        text(
            "INSERT INTO resume_fit_analyses (id, user_id, resume_id, resume_version, "
            "resume_hash, mode, job_id, run_id, input_fingerprint) VALUES "
            "(:id, :user_id, :resume_id, 7, :resume_hash, 'job_fit', :job_id, "
            ":run_id, :fingerprint)"
        ),
        {
            "id": analysis_id,
            "user_id": user_id,
            "resume_id": graph["resume_id"],
            "resume_hash": f"resume-hash-{label}",
            "job_id": graph["job_id"],
            "run_id": graph["run_id"],
            "fingerprint": f"fingerprint-{label}",
        },
    )
    await conn.execute(
        text(
            "INSERT INTO resume_ai_change_sets (id, user_id, resume_id, analysis_id, "
            "base_resume_version, result_resume_version, before_hash, after_hash, "
            "preview_digest, idempotency_key) VALUES "
            "(:id, :user_id, :resume_id, :analysis_id, 7, 8, :before_hash, "
            ":after_hash, :digest, :idempotency_key)"
        ),
        {
            "id": change_set_id,
            "user_id": user_id,
            "resume_id": graph["resume_id"],
            "analysis_id": analysis_id,
            "before_hash": f"before-{label}",
            "after_hash": f"after-{label}",
            "digest": f"digest-{label}",
            "idempotency_key": f"change-{label}-{uuid.uuid4().hex}",
        },
    )
    await conn.execute(
        text(
            "INSERT INTO resume_ai_suggestions (id, user_id, analysis_id, resume_id, "
            "base_resume_version, kind, action_mode, priority, title, explanation, "
            "anchor, applied_change_set_id) VALUES "
            "(:id, :user_id, :analysis_id, :resume_id, 7, 'rewrite', 'manual', "
            "'high', :title, :explanation, '{\"path\": \"summary\"}'::jsonb, "
            ":change_set_id)"
        ),
        {
            "id": suggestion_id,
            "user_id": user_id,
            "analysis_id": analysis_id,
            "resume_id": graph["resume_id"],
            "title": f"Suggestion {label}",
            "explanation": f"Explanation {label}",
            "change_set_id": change_set_id,
        },
    )
    await conn.execute(
        text(
            "INSERT INTO resume_ai_feedback (id, user_id, analysis_id, suggestion_id, "
            "change_set_id, category, comment) VALUES "
            "(:id, :user_id, :analysis_id, :suggestion_id, :change_set_id, "
            "'helpful', :comment)"
        ),
        {
            "id": feedback_id,
            "user_id": user_id,
            "analysis_id": analysis_id,
            "suggestion_id": suggestion_id,
            "change_set_id": change_set_id,
            "comment": f"feedback-{label}",
        },
    )
    await conn.execute(
        text("UPDATE resume_derive_runs SET analysis_id = :analysis_id WHERE id = :run_id"),
        {"analysis_id": analysis_id, "run_id": graph["run_id"]},
    )
    return {
        "analysis_id": analysis_id,
        "suggestion_id": suggestion_id,
        "change_set_id": change_set_id,
        "feedback_id": feedback_id,
    }


async def _set_tenant_role(conn, role: str, user_id: uuid.UUID) -> None:
    await conn.execute(text(f"SET LOCAL ROLE {_identifier(role)}"))
    await conn.execute(
        text("SELECT set_config('app.user_id', :user_id, true)"),
        {"user_id": str(user_id)},
    )


async def _assert_tenant_statement_rejected(
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


def _postgres_error_identity(error: DBAPIError) -> tuple[str | None, str | None]:
    """Read SQLSTATE/constraint from SQLAlchemy and its asyncpg cause chain."""
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


async def _assert_nullable_parent_accepts_own(
    engine: AsyncEngine,
    role: str,
    user_id: uuid.UUID,
    clear_statement: Any,
    assign_statement: Any,
    parameters: dict[str, Any],
) -> None:
    """Prove a nullable relation accepts an own-tenant non-NULL parent."""
    async with engine.connect() as conn:
        transaction = await conn.begin()
        try:
            await _set_tenant_role(conn, role, user_id)
            cleared = await conn.execute(clear_statement, parameters)
            assigned = await conn.execute(assign_statement, parameters)
            assert cleared.rowcount == assigned.rowcount == 1
        finally:
            await transaction.rollback()


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


async def test_ddl_guards_fail_closed_without_explicit_isolated_namespace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base = "postgresql+asyncpg://user:password@localhost:5432/intercraft_test"
    monkeypatch.delenv(_DDL_OPT_IN, raising=False)
    with pytest.raises(RuntimeError, match=_DDL_OPT_IN):
        _assert_database_ddl_allowed(base, "req076_0123456789ab")
    with pytest.raises(RuntimeError, match=_DDL_OPT_IN):
        _assert_role_ddl_allowed(base, "req076_role_0123456789ab")

    monkeypatch.setenv(_DDL_OPT_IN, "1")
    for unsafe in ("intercraft_test", "postgres", "req072_0123456789ab", "req076_bad"):
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

    database = "req076_0123456789ab"
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

    uncertain_database = "req076_abcdef012345"
    _PENDING_DATABASES[uncertain_database] = (
        "intercraft:req076:database:expected",
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

    role = "req076_role_0123456789ab"
    role_connection = _FailingCommentConnection("COMMENT ON ROLE")
    role_engine = _BeginEngine(role_connection)
    monkeypatch.setattr(sys.modules[__name__], "create_async_engine", lambda *_a, **_k: role_engine)
    with pytest.raises(TimeoutError, match="COMMENT"):
        await _create_test_role(base, role)
    assert role not in _OWNED_ROLES
    assert role_engine.transaction.rolled_back is True
    assert role_engine.disposed is True
    assert role_connection.commands[0].startswith("CREATE ROLE")


async def test_fresh_upgrade_has_exact_schema_rls_and_orm_parity(
    fresh_database: tuple[str, str],
) -> None:
    url, _ = fresh_database
    engine = create_async_engine(url)
    try:
        async with engine.connect() as conn:
            server_version_num = int(await conn.scalar(text("SHOW server_version_num")))
            assert 160000 <= server_version_num < 170000
            assert await conn.scalar(text("SELECT version_num FROM alembic_version")) == (
                "0055_059_ai_resume"
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
            assert tables >= _NEW_TABLES

            expected_columns: dict[str, dict[str, tuple[str, str]]] = {
                "resume_fit_analyses": {
                    "id": ("uuid", "NO"),
                    "user_id": ("uuid", "NO"),
                    "resume_id": ("uuid", "NO"),
                    "resume_version": ("integer", "NO"),
                    "resume_hash": ("text", "NO"),
                    "mode": ("text", "NO"),
                    "job_id": ("uuid", "YES"),
                    "jd_hash": ("text", "YES"),
                    "job_snapshot": ("jsonb", "NO"),
                    "run_id": ("uuid", "YES"),
                    "status": ("text", "NO"),
                    "overall_score": ("numeric", "YES"),
                    "confidence_score": ("numeric", "YES"),
                    "confidence_band": ("text", "YES"),
                    "dimensions": ("jsonb", "NO"),
                    "requirements": ("jsonb", "NO"),
                    "summary": ("jsonb", "NO"),
                    "hard_blockers": ("jsonb", "NO"),
                    "source_manifest": ("jsonb", "NO"),
                    "quality_flags": ("jsonb", "NO"),
                    "scoring_version": ("text", "NO"),
                    "prompt_version": ("text", "NO"),
                    "schema_version": ("text", "NO"),
                    "input_fingerprint": ("text", "NO"),
                    "error_code": ("text", "YES"),
                    "error_detail_safe": ("jsonb", "NO"),
                    "created_at": ("timestamp with time zone", "NO"),
                    "finished_at": ("timestamp with time zone", "YES"),
                },
                "resume_ai_suggestions": {
                    "id": ("uuid", "NO"),
                    "user_id": ("uuid", "NO"),
                    "analysis_id": ("uuid", "NO"),
                    "resume_id": ("uuid", "NO"),
                    "base_resume_version": ("integer", "NO"),
                    "kind": ("text", "NO"),
                    "action_mode": ("text", "NO"),
                    "priority": ("text", "NO"),
                    "title": ("text", "NO"),
                    "explanation": ("text", "NO"),
                    "anchor": ("jsonb", "NO"),
                    "source_refs": ("jsonb", "NO"),
                    "requirement_refs": ("jsonb", "NO"),
                    "proposed_patch": ("jsonb", "NO"),
                    "page_impact": ("jsonb", "NO"),
                    "status": ("text", "NO"),
                    "applied_change_set_id": ("uuid", "YES"),
                    "status_reason": ("text", "YES"),
                    "created_at": ("timestamp with time zone", "NO"),
                    "updated_at": ("timestamp with time zone", "NO"),
                },
                "resume_ai_change_sets": {
                    "id": ("uuid", "NO"),
                    "user_id": ("uuid", "NO"),
                    "resume_id": ("uuid", "NO"),
                    "analysis_id": ("uuid", "YES"),
                    "base_resume_version": ("integer", "NO"),
                    "result_resume_version": ("integer", "NO"),
                    "suggestion_ids": ("jsonb", "NO"),
                    "forward_patch": ("jsonb", "NO"),
                    "inverse_patch": ("jsonb", "NO"),
                    "before_hash": ("text", "NO"),
                    "after_hash": ("text", "NO"),
                    "preview_digest": ("text", "NO"),
                    "idempotency_key": ("text", "NO"),
                    "status": ("text", "NO"),
                    "undo_of_change_set_id": ("uuid", "YES"),
                    "created_at": ("timestamp with time zone", "NO"),
                    "undone_at": ("timestamp with time zone", "YES"),
                },
                "resume_ai_feedback": {
                    "id": ("uuid", "NO"),
                    "user_id": ("uuid", "NO"),
                    "analysis_id": ("uuid", "NO"),
                    "suggestion_id": ("uuid", "YES"),
                    "change_set_id": ("uuid", "YES"),
                    "category": ("text", "NO"),
                    "comment": ("text", "YES"),
                    "created_at": ("timestamp with time zone", "NO"),
                },
            }
            for table, expected in expected_columns.items():
                columns = await _table_columns(conn, table)
                assert set(columns) == set(expected)
                assert {
                    name: (definition[0], definition[1]) for name, definition in columns.items()
                } == expected

            expected_default_fragments = {
                "resume_fit_analyses": {
                    "job_snapshot": "{}",
                    "status": "queued",
                    "dimensions": "{}",
                    "requirements": "[]",
                    "summary": "{}",
                    "hard_blockers": "[]",
                    "source_manifest": "{}",
                    "quality_flags": "{}",
                    "scoring_version": "scoring.v1",
                    "prompt_version": "resume-intelligence.v1",
                    "schema_version": "analysis.v1",
                    "error_detail_safe": "{}",
                    "created_at": "now()",
                },
                "resume_ai_suggestions": {
                    "source_refs": "[]",
                    "requirement_refs": "[]",
                    "proposed_patch": "[]",
                    "page_impact": "{}",
                    "status": "open",
                    "created_at": "now()",
                    "updated_at": "now()",
                },
                "resume_ai_change_sets": {
                    "suggestion_ids": "[]",
                    "forward_patch": "[]",
                    "inverse_patch": "[]",
                    "status": "applied",
                    "created_at": "now()",
                },
                "resume_ai_feedback": {"created_at": "now()"},
            }
            for table, defaults in expected_default_fragments.items():
                columns = await _table_columns(conn, table)
                assert {name for name, definition in columns.items() if definition[2]} == set(
                    defaults
                )
                for name, fragment in defaults.items():
                    assert fragment in (columns[name][2] or "")

            numeric_shape = {
                row.column_name: (row.numeric_precision, row.numeric_scale)
                for row in (
                    await conn.execute(
                        text(
                            "SELECT column_name, numeric_precision, numeric_scale "
                            "FROM information_schema.columns WHERE table_schema = 'public' "
                            "AND table_name = 'resume_fit_analyses' "
                            "AND column_name IN ('overall_score', 'confidence_score')"
                        )
                    )
                )
            }
            assert numeric_shape == {
                "overall_score": (5, 2),
                "confidence_score": (4, 3),
            }

            derive = await _table_columns(conn, "resume_derive_runs")
            expected_new_derive = {
                "root_hash": ("text", "YES"),
                "jd_hash": ("text", "YES"),
                "root_snapshot": ("jsonb", "NO"),
                "job_snapshot": ("jsonb", "NO"),
                "idempotency_key": ("text", "YES"),
                "request_hash": ("text", "YES"),
                "input_fingerprint": ("text", "YES"),
                "component_status": ("jsonb", "NO"),
                "analysis_id": ("uuid", "YES"),
                "prompt_version": ("text", "YES"),
                "schema_version": ("text", "YES"),
                "scoring_version": ("text", "YES"),
                "cancel_requested_at": ("timestamp with time zone", "YES"),
                "published_at": ("timestamp with time zone", "YES"),
            }
            assert {
                name: (derive[name][0], derive[name][1]) for name in expected_new_derive
            } == expected_new_derive
            assert derive["job_id"][1] == "YES"
            for name in ("root_snapshot", "job_snapshot", "component_status"):
                assert "{}" in (derive[name][2] or "")

            for table in _TENANT_TABLES:
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
                    assert " OR " not in expression.upper()

            constraints = {
                row.conname: row.definition
                for row in (
                    await conn.execute(
                        text(
                            "SELECT conname, pg_get_constraintdef(oid) AS definition "
                            "FROM pg_constraint WHERE conrelid = ANY(ARRAY["
                            "'jobs'::regclass, 'resumes_v2'::regclass, "
                            "'resume_derive_runs'::regclass, 'resume_fit_analyses'::regclass, "
                            "'resume_ai_suggestions'::regclass, 'resume_ai_change_sets'::regclass, "
                            "'resume_ai_feedback'::regclass])"
                        )
                    )
                )
            }
            for name in (
                "ck_resume_derive_runs_status",
                "ck_resume_derive_runs_pages",
                "ck_resume_fit_analyses_mode",
                "ck_resume_fit_analyses_status",
                "ck_resume_fit_analyses_score",
                "ck_resume_fit_analyses_confidence",
                "ck_resume_ai_suggestions_status",
                "ck_resume_ai_change_sets_status",
                "ck_resume_ai_feedback_category",
                "ck_resume_ai_feedback_comment_length",
            ):
                assert name in constraints
            for name in (
                "uq_jobs_user_id_id",
                "uq_resumes_v2_user_id_id",
                "uq_resume_derive_runs_user_id_id",
                "uq_resume_fit_analyses_user_id_id",
                "uq_resume_ai_suggestions_user_id_id",
                "uq_resume_ai_change_sets_user_id_id",
            ):
                assert "unique (user_id, id)" in constraints[name].lower()

            tenant_fk_fragments = {
                "fk_resume_derive_runs_job_tenant": (
                    "foreign key (user_id, job_id)",
                    "references jobs(user_id, id)",
                ),
                "fk_resume_derive_runs_root_resume_tenant": (
                    "foreign key (user_id, root_resume_id)",
                    "references resumes_v2(user_id, id)",
                ),
                "fk_resume_derive_runs_derived_resume_tenant": (
                    "foreign key (user_id, derived_resume_id)",
                    "references resumes_v2(user_id, id)",
                ),
                "fk_resume_derive_runs_analysis_tenant": (
                    "foreign key (user_id, analysis_id)",
                    "references resume_fit_analyses(user_id, id)",
                ),
                "fk_resume_fit_analyses_resume_tenant": (
                    "foreign key (user_id, resume_id)",
                    "references resumes_v2(user_id, id)",
                ),
                "fk_resume_fit_analyses_job_tenant": (
                    "foreign key (user_id, job_id)",
                    "references jobs(user_id, id)",
                ),
                "fk_resume_fit_analyses_run_tenant": (
                    "foreign key (user_id, run_id)",
                    "references resume_derive_runs(user_id, id)",
                ),
                "fk_resume_ai_suggestions_analysis_tenant": (
                    "foreign key (user_id, analysis_id)",
                    "references resume_fit_analyses(user_id, id)",
                ),
                "fk_resume_ai_suggestions_resume_tenant": (
                    "foreign key (user_id, resume_id)",
                    "references resumes_v2(user_id, id)",
                ),
                "fk_resume_ai_suggestions_change_set_tenant": (
                    "foreign key (user_id, applied_change_set_id)",
                    "references resume_ai_change_sets(user_id, id)",
                ),
                "fk_resume_ai_change_sets_resume_tenant": (
                    "foreign key (user_id, resume_id)",
                    "references resumes_v2(user_id, id)",
                ),
                "fk_resume_ai_change_sets_analysis_tenant": (
                    "foreign key (user_id, analysis_id)",
                    "references resume_fit_analyses(user_id, id)",
                ),
                "fk_resume_ai_change_sets_undo_of_tenant": (
                    "foreign key (user_id, undo_of_change_set_id)",
                    "references resume_ai_change_sets(user_id, id)",
                ),
                "fk_resume_ai_feedback_analysis_tenant": (
                    "foreign key (user_id, analysis_id)",
                    "references resume_fit_analyses(user_id, id)",
                ),
                "fk_resume_ai_feedback_suggestion_tenant": (
                    "foreign key (user_id, suggestion_id)",
                    "references resume_ai_suggestions(user_id, id)",
                ),
                "fk_resume_ai_feedback_change_set_tenant": (
                    "foreign key (user_id, change_set_id)",
                    "references resume_ai_change_sets(user_id, id)",
                ),
            }
            for name, fragments in tenant_fk_fragments.items():
                definition = constraints[name].lower()
                assert all(fragment in definition for fragment in fragments)
            check_fragments = {
                "ck_resume_derive_runs_status": (
                    "pending",
                    "queued",
                    "running",
                    "succeeded",
                    "partial_success",
                    "needs_guidance",
                    "canceling",
                    "cancelled",
                    "failed",
                    "canceled",
                ),
                "ck_resume_derive_runs_pages": ("target_page_count", "1", "2", "3"),
                "ck_resume_fit_analyses_mode": ("general", "job_fit"),
                "ck_resume_fit_analyses_status": (
                    "queued",
                    "running",
                    "complete",
                    "partial",
                    "failed",
                    "cancelled",
                ),
                "ck_resume_fit_analyses_score": (
                    "overall_score",
                    ">=",
                    "0",
                    "<=",
                    "100",
                ),
                "ck_resume_fit_analyses_confidence": (
                    "confidence_score",
                    ">=",
                    "0",
                    "<=",
                    "1",
                ),
                "ck_resume_ai_suggestions_status": (
                    "open",
                    "previewed",
                    "applied",
                    "ignored",
                    "deferred",
                    "stale",
                    "conflict",
                    "withdrawn",
                    "undone",
                ),
                "ck_resume_ai_change_sets_status": (
                    "applied",
                    "undone",
                    "superseded",
                ),
                "ck_resume_ai_feedback_category": (
                    "helpful",
                    "not_applicable",
                    "repeated",
                    "poor_wording",
                    "fact_error",
                    "other",
                ),
                "ck_resume_ai_feedback_comment_length": (
                    "comment",
                    "length",
                    "<=",
                    "1000",
                ),
            }
            for name, fragments in check_fragments.items():
                definition = constraints[name].lower()
                assert all(fragment.lower() in definition for fragment in fragments)
            derive_status = constraints["ck_resume_derive_runs_status"]
            for status in (
                "pending",
                "queued",
                "running",
                "succeeded",
                "partial_success",
                "needs_guidance",
                "canceling",
                "cancelled",
                "failed",
                "canceled",
            ):
                assert status in derive_status

            foreign_keys = {
                row.conname: (row.target, row.delete_action)
                for row in (
                    await conn.execute(
                        text(
                            "SELECT conname, confrelid::regclass::text AS target, "
                            "confdeltype::text AS delete_action FROM pg_constraint "
                            "WHERE contype = 'f' AND connamespace = 'public'::regnamespace"
                        )
                    )
                )
            }
            expected_fks = {
                "resume_derive_runs_user_id_fkey": ("users", "c"),
                "resume_derive_runs_job_id_fkey": ("jobs", "n"),
                "resume_derive_runs_root_resume_id_fkey": ("resumes_v2", "c"),
                "resume_derive_runs_derived_resume_id_fkey": ("resumes_v2", "n"),
                "fk_resume_derive_runs_analysis_id": ("resume_fit_analyses", "n"),
                "fk_resume_derive_runs_job_tenant": ("jobs", "a"),
                "fk_resume_derive_runs_root_resume_tenant": ("resumes_v2", "a"),
                "fk_resume_derive_runs_derived_resume_tenant": ("resumes_v2", "a"),
                "fk_resume_derive_runs_analysis_tenant": (
                    "resume_fit_analyses",
                    "a",
                ),
                "resume_fit_analyses_user_id_fkey": ("users", "c"),
                "resume_fit_analyses_resume_id_fkey": ("resumes_v2", "c"),
                "resume_fit_analyses_job_id_fkey": ("jobs", "n"),
                "resume_fit_analyses_run_id_fkey": ("resume_derive_runs", "n"),
                "fk_resume_fit_analyses_resume_tenant": ("resumes_v2", "a"),
                "fk_resume_fit_analyses_job_tenant": ("jobs", "a"),
                "fk_resume_fit_analyses_run_tenant": ("resume_derive_runs", "a"),
                "resume_ai_suggestions_user_id_fkey": ("users", "c"),
                "resume_ai_suggestions_analysis_id_fkey": ("resume_fit_analyses", "c"),
                "resume_ai_suggestions_resume_id_fkey": ("resumes_v2", "c"),
                "fk_resume_ai_suggestions_change_set": ("resume_ai_change_sets", "n"),
                "fk_resume_ai_suggestions_analysis_tenant": (
                    "resume_fit_analyses",
                    "a",
                ),
                "fk_resume_ai_suggestions_resume_tenant": ("resumes_v2", "a"),
                "fk_resume_ai_suggestions_change_set_tenant": (
                    "resume_ai_change_sets",
                    "a",
                ),
                "resume_ai_change_sets_user_id_fkey": ("users", "c"),
                "resume_ai_change_sets_resume_id_fkey": ("resumes_v2", "c"),
                "resume_ai_change_sets_analysis_id_fkey": ("resume_fit_analyses", "n"),
                "fk_resume_ai_change_sets_undo_of": ("resume_ai_change_sets", "n"),
                "fk_resume_ai_change_sets_resume_tenant": ("resumes_v2", "a"),
                "fk_resume_ai_change_sets_analysis_tenant": (
                    "resume_fit_analyses",
                    "a",
                ),
                "fk_resume_ai_change_sets_undo_of_tenant": (
                    "resume_ai_change_sets",
                    "a",
                ),
                "resume_ai_feedback_user_id_fkey": ("users", "c"),
                "resume_ai_feedback_analysis_id_fkey": ("resume_fit_analyses", "c"),
                "resume_ai_feedback_suggestion_id_fkey": ("resume_ai_suggestions", "n"),
                "resume_ai_feedback_change_set_id_fkey": ("resume_ai_change_sets", "n"),
                "fk_resume_ai_feedback_analysis_tenant": (
                    "resume_fit_analyses",
                    "a",
                ),
                "fk_resume_ai_feedback_suggestion_tenant": (
                    "resume_ai_suggestions",
                    "a",
                ),
                "fk_resume_ai_feedback_change_set_tenant": (
                    "resume_ai_change_sets",
                    "a",
                ),
            }
            assert {name: foreign_keys[name] for name in expected_fks} == expected_fks

            indexes = {
                row.indexname: row.indexdef.lower()
                for row in (
                    await conn.execute(
                        text(
                            "SELECT indexname, indexdef FROM pg_indexes "
                            "WHERE schemaname = 'public' AND tablename::text = "
                            "ANY(CAST(:tables AS text[]))"
                        ),
                        {"tables": list(_TENANT_TABLES)},
                    )
                )
            }
            expected_index_fragments = {
                "uq_resume_derive_runs_user_idempotency": (
                    "unique",
                    "user_id",
                    "idempotency_key",
                    "where",
                    "is not null",
                ),
                "idx_resume_derive_runs_input_fingerprint": (
                    "user_id",
                    "input_fingerprint",
                ),
                "idx_resume_fit_analyses_resume_history": (
                    "user_id",
                    "resume_id",
                    "created_at",
                ),
                "idx_resume_fit_analyses_run": ("run_id",),
                "idx_resume_ai_suggestions_analysis_status": ("analysis_id", "status"),
                "idx_resume_ai_suggestions_resume": ("user_id", "resume_id"),
                "uq_resume_ai_change_sets_result_version": (
                    "unique",
                    "resume_id",
                    "result_resume_version",
                ),
                "uq_resume_ai_change_sets_idempotency": (
                    "unique",
                    "user_id",
                    "idempotency_key",
                ),
                "idx_resume_ai_change_sets_history": (
                    "user_id",
                    "resume_id",
                    "created_at",
                ),
                "idx_resume_ai_feedback_analysis": ("user_id", "analysis_id", "created_at"),
            }
            for name, fragments in expected_index_fragments.items():
                assert name in indexes
                assert all(fragment in indexes[name] for fragment in fragments)

            from app.core.db import Base
            from app.modules.jobs.models import Job  # noqa: F401
            from app.modules.resume_derive.models import ResumeDeriveRun  # noqa: F401
            from app.modules.resume_intelligence.models import (  # noqa: F401
                ResumeAIChangeSet,
                ResumeAIFeedback,
                ResumeAISuggestion,
                ResumeFitAnalysis,
            )
            from app.modules.resumes_v2.models import ResumeV2  # noqa: F401

            for table in _NEW_TABLES | {"resume_derive_runs"}:
                model_table = Base.metadata.tables[table]
                model_columns = model_table.columns
                live_columns = await _table_columns(conn, table)
                assert {column.name for column in model_columns} == set(live_columns)
                assert {column.name: column.nullable for column in model_columns} == {
                    name: definition[1] == "YES" for name, definition in live_columns.items()
                }
                catalog_columns = await _table_catalog_columns(conn, table)
                assert set(catalog_columns) == {column.name for column in model_columns}
                model_types = {
                    column.name: _normalize_catalog_sql(
                        str(column.type.compile(dialect=postgresql.dialect()))
                    )
                    for column in model_columns
                }
                assert model_types == {
                    name: _normalize_catalog_sql(definition[0])
                    for name, definition in catalog_columns.items()
                }
                model_defaults = {
                    column.name: _normalize_catalog_sql(
                        str(column.server_default.arg.compile(dialect=postgresql.dialect()))
                        if hasattr(column.server_default.arg, "compile")
                        else str(column.server_default.arg)
                    )
                    if column.server_default is not None
                    else None
                    for column in model_columns
                }
                assert model_defaults == {
                    name: _normalize_catalog_sql(definition[1])
                    for name, definition in catalog_columns.items()
                }

                model_foreign_keys = {
                    constraint.name for constraint in model_table.foreign_key_constraints
                }
                live_foreign_keys = set(
                    (
                        await conn.execute(
                            text(
                                "SELECT conname FROM pg_constraint WHERE contype = 'f' "
                                "AND conrelid = to_regclass(:table)"
                            ),
                            {"table": f"public.{table}"},
                        )
                    ).scalars()
                )
                assert model_foreign_keys == live_foreign_keys

                model_indexes = {index.name for index in model_table.indexes}
                live_indexes = set(
                    (
                        await conn.execute(
                            text(
                                "SELECT index_class.relname FROM pg_index "
                                "JOIN pg_class AS index_class "
                                "ON index_class.oid = pg_index.indexrelid "
                                "WHERE pg_index.indrelid = to_regclass(:table) "
                                "AND NOT EXISTS (SELECT 1 FROM pg_constraint "
                                "WHERE conindid = pg_index.indexrelid)"
                            ),
                            {"table": f"public.{table}"},
                        )
                    ).scalars()
                )
                assert model_indexes == live_indexes

                model_uniques = {
                    constraint.name
                    for constraint in model_table.constraints
                    if isinstance(constraint, UniqueConstraint)
                }
                live_uniques = set(
                    (
                        await conn.execute(
                            text(
                                "SELECT conname FROM pg_constraint WHERE contype = 'u' "
                                "AND conrelid = to_regclass(:table)"
                            ),
                            {"table": f"public.{table}"},
                        )
                    ).scalars()
                )
                assert model_uniques == live_uniques

                model_checks = {
                    constraint.name: str(constraint.sqltext).lower()
                    for constraint in model_table.constraints
                    if isinstance(constraint, CheckConstraint)
                }
                live_checks = {
                    row.conname: row.definition.lower()
                    for row in (
                        await conn.execute(
                            text(
                                "SELECT conname, pg_get_constraintdef(oid) AS definition "
                                "FROM pg_constraint WHERE contype = 'c' "
                                "AND conrelid = to_regclass(:table)"
                            ),
                            {"table": f"public.{table}"},
                        )
                    )
                }
                assert set(model_checks) == set(live_checks)
                for name, model_definition in model_checks.items():
                    live_definition = live_checks[name]
                    assert all(
                        fragment.lower() in model_definition and fragment.lower() in live_definition
                        for fragment in check_fragments[name]
                    )
                    assert set(re.findall(r"'([^']*)'", model_definition)) == set(
                        re.findall(r"'([^']*)'", live_definition)
                    )

            for parent, unique_name in (
                ("jobs", "uq_jobs_user_id_id"),
                ("resumes_v2", "uq_resumes_v2_user_id_id"),
            ):
                model_uniques = {
                    constraint.name
                    for constraint in Base.metadata.tables[parent].constraints
                    if isinstance(constraint, UniqueConstraint)
                }
                assert unique_name in model_uniques
                assert unique_name in constraints
    finally:
        await engine.dispose()


async def test_genuine_0054_upgrade_preserves_users_resumes_jobs_and_runs(
    database_url: str,
) -> None:
    database = f"req076_upgrade_{uuid.uuid4().hex[:12]}"
    url: str | None = None
    user_id = uuid.uuid4()
    try:
        url = await _create_database(database_url, database)
        _run_alembic(url, "upgrade", "0054_account_notifications")
        engine = create_async_engine(url)
        try:
            async with engine.begin() as conn:
                user = await _seed_user(conn, user_id, "preserve")
                graph = await _seed_0054_graph(conn, user_id, "preserve")
                notification_id = uuid.uuid4()
                await conn.execute(
                    text(
                        "INSERT INTO notifications (id, user_id, type, title, message) "
                        "VALUES (:id, :user_id, 'req076', 'preserve', '0054-row')"
                    ),
                    {"id": notification_id, "user_id": user_id},
                )
        finally:
            await engine.dispose()

        _run_alembic(url, "upgrade", "0055_059_ai_resume")
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
                    user["id"],
                    user["email"],
                    user["email_sha256"],
                    user["password_hash"],
                )
                assert (
                    await conn.execute(
                        text("SELECT company, position, notes_md FROM jobs WHERE id = :id"),
                        {"id": graph["job_id"]},
                    )
                ).one() == ("Company preserve", "Position preserve", "preserve-job-preserve")
                assert (
                    await conn.execute(
                        text(
                            "SELECT name, version, data, derive_meta FROM resumes_v2 WHERE id = :id"
                        ),
                        {"id": graph["resume_id"]},
                    )
                ).one() == (
                    "Resume preserve",
                    7,
                    {"marker": "req076"},
                    {"source": "0054"},
                )
                run = (
                    await conn.execute(
                        text(
                            "SELECT job_id, root_resume_id, root_version, template_id, status, "
                            "calibrate_round, progress_pct, artifacts, root_snapshot, job_snapshot, "
                            "component_status FROM resume_derive_runs WHERE id = :id"
                        ),
                        {"id": graph["run_id"]},
                    )
                ).one()
                assert tuple(run[:8]) == (
                    graph["job_id"],
                    graph["resume_id"],
                    7,
                    "template-preserve",
                    "pending",
                    3,
                    11,
                    {"preserve": True},
                )
                assert tuple(run[8:]) == ({}, {}, {})
                assert (
                    await conn.scalar(
                        text("SELECT count(*) FROM notifications WHERE id = :id"),
                        {"id": notification_id},
                    )
                    == 1
                )
        finally:
            await engine.dispose()
    finally:
        await _cleanup_database_state(database_url, database)


async def test_non_bypass_role_enforces_two_tenant_crud(
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
            graph_a = await _seed_0054_graph(conn, user_a, "tenant-a")
            graph_b = await _seed_0054_graph(conn, user_b, "tenant-b")
            ai_a = await _seed_intelligence_graph(conn, user_a, graph_a, "tenant-a")
            ai_b = await _seed_intelligence_graph(conn, user_b, graph_b, "tenant-b")

        async with engine.connect() as conn:
            transaction = await conn.begin()
            try:
                await conn.execute(text(f"SET LOCAL ROLE {_identifier(role)}"))
                assert await conn.scalar(text("SELECT current_setting('app.user_id', true)")) in (
                    None,
                    "",
                )
                for table in _TENANT_TABLES:
                    assert (
                        await conn.scalar(text(f"SELECT count(*) FROM {_identifier(table)}")) == 0
                    )
                with pytest.raises(DBAPIError):
                    await conn.execute(
                        text(
                            "INSERT INTO resume_ai_feedback "
                            "(id, user_id, analysis_id, category) "
                            "VALUES (:id, :user_id, :analysis_id, 'helpful')"
                        ),
                        {
                            "id": uuid.uuid4(),
                            "user_id": user_a,
                            "analysis_id": ai_a["analysis_id"],
                        },
                    )
            finally:
                await transaction.rollback()

        async with engine.begin() as conn:
            await _set_tenant_role(conn, role, user_a)
            role_flags = (
                await conn.execute(
                    text("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user")
                )
            ).one()
            assert tuple(role_flags) == (False, False)
            for table in _TENANT_TABLES:
                assert await conn.scalar(text(f"SELECT count(*) FROM {_identifier(table)}")) == 1

            result = await conn.execute(
                text("UPDATE resume_fit_analyses SET status = 'running' WHERE id = :id"),
                {"id": ai_a["analysis_id"]},
            )
            assert result.rowcount == 1
            result = await conn.execute(
                text("UPDATE resume_fit_analyses SET status = 'running' WHERE id = :id"),
                {"id": ai_b["analysis_id"]},
            )
            assert result.rowcount == 0

            own_feedback = uuid.uuid4()
            await conn.execute(
                text(
                    "INSERT INTO resume_ai_feedback (id, user_id, analysis_id, category) "
                    "VALUES (:id, :user_id, :analysis_id, 'helpful')"
                ),
                {"id": own_feedback, "user_id": user_a, "analysis_id": ai_a["analysis_id"]},
            )
            result = await conn.execute(
                text("DELETE FROM resume_ai_feedback WHERE id = :id"),
                {"id": own_feedback},
            )
            assert result.rowcount == 1

        async with engine.connect() as conn:
            transaction = await conn.begin()
            try:
                await _set_tenant_role(conn, role, user_a)
                with pytest.raises(DBAPIError):
                    await conn.execute(
                        text(
                            "INSERT INTO resume_ai_feedback "
                            "(id, user_id, analysis_id, category) "
                            "VALUES (:id, :user_id, :analysis_id, 'helpful')"
                        ),
                        {
                            "id": uuid.uuid4(),
                            "user_id": user_b,
                            "analysis_id": ai_b["analysis_id"],
                        },
                    )
            finally:
                await transaction.rollback()

        # RLS on the child row is not enough: every parent reference must also
        # belong to the same tenant. Isolate each relationship so a different
        # valid guard cannot mask a missing composite tenant foreign key.
        for table, column, child_id, own_parent_id in (
            ("resume_derive_runs", "job_id", graph_a["run_id"], graph_a["job_id"]),
            (
                "resume_derive_runs",
                "derived_resume_id",
                graph_a["run_id"],
                graph_a["resume_id"],
            ),
            (
                "resume_derive_runs",
                "analysis_id",
                graph_a["run_id"],
                ai_a["analysis_id"],
            ),
            ("resume_fit_analyses", "job_id", ai_a["analysis_id"], graph_a["job_id"]),
            ("resume_fit_analyses", "run_id", ai_a["analysis_id"], graph_a["run_id"]),
            (
                "resume_ai_suggestions",
                "applied_change_set_id",
                ai_a["suggestion_id"],
                ai_a["change_set_id"],
            ),
            (
                "resume_ai_change_sets",
                "analysis_id",
                ai_a["change_set_id"],
                ai_a["analysis_id"],
            ),
            (
                "resume_ai_change_sets",
                "undo_of_change_set_id",
                ai_a["change_set_id"],
                ai_a["change_set_id"],
            ),
            (
                "resume_ai_feedback",
                "suggestion_id",
                ai_a["feedback_id"],
                ai_a["suggestion_id"],
            ),
            (
                "resume_ai_feedback",
                "change_set_id",
                ai_a["feedback_id"],
                ai_a["change_set_id"],
            ),
        ):
            await _assert_nullable_parent_accepts_own(
                engine,
                role,
                user_a,
                text(
                    f"UPDATE {_identifier(table)} SET {_identifier(column)} = NULL "
                    "WHERE id = :child_id"
                ),
                text(
                    f"UPDATE {_identifier(table)} SET {_identifier(column)} = :parent_id "
                    "WHERE id = :child_id"
                ),
                {"child_id": child_id, "parent_id": own_parent_id},
            )

        for column, cross_tenant_id, expected_constraint in (
            ("job_id", graph_b["job_id"], "fk_resume_derive_runs_job_tenant"),
            (
                "root_resume_id",
                graph_b["resume_id"],
                "fk_resume_derive_runs_root_resume_tenant",
            ),
            (
                "derived_resume_id",
                graph_b["resume_id"],
                "fk_resume_derive_runs_derived_resume_tenant",
            ),
            (
                "analysis_id",
                ai_b["analysis_id"],
                "fk_resume_derive_runs_analysis_tenant",
            ),
        ):
            await _assert_tenant_statement_rejected(
                engine,
                role,
                user_a,
                text(
                    f"UPDATE resume_derive_runs SET {_identifier(column)} = :parent_id "
                    "WHERE id = :run_id"
                ),
                {"parent_id": cross_tenant_id, "run_id": graph_a["run_id"]},
                expected_constraint,
            )

        for resume_id, job_id, run_id, expected_constraint in (
            (
                graph_b["resume_id"],
                graph_a["job_id"],
                graph_a["run_id"],
                "fk_resume_fit_analyses_resume_tenant",
            ),
            (
                graph_a["resume_id"],
                graph_b["job_id"],
                graph_a["run_id"],
                "fk_resume_fit_analyses_job_tenant",
            ),
            (
                graph_a["resume_id"],
                graph_a["job_id"],
                graph_b["run_id"],
                "fk_resume_fit_analyses_run_tenant",
            ),
        ):
            await _assert_tenant_statement_rejected(
                engine,
                role,
                user_a,
                text(
                    "INSERT INTO resume_fit_analyses "
                    "(id, user_id, resume_id, resume_version, resume_hash, mode, job_id, "
                    "run_id, input_fingerprint) VALUES "
                    "(:id, :user_id, :resume_id, 7, 'cross-parent', 'job_fit', :job_id, "
                    ":run_id, :fingerprint)"
                ),
                {
                    "id": uuid.uuid4(),
                    "user_id": user_a,
                    "resume_id": resume_id,
                    "job_id": job_id,
                    "run_id": run_id,
                    "fingerprint": f"cross-fit-{uuid.uuid4()}",
                },
                expected_constraint,
            )

        for analysis_id, resume_id, expected_constraint in (
            (
                ai_b["analysis_id"],
                graph_a["resume_id"],
                "fk_resume_ai_suggestions_analysis_tenant",
            ),
            (
                ai_a["analysis_id"],
                graph_b["resume_id"],
                "fk_resume_ai_suggestions_resume_tenant",
            ),
        ):
            await _assert_tenant_statement_rejected(
                engine,
                role,
                user_a,
                text(
                    "INSERT INTO resume_ai_suggestions "
                    "(id, user_id, analysis_id, resume_id, base_resume_version, kind, "
                    "action_mode, priority, title, explanation, anchor) VALUES "
                    "(:id, :user_id, :analysis_id, :resume_id, 7, 'rewrite', "
                    "'manual', 'high', 'cross-parent', 'must fail', '{}'::jsonb)"
                ),
                {
                    "id": uuid.uuid4(),
                    "user_id": user_a,
                    "analysis_id": analysis_id,
                    "resume_id": resume_id,
                },
                expected_constraint,
            )

        for resume_id, analysis_id, expected_constraint in (
            (
                graph_b["resume_id"],
                ai_a["analysis_id"],
                "fk_resume_ai_change_sets_resume_tenant",
            ),
            (
                graph_a["resume_id"],
                ai_b["analysis_id"],
                "fk_resume_ai_change_sets_analysis_tenant",
            ),
        ):
            await _assert_tenant_statement_rejected(
                engine,
                role,
                user_a,
                text(
                    "INSERT INTO resume_ai_change_sets "
                    "(id, user_id, resume_id, analysis_id, base_resume_version, "
                    "result_resume_version, before_hash, after_hash, preview_digest, "
                    "idempotency_key) VALUES "
                    "(:id, :user_id, :resume_id, :analysis_id, 7, 999, 'before', 'after', "
                    "'cross-parent', :idempotency_key)"
                ),
                {
                    "id": uuid.uuid4(),
                    "user_id": user_a,
                    "resume_id": resume_id,
                    "analysis_id": analysis_id,
                    "idempotency_key": f"cross-{uuid.uuid4()}",
                },
                expected_constraint,
            )

        for analysis_id, suggestion_id, change_set_id, expected_constraint in (
            (
                ai_b["analysis_id"],
                None,
                None,
                "fk_resume_ai_feedback_analysis_tenant",
            ),
            (
                ai_a["analysis_id"],
                ai_b["suggestion_id"],
                None,
                "fk_resume_ai_feedback_suggestion_tenant",
            ),
            (
                ai_a["analysis_id"],
                None,
                ai_b["change_set_id"],
                "fk_resume_ai_feedback_change_set_tenant",
            ),
        ):
            await _assert_tenant_statement_rejected(
                engine,
                role,
                user_a,
                text(
                    "INSERT INTO resume_ai_feedback "
                    "(id, user_id, analysis_id, suggestion_id, change_set_id, category) "
                    "VALUES (:id, :user_id, :analysis_id, :suggestion_id, "
                    ":change_set_id, 'helpful')"
                ),
                {
                    "id": uuid.uuid4(),
                    "user_id": user_a,
                    "analysis_id": analysis_id,
                    "suggestion_id": suggestion_id,
                    "change_set_id": change_set_id,
                },
                expected_constraint,
            )

        await _assert_tenant_statement_rejected(
            engine,
            role,
            user_a,
            text(
                "UPDATE resume_ai_suggestions "
                "SET applied_change_set_id = :change_set_id WHERE id = :suggestion_id"
            ),
            {
                "change_set_id": ai_b["change_set_id"],
                "suggestion_id": ai_a["suggestion_id"],
            },
            "fk_resume_ai_suggestions_change_set_tenant",
        )
        await _assert_tenant_statement_rejected(
            engine,
            role,
            user_a,
            text(
                "UPDATE resume_ai_change_sets SET undo_of_change_set_id = :undo_id "
                "WHERE id = :change_set_id"
            ),
            {
                "undo_id": ai_b["change_set_id"],
                "change_set_id": ai_a["change_set_id"],
            },
            "fk_resume_ai_change_sets_undo_of_tenant",
        )
    finally:
        await engine.dispose()


async def test_single_column_delete_actions_coexist_with_tenant_guards(
    fresh_database: tuple[str, str],
) -> None:
    """Execute every retained CASCADE/SET NULL path, including all cycles."""
    url, _ = fresh_database
    engine = create_async_engine(url)

    async def seed_case(conn, label: str):
        user_id = uuid.uuid4()
        await _seed_user(conn, user_id, label)
        graph = await _seed_0054_graph(conn, user_id, label)
        ai = await _seed_intelligence_graph(conn, user_id, graph, label)
        return user_id, graph, ai

    try:
        async with engine.connect() as conn:
            transaction = await conn.begin()
            try:
                _, graph, ai = await seed_case(conn, "delete-job")
                await conn.execute(text("DELETE FROM jobs WHERE id = :id"), {"id": graph["job_id"]})
                assert (
                    await conn.scalar(
                        text("SELECT job_id FROM resume_derive_runs WHERE id = :id"),
                        {"id": graph["run_id"]},
                    )
                    is None
                )
                assert (
                    await conn.scalar(
                        text("SELECT job_id FROM resume_fit_analyses WHERE id = :id"),
                        {"id": ai["analysis_id"]},
                    )
                    is None
                )

                _, graph, ai = await seed_case(conn, "delete-run")
                await conn.execute(
                    text("DELETE FROM resume_derive_runs WHERE id = :id"),
                    {"id": graph["run_id"]},
                )
                assert (
                    await conn.scalar(
                        text("SELECT run_id FROM resume_fit_analyses WHERE id = :id"),
                        {"id": ai["analysis_id"]},
                    )
                    is None
                )

                _, graph, ai = await seed_case(conn, "delete-analysis")
                await conn.execute(
                    text("DELETE FROM resume_fit_analyses WHERE id = :id"),
                    {"id": ai["analysis_id"]},
                )
                assert (
                    await conn.scalar(
                        text("SELECT analysis_id FROM resume_derive_runs WHERE id = :id"),
                        {"id": graph["run_id"]},
                    )
                    is None
                )
                assert (
                    await conn.scalar(
                        text("SELECT analysis_id FROM resume_ai_change_sets WHERE id = :id"),
                        {"id": ai["change_set_id"]},
                    )
                    is None
                )
                assert (
                    await conn.scalar(
                        text("SELECT count(*) FROM resume_ai_suggestions WHERE id = :id"),
                        {"id": ai["suggestion_id"]},
                    )
                    == 0
                )
                assert (
                    await conn.scalar(
                        text("SELECT count(*) FROM resume_ai_feedback WHERE id = :id"),
                        {"id": ai["feedback_id"]},
                    )
                    == 0
                )

                _, _, ai = await seed_case(conn, "delete-change")
                await conn.execute(
                    text("DELETE FROM resume_ai_change_sets WHERE id = :id"),
                    {"id": ai["change_set_id"]},
                )
                assert (
                    await conn.scalar(
                        text(
                            "SELECT applied_change_set_id FROM resume_ai_suggestions WHERE id = :id"
                        ),
                        {"id": ai["suggestion_id"]},
                    )
                    is None
                )
                assert (
                    await conn.scalar(
                        text("SELECT change_set_id FROM resume_ai_feedback WHERE id = :id"),
                        {"id": ai["feedback_id"]},
                    )
                    is None
                )

                _, _, ai = await seed_case(conn, "delete-suggestion")
                await conn.execute(
                    text("DELETE FROM resume_ai_suggestions WHERE id = :id"),
                    {"id": ai["suggestion_id"]},
                )
                assert (
                    await conn.scalar(
                        text("SELECT suggestion_id FROM resume_ai_feedback WHERE id = :id"),
                        {"id": ai["feedback_id"]},
                    )
                    is None
                )

                user_id, _, ai = await seed_case(conn, "delete-suggestion-resume")
                independent_resume_id = uuid.uuid4()
                independent_suggestion_id = uuid.uuid4()
                await conn.execute(
                    text(
                        "INSERT INTO resumes_v2 (id, user_id, name, slug, tags, is_public, "
                        "is_locked, data, version, resume_kind, derive_meta) VALUES "
                        "(:id, :user_id, 'Independent', :slug, ARRAY[]::text[], false, "
                        "false, '{}'::jsonb, 1, 'standard', '{}'::jsonb)"
                    ),
                    {
                        "id": independent_resume_id,
                        "user_id": user_id,
                        "slug": f"req076-independent-{independent_resume_id.hex[:8]}",
                    },
                )
                await conn.execute(
                    text(
                        "INSERT INTO resume_ai_suggestions "
                        "(id, user_id, analysis_id, resume_id, base_resume_version, kind, "
                        "action_mode, priority, title, explanation, anchor) VALUES "
                        "(:id, :user_id, :analysis_id, :resume_id, 1, 'rewrite', "
                        "'manual', 'high', 'independent', 'delete contract', '{}'::jsonb)"
                    ),
                    {
                        "id": independent_suggestion_id,
                        "user_id": user_id,
                        "analysis_id": ai["analysis_id"],
                        "resume_id": independent_resume_id,
                    },
                )
                await conn.execute(
                    text("DELETE FROM resumes_v2 WHERE id = :id"),
                    {"id": independent_resume_id},
                )
                assert (
                    await conn.scalar(
                        text("SELECT count(*) FROM resume_ai_suggestions WHERE id = :id"),
                        {"id": independent_suggestion_id},
                    )
                    == 0
                )
                assert (
                    await conn.scalar(
                        text("SELECT count(*) FROM resume_fit_analyses WHERE id = :id"),
                        {"id": ai["analysis_id"]},
                    )
                    == 1
                )

                user_id, graph, _ = await seed_case(conn, "delete-resume")
                await conn.execute(
                    text("DELETE FROM resumes_v2 WHERE id = :id"),
                    {"id": graph["resume_id"]},
                )
                for table in _TENANT_TABLES:
                    assert (
                        await conn.scalar(
                            text(
                                f"SELECT count(*) FROM {_identifier(table)} "
                                "WHERE user_id = :user_id"
                            ),
                            {"user_id": user_id},
                        )
                        == 0
                    )

                user_id, graph, _ = await seed_case(conn, "delete-derived-resume")
                derived_resume_id = uuid.uuid4()
                await conn.execute(
                    text(
                        "INSERT INTO resumes_v2 (id, user_id, name, slug, tags, is_public, "
                        "is_locked, data, version, resume_kind, root_resume_id, job_id, "
                        "root_version_at_derive, target_page_count, derive_meta) VALUES "
                        "(:id, :user_id, 'Derived', :slug, ARRAY[]::text[], false, false, "
                        "'{}'::jsonb, 8, 'derived', :root_id, :job_id, 7, 2, '{}'::jsonb)"
                    ),
                    {
                        "id": derived_resume_id,
                        "user_id": user_id,
                        "slug": f"req076-derived-{derived_resume_id.hex[:8]}",
                        "root_id": graph["resume_id"],
                        "job_id": graph["job_id"],
                    },
                )
                await conn.execute(
                    text(
                        "UPDATE resume_derive_runs SET derived_resume_id = :resume_id "
                        "WHERE id = :run_id"
                    ),
                    {"resume_id": derived_resume_id, "run_id": graph["run_id"]},
                )
                await conn.execute(
                    text("DELETE FROM resumes_v2 WHERE id = :id"),
                    {"id": derived_resume_id},
                )
                assert (
                    await conn.scalar(
                        text("SELECT derived_resume_id FROM resume_derive_runs WHERE id = :id"),
                        {"id": graph["run_id"]},
                    )
                    is None
                )

                user_id, graph, ai = await seed_case(conn, "delete-undo-target")
                undo_id = uuid.uuid4()
                await conn.execute(
                    text(
                        "INSERT INTO resume_ai_change_sets "
                        "(id, user_id, resume_id, analysis_id, base_resume_version, "
                        "result_resume_version, before_hash, after_hash, preview_digest, "
                        "idempotency_key, undo_of_change_set_id) VALUES "
                        "(:id, :user_id, :resume_id, :analysis_id, 8, 9, 'before-undo', "
                        "'after-undo', 'undo-digest', :idempotency_key, :undo_id)"
                    ),
                    {
                        "id": undo_id,
                        "user_id": user_id,
                        "resume_id": graph["resume_id"],
                        "analysis_id": ai["analysis_id"],
                        "idempotency_key": f"undo-{uuid.uuid4()}",
                        "undo_id": ai["change_set_id"],
                    },
                )
                await conn.execute(
                    text("DELETE FROM resume_ai_change_sets WHERE id = :id"),
                    {"id": ai["change_set_id"]},
                )
                assert (
                    await conn.scalar(
                        text(
                            "SELECT undo_of_change_set_id FROM resume_ai_change_sets WHERE id = :id"
                        ),
                        {"id": undo_id},
                    )
                    is None
                )

                user_id, _, _ = await seed_case(conn, "delete-user")
                await conn.execute(text("DELETE FROM users WHERE id = :id"), {"id": user_id})
                for table in _TENANT_TABLES:
                    assert (
                        await conn.scalar(
                            text(
                                f"SELECT count(*) FROM {_identifier(table)} "
                                "WHERE user_id = :user_id"
                            ),
                            {"user_id": user_id},
                        )
                        == 0
                    )
            finally:
                await transaction.rollback()
    finally:
        await engine.dispose()


async def test_downgrade_restores_true_0054_then_reupgrades(database_url: str) -> None:
    database = f"req076_downgrade_{uuid.uuid4().hex[:12]}"
    url: str | None = None
    user_id = uuid.uuid4()
    try:
        url = await _create_database(database_url, database)
        _run_alembic(url, "upgrade", "0054_account_notifications")
        engine = create_async_engine(url)
        try:
            async with engine.begin() as conn:
                await _seed_user(conn, user_id, "downgrade")
                graph = await _seed_0054_graph(conn, user_id, "downgrade")
        finally:
            await engine.dispose()
        _run_alembic(url, "upgrade", "0055_059_ai_resume")
        _run_alembic(url, "downgrade", "0054_account_notifications")

        engine = create_async_engine(url)
        try:
            async with engine.connect() as conn:
                assert await conn.scalar(text("SELECT version_num FROM alembic_version")) == (
                    "0054_account_notifications"
                )
                for table in _NEW_TABLES:
                    assert (
                        await conn.scalar(
                            text("SELECT to_regclass(:table)"), {"table": f"public.{table}"}
                        )
                        is None
                    )
                derive = await _table_columns(conn, "resume_derive_runs")
                assert set(derive) == {
                    "id",
                    "user_id",
                    "job_id",
                    "root_resume_id",
                    "root_version",
                    "target_page_count",
                    "template_id",
                    "derived_resume_id",
                    "status",
                    "phase",
                    "calibrate_round",
                    "progress_pct",
                    "error_code",
                    "error_message",
                    "artifacts",
                    "created_at",
                    "updated_at",
                    "finished_at",
                }
                assert derive["job_id"][1] == "NO"
                rls = (
                    await conn.execute(
                        text(
                            "SELECT relrowsecurity, relforcerowsecurity FROM pg_class "
                            "WHERE oid = 'resume_derive_runs'::regclass"
                        )
                    )
                ).one()
                assert tuple(rls) == (False, False)
                assert (
                    await conn.scalar(
                        text(
                            "SELECT count(*) FROM pg_policies WHERE schemaname = 'public' "
                            "AND tablename = 'resume_derive_runs'"
                        )
                    )
                    == 0
                )
                job_fk = (
                    await conn.execute(
                        text(
                            "SELECT confrelid::regclass::text, confdeltype::text "
                            "FROM pg_constraint WHERE conname = 'resume_derive_runs_job_id_fkey'"
                        )
                    )
                ).one()
                assert tuple(job_fk) == ("jobs", "c")
                assert (
                    await conn.scalar(
                        text("SELECT count(*) FROM resume_derive_runs WHERE id = :id"),
                        {"id": graph["run_id"]},
                    )
                    == 1
                )
        finally:
            await engine.dispose()

        _run_alembic(url, "upgrade", "0055_059_ai_resume")
        engine = create_async_engine(url)
        try:
            async with engine.connect() as conn:
                assert await conn.scalar(text("SELECT version_num FROM alembic_version")) == (
                    "0055_059_ai_resume"
                )
                assert (
                    await conn.scalar(text("SELECT to_regclass('public.resume_fit_analyses')"))
                    == "resume_fit_analyses"
                )
        finally:
            await engine.dispose()
    finally:
        await _cleanup_database_state(database_url, database)


def test_shipped_models_are_explicitly_registered_in_alembic() -> None:
    from app.core.db import Base
    from app.modules.jobs.models import Job  # noqa: F401
    from app.modules.resume_derive.models import ResumeDeriveRun  # noqa: F401
    from app.modules.resume_intelligence.models import (  # noqa: F401
        ResumeAIChangeSet,
        ResumeAIFeedback,
        ResumeAISuggestion,
        ResumeFitAnalysis,
    )
    from app.modules.resumes_v2.models import ResumeV2  # noqa: F401

    assert _NEW_TABLES | {"jobs", "resumes_v2", "resume_derive_runs"} <= set(Base.metadata.tables)
    derive = Base.metadata.tables["resume_derive_runs"]
    assert isinstance(derive.c.job_id.type, PG_UUID)
    assert derive.c.job_id.nullable is True
    assert isinstance(derive.c.target_page_count.type, SmallInteger)
    assert isinstance(derive.c.root_version.type, Integer)
    assert isinstance(derive.c.root_snapshot.type, JSONB)
    assert isinstance(derive.c.cancel_requested_at.type, DateTime)

    fit = Base.metadata.tables["resume_fit_analyses"]
    assert isinstance(fit.c.overall_score.type, Numeric)
    assert (fit.c.overall_score.type.precision, fit.c.overall_score.type.scale) == (5, 2)
    assert isinstance(fit.c.confidence_score.type, Numeric)
    assert (fit.c.confidence_score.type.precision, fit.c.confidence_score.type.scale) == (4, 3)
    for table_name in _NEW_TABLES:
        table = Base.metadata.tables[table_name]
        assert isinstance(table.c.id.type, PG_UUID)
        assert isinstance(table.c.user_id.type, PG_UUID)
        assert table.c.user_id.nullable is False
        assert isinstance(table.c.created_at.type, DateTime)
        assert table.c.created_at.type.timezone is True
    assert isinstance(Base.metadata.tables["resume_ai_suggestions"].c.title.type, Text)

    env_source = (_BACKEND_ROOT / "migrations" / "env.py").read_text(encoding="utf-8")
    assert "from app.modules.jobs.models import Job" in env_source
    assert "from app.modules.resume_derive.models import ResumeDeriveRun" in env_source
    assert "from app.modules.resume_intelligence.models import (" in env_source
    for model in (
        "ResumeAIChangeSet",
        "ResumeAIFeedback",
        "ResumeAISuggestion",
        "ResumeFitAnalysis",
    ):
        assert model in env_source
    assert "from app.modules.resumes_v2.models import ResumeV2" in env_source
