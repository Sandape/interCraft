"""RLS helpers — both migration-time (Alembic ops) and runtime (session SET LOCAL)."""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def set_user_context(session: AsyncSession, user_id: str) -> None:
    """Bind PostgreSQL RLS GUC for the current transaction."""
    await session.execute(text("SELECT set_config('app.user_id', :u, true)"), {"u": str(user_id)})


async def with_user_context(session: AsyncSession, user_id: str) -> None:
    """Same as set_user_context; aliased for readability in service code."""
    await set_user_context(session, user_id)


async def disable_rls_for_session(session: AsyncSession) -> None:
    """Phase 1: register flow inserts into `users` before any RLS context exists.

    Sets `row_security = off` for the current transaction. Use sparingly.
    """
    await session.execute(text("SET LOCAL row_security = off"))


def enable_rls_sql(table: str, policy: str | None = None) -> list[str]:
    """Return the SQL statements to enable + force RLS + add the standard policy."""
    policy = policy or f"{table}_user_isolation"
    return [
        f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;",
        f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;",
        (
            f"CREATE POLICY {policy} ON {table} "
            f"USING (user_id = current_setting('app.user_id', true)::uuid) "
            f"WITH CHECK (user_id = current_setting('app.user_id', true)::uuid);"
        ),
    ]


__all__ = ["disable_rls_for_session", "enable_rls_sql", "set_user_context", "with_user_context"]
