"""M05 — sessions CLI."""
from __future__ import annotations

import asyncio
import json
from uuid import UUID

import typer

from app.core.db import get_session_factory
from app.modules.sessions.service import SessionService

app = typer.Typer(help="InterCraft sessions CLI (M05)")


def _emit(obj: dict, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(obj, ensure_ascii=False, indent=2))
    else:
        for k, v in obj.items():
            typer.echo(f"{k}: {v}")


@app.command("list")
def cmd_list(
    user_id: str = typer.Option(..., "--user-id", "-u"),
    as_json: bool = typer.Option(False, "--json"),
):
    async def _run() -> dict:
        factory = get_session_factory()
        async with factory() as db:
            svc = SessionService(db)
            rows = await svc.repo.list_active(UUID(user_id))
            return {
                "count": len(rows),
                "sessions": [
                    {
                        "id": str(s.id),
                        "device_id": s.device_id[:12] + "...",
                        "last_seen_at": s.last_seen_at.isoformat(),
                    }
                    for s in rows
                ],
            }

    _emit(asyncio.run(_run()), as_json)


@app.command("revoke")
def cmd_revoke(
    session_id: str = typer.Option(..., "--session-id", "-s"),
    user_id: str | None = typer.Option(None, "--user-id", "-u"),
):
    async def _run() -> None:
        factory = get_session_factory()
        async with factory() as db:
            svc = SessionService(db)
            await svc.revoke_session(UUID(session_id), user_id=UUID(user_id) if user_id else None)

    try:
        asyncio.run(_run())
    except Exception as e:
        typer.echo(f"revoke failed: {e}", err=True)
        raise typer.Exit(code=1) from None
    typer.echo("ok")


if __name__ == "__main__":  # pragma: no cover
    app()
