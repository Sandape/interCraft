"""Async SQLAlchemy engine + session factory + per-request session dependency.

The session dependency sets the PostgreSQL RLS context (app.user_id)
per spec FR-004. The register flow uses a no-RLS session because the
user doesn't exist yet.
"""
from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from uuid import UUID

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings


class Base(DeclarativeBase):
    """Single declarative base for all ORM models."""


_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        settings = get_settings()
        connect_args: dict[str, object] = {}
        if settings.db_ssl:
            # asyncpg accepts True / False / "prefer" / "require" / context
            connect_args["ssl"] = settings.db_ssl
        engine_kwargs: dict[str, object] = {
            "echo": settings.db_echo,
            "pool_pre_ping": True,
            "future": True,
            "connect_args": connect_args,
        }
        if settings.db_use_null_pool:
            from sqlalchemy.pool import NullPool

            engine_kwargs["poolclass"] = NullPool
        else:
            engine_kwargs["pool_size"] = settings.db_pool_size
            engine_kwargs["max_overflow"] = settings.db_max_overflow
        _engine = create_async_engine(settings.database_url, **engine_kwargs)
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            expire_on_commit=False,
            autoflush=False,
            autocommit=False,
        )
    return _session_factory


async def dispose_engine() -> None:
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None


async def db_ping() -> bool:
    """Health probe — returns True if `SELECT 1` works."""
    try:
        async with get_engine().connect() as conn:
            await conn.exec_driver_sql("SELECT 1")
        return True
    except Exception:
        return False


@asynccontextmanager
async def _session_cm() -> AsyncGenerator[AsyncSession, None]:
    """Per-request session.

    Commits on successful exit; rolls back on exception. Both commit and
    rollback end the transaction, which also resets the `SET LOCAL app.user_id`
    set during the request. With NullPool (tests) or pool_pre_ping (prod)
    the connection cannot leak the previous request's RLS context.

    Belt-and-suspenders: after commit/rollback we also issue a
    ``RESET app.user_id`` so that even if the connection is returned to
    the pool mid-failure (where the auto-reset may have been skipped),
    the next request sees a clean GUC.
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        else:
            try:
                await session.commit()
            except Exception:
                await session.rollback()
                raise
        finally:
            # Belt-and-suspenders: explicitly clear the RLS GUC so the
            # connection returned to the pool has no stale user context.
            # Safe because per-request session is over and connection
            # is about to be returned to the pool.
            try:
                await session.execute(
                    __import__("sqlalchemy").text("RESET app.user_id")
                )
            except Exception:
                pass


async def get_db_session_no_rls() -> AsyncGenerator[AsyncSession, None]:
    """Session WITHOUT RLS context. Use ONLY for register / first INSERT into users."""
    async with _session_cm() as session:
        yield session


async def get_db_session(
    user_id: UUID | None = None,
) -> AsyncGenerator[AsyncSession, None]:
    """Per-request session. If `user_id` is provided, bind RLS via `SET LOCAL`."""
    async with _session_cm() as session:
        await session.begin()
        if user_id is not None:
            # Use SET (session-scoped) instead of SET LOCAL because asyncpg's
            # ORM autobegin timing makes SET LOCAL disappear between the GUC
            # statement and the subsequent ORM INSERT when running through
            # ``session.add(...)`` + ``session.flush()``. SET (third arg false)
            # binds for the duration of this connection — safe because the
            # per-request session is closed at yield exit (NullPool + autouse
            # cleanup in conftest.py).
            await session.execute(
                __import__("sqlalchemy").text("SELECT set_config('app.user_id', :u, false)"),
                {"u": str(user_id)},
            )
        yield session


async def set_rls_user_id(session: AsyncSession, user_id: UUID) -> None:
    """Bind RLS context to `user_id` mid-transaction. Use this for the register
    flow to satisfy the WITH CHECK on `users(id = app.user_id)` before INSERT.
    """
    await session.execute(
        __import__("sqlalchemy").text("SELECT set_config('app.user_id', :u, true)"),
        {"u": str(user_id)},
    )


@asynccontextmanager
async def get_session_context(
    user_id: UUID | None = None,
) -> AsyncGenerator[AsyncSession, None]:
    """Public async context manager for ad-hoc DB sessions outside a request.

    With `user_id`, binds RLS via SET LOCAL. Without, returns a plain
    session. Commits on successful exit; rolls back on exception.
    """
    async with _session_cm() as session:
        if user_id is not None:
            await session.execute(
                __import__("sqlalchemy").text("SELECT set_config('app.user_id', :u, true)"),
                {"u": str(user_id)},
            )
        yield session


__all__ = [
    "Base",
    "db_ping",
    "dispose_engine",
    "get_db_session",
    "get_db_session_no_rls",
    "get_engine",
    "get_session_context",
    "get_session_factory",
    "set_rls_user_id",
]
