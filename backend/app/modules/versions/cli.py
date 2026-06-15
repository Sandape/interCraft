"""M07 — versions CLI."""
from __future__ import annotations

import asyncio
import json
from uuid import UUID

import typer

from app.core.db import get_session_factory
from app.modules.versions.service import VersionService

app = typer.Typer(help="InterCraft versions CLI (M07)")


def _emit(obj: dict, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(obj, ensure_ascii=False, indent=2))
    else:
        for k, v in obj.items():
            typer.echo(f"{k}: {v}")


@app.command("list")
def cmd_list(
    branch_id: str = typer.Option(..., "--branch-id", "-b"),
    user_id: str = typer.Option(..., "--user-id", "-u"),
    as_json: bool = typer.Option(False, "--json"),
):
    async def _run() -> dict:
        factory = get_session_factory()
        async with factory() as db:
            svc = VersionService(db)
            rows = await svc.list_versions(UUID(branch_id), UUID(user_id))
            return {
                "count": len(rows),
                "versions": [
                    {
                        "id": str(v.id),
                        "version_no": v.version_no,
                        "label": v.label,
                        "is_full_snapshot": v.is_full_snapshot,
                    }
                    for v in rows
                ],
            }

    _emit(asyncio.run(_run()), as_json)


@app.command("save")
def cmd_save(
    branch_id: str = typer.Option(..., "--branch-id", "-b"),
    user_id: str = typer.Option(..., "--user-id", "-u"),
    label: str | None = typer.Option(None, "--label", "-l"),
    as_json: bool = typer.Option(False, "--json"),
):
    async def _run() -> dict:
        factory = get_session_factory()
        async with factory() as db:
            svc = VersionService(db)
            v = await svc.create_manual_version(
                branch_id=UUID(branch_id),
                user_id=UUID(user_id),
                label=label,
            )
            if v is None:
                return {"error": "branch_not_found"}
            return {
                "id": str(v.id),
                "version_no": v.version_no,
                "label": v.label,
            }

    _emit(asyncio.run(_run()), as_json)


@app.command("get")
def cmd_get(
    branch_id: str = typer.Option(..., "--branch-id", "-b"),
    version_no: int = typer.Option(..., "--version-no", "-n"),
    user_id: str = typer.Option(..., "--user-id", "-u"),
    as_json: bool = typer.Option(True, "--json"),
):
    async def _run() -> dict:
        factory = get_session_factory()
        async with factory() as db:
            svc = VersionService(db)
            snap = await svc.get_snapshot(UUID(branch_id), version_no, UUID(user_id))
            return snap or {"error": "not_found"}

    _emit(asyncio.run(_run()), as_json)


@app.command("rollback")
def cmd_rollback(
    branch_id: str = typer.Option(..., "--branch-id", "-b"),
    version_no: int = typer.Option(..., "--version-no", "-n"),
    user_id: str = typer.Option(..., "--user-id", "-u"),
    new_name: str | None = typer.Option(None, "--name"),
):
    async def _run() -> dict:
        factory = get_session_factory()
        async with factory() as db:
            svc = VersionService(db)
            new_b = await svc.rollback_to_version(
                branch_id=UUID(branch_id),
                version_no=version_no,
                user_id=UUID(user_id),
                new_name=new_name,
            )
            if new_b is None:
                return {"error": "not_found"}
            return {"new_branch_id": str(new_b.id), "name": new_b.name}

    _emit(asyncio.run(_run()), as_json=True)


if __name__ == "__main__":  # pragma: no cover
    app()
