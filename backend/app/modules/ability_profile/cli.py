"""Ability profile CLI — list-links, revoke-expired, list-exports."""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from uuid import UUID

import typer

from app.core.db import get_session_factory

cli = typer.Typer(help="Personal Ability Profile (M18)")


@cli.command("list-links")
def list_links(
    user_id: str = typer.Option(..., "--user-id", help="UUID of the user"),
    json_out: bool = typer.Option(False, "--json", help="JSON output"),
) -> None:
    """List share links for a user."""
    uid = UUID(user_id)

    async def _run() -> None:
        from app.modules.ability_profile.repository import AbilityProfileRepository

        factory = get_session_factory()
        async with factory() as session:
            repo = AbilityProfileRepository(session)
            links = await repo.list_share_links(uid)
            if json_out:
                out = [{
                    "id": str(l.id),
                    "token": l.token,
                    "expires_at": l.expires_at.isoformat() if l.expires_at else None,
                    "revoked_at": l.revoked_at.isoformat() if l.revoked_at else None,
                    "access_count": l.access_count,
                    "status": _link_status(l),
                } for l in links]
                typer.echo(json.dumps(out, indent=2, ensure_ascii=False))
            else:
                for l in links:
                    status = _link_status(l)
                    typer.echo(f"  {l.token} [{status}] access={l.access_count}")

    asyncio.run(_run())


@cli.command("revoke-expired")
def revoke_expired() -> None:
    """Revoke all expired share links."""
    async def _run() -> None:
        from app.modules.ability_profile.models import ProfileShareLink
        from sqlalchemy import select

        factory = get_session_factory()
        async with factory() as session:
            now = datetime.now(timezone.utc)
            stmt = select(ProfileShareLink).where(
                ProfileShareLink.revoked_at.is_(None),
                ProfileShareLink.expires_at.is_not(None),
                ProfileShareLink.expires_at <= now,
            )
            result = await session.execute(stmt)
            expired = list(result.scalars().all())
            count = 0
            for link in expired:
                link.revoked_at = now
                count += 1
            await session.commit()
            typer.echo(f"Revoked {count} expired links")

    asyncio.run(_run())


@cli.command("list-exports")
def list_exports(
    user_id: str = typer.Option(..., "--user-id", help="UUID of the user"),
    json_out: bool = typer.Option(False, "--json", help="JSON output"),
) -> None:
    """List export logs for a user."""
    uid = UUID(user_id)

    async def _run() -> None:
        from app.modules.ability_profile.repository import AbilityProfileRepository

        factory = get_session_factory()
        async with factory() as session:
            repo = AbilityProfileRepository(session)
            logs = await repo.list_export_logs(uid)
            if json_out:
                out = [{
                    "id": str(l.id),
                    "status": l.status,
                    "file_size_bytes": l.file_size_bytes,
                    "requested_at": l.requested_at.isoformat() if l.requested_at else None,
                } for l in logs]
                typer.echo(json.dumps(out, indent=2, ensure_ascii=False))
            else:
                for l in logs:
                    size = f" ({l.file_size_bytes}B)" if l.file_size_bytes else ""
                    typer.echo(f"  {l.status} {size} @ {l.requested_at}")

    asyncio.run(_run())


def _link_status(link) -> str:
    if link.revoked_at:
        return "revoked"
    if link.expires_at and link.expires_at < datetime.now(timezone.utc):
        return "expired"
    return "active"


__all__ = ["cli"]
