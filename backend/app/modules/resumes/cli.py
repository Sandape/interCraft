"""M06 — resumes CLI."""
from __future__ import annotations

import asyncio
import json
from uuid import UUID

import typer

from app.core.db import get_session_factory
from app.modules.resumes.service import ResumeService

app = typer.Typer(help="InterCraft resumes CLI (M06)")


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
            svc = ResumeService(db)
            rows = await svc.list_branches(UUID(user_id))
            return {
                "count": len(rows),
                "branches": [
                    {
                        "id": str(b.id),
                        "name": b.name,
                        "company": b.company,
                        "is_main": b.is_main,
                    }
                    for b in rows
                ],
            }

    _emit(asyncio.run(_run()), as_json)


@app.command("create")
def cmd_create(
    user_id: str = typer.Option(..., "--user-id", "-u"),
    name: str = typer.Option(..., "--name", "-n"),
    company: str | None = typer.Option(None, "--company", "-c"),
    position: str | None = typer.Option(None, "--position", "-p"),
    parent_id: str | None = typer.Option(None, "--parent-id"),
    is_main: bool = typer.Option(False, "--main"),
    as_json: bool = typer.Option(False, "--json"),
):
    async def _run() -> dict:
        factory = get_session_factory()
        async with factory() as db:
            svc = ResumeService(db)
            b = await svc.create_branch(
                user_id=UUID(user_id),
                name=name,
                company=company,
                position=position,
                parent_id=UUID(parent_id) if parent_id else None,
                is_main=is_main,
            )
            return {"id": str(b.id), "name": b.name, "is_main": b.is_main}

    _emit(asyncio.run(_run()), as_json)


@app.command("reorder")
def cmd_reorder(
    block_id: str = typer.Option(..., "--block-id", "-b"),
    prev_id: str | None = typer.Option(None, "--prev-id"),
    next_id: str | None = typer.Option(None, "--next-id"),
    user_id: str = typer.Option(..., "--user-id", "-u"),
):
    async def _run() -> dict:
        factory = get_session_factory()
        async with factory() as db:
            svc = ResumeService(db)
            block = await svc.reorder_block(
                block_id=UUID(block_id),
                user_id=UUID(user_id),
                prev_id=UUID(prev_id) if prev_id else None,
                next_id=UUID(next_id) if next_id else None,
            )
            if block is None:
                return {"error": "not_found"}
            return {"id": str(block.id), "order_index": block.order_index}

    _emit(asyncio.run(_run()), as_json=True)


if __name__ == "__main__":  # pragma: no cover
    app()
