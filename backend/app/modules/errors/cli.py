"""Error question CLI."""
from __future__ import annotations

import asyncio
import json
from uuid import UUID

import typer

cli = typer.Typer(help="Error questions (M08)")


@cli.command("list")
def list_errors(
    user_id: str = typer.Option(..., "--user-id", help="UUID of user"),
    dimension: str | None = typer.Option(None, "--dimension"),
    status: str | None = typer.Option(None, "--status"),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    uid = UUID(user_id)
    async def _run() -> None:
        from app.core.db import get_session_factory
        from app.modules.errors.repository import ErrorQuestionRepository
        factory = get_session_factory()
        async with factory() as session:
            repo = ErrorQuestionRepository(session)
            items = await repo.list(uid, dimension=dimension, status=status)
            if json_out:
                out = [{"id": str(e.id), "question_text": e.question_text, "status": e.status, "frequency": e.frequency} for e in items]
                typer.echo(json.dumps(out, indent=2, ensure_ascii=False))
            else:
                for e in items:
                    typer.echo(f"  [{e.status}] f={e.frequency} {e.question_text[:60]}")
    asyncio.run(_run())


__all__ = ["cli"]
