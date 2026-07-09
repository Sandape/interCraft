"""M032 — Resume v2 CLI (Constitution Principle II).

Subcommands:
  seed-test-data   Create a sample Pikachu resume for the given user.
  show             Print a v2 resume as JSON.
  analyze          Placeholder for AI analysis (US14).
  duplicate        Duplicate a v2 resume.
  dump-schema      Print the contracts/02-resume-data-schema.md header.

All commands support ``--json`` for machine-readable output.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

import typer

from app.core.db import get_session_context

cli = typer.Typer(help="Resume v2 management commands")


def _emit(data: Any, *, as_json: bool) -> None:
    """Print either as JSON or pretty dict."""
    if as_json:
        typer.echo(json.dumps(data, default=str, ensure_ascii=False, indent=2))
        return
    if isinstance(data, dict):
        for k, v in data.items():
            typer.echo(f"{k}: {v}")
    elif isinstance(data, list):
        for row in data:
            typer.echo(json.dumps(row, default=str, ensure_ascii=False))
    else:
        typer.echo(str(data))


async def _resolve_user(db, email: str):
    """Find a user by email; raise on miss."""
    from sqlalchemy import select
    from app.modules.auth.models import User

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None:
        typer.echo(f"user not found: {email}", err=True)
        raise typer.Exit(code=2)
    return user


@cli.command("seed-test-data")
def seed_test_data(
    email: str = typer.Option(..., "--user", help="Email of the owner user"),
    slug: str = typer.Option("pikachu-sample", "--slug"),
    name: str = typer.Option("Pikachu Sample", "--name"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Create a sample v2 resume for the given user (idempotent on slug)."""

    async def _run() -> dict[str, Any]:
        from app.core.db import set_rls_user_id
        from app.modules.resumes_v2.repository import ResumeV2Repository
        from app.modules.resumes_v2.defaults import (
            apply_template,
            default_resume_data_v2,
        )

        async with get_session_context() as db:
            user = await _resolve_user(db, email)
            await set_rls_user_id(db, user.id)
            repo = ResumeV2Repository(db)
            data = default_resume_data_v2()
            apply_template(data, "pikachu")
            try:
                row = await repo.create(
                    user_id=user.id, name=name, slug=slug, data=data
                )
                await db.commit()
                return {
                    "id": str(row.id),
                    "user_id": str(row.user_id),
                    "name": row.name,
                    "slug": row.slug,
                    "version": int(row.version),
                    "template": "pikachu",
                }
            except Exception as e:
                await db.rollback()
                return {"error": str(e)}

    _emit(asyncio.run(_run()), as_json=as_json)


@cli.command("show")
def show(
    resume_id: str = typer.Argument(..., help="Resume UUID (v7)"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Print a v2 resume as JSON."""

    async def _run() -> dict[str, Any]:
        from sqlalchemy import select
        from app.modules.resumes_v2.models import ResumeV2

        async with get_session_context() as db:
            stmt = select(ResumeV2).where(ResumeV2.id == resume_id)
            result = await db.execute(stmt)
            row = result.scalar_one_or_none()
            if row is None:
                typer.echo(f"resume not found: {resume_id}", err=True)
                raise typer.Exit(code=2)
            return {
                "id": str(row.id),
                "user_id": str(row.user_id),
                "name": row.name,
                "slug": row.slug,
                "tags": list(row.tags or []),
                "is_public": bool(row.is_public),
                "is_locked": bool(row.is_locked),
                "version": int(row.version),
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "updated_at": row.updated_at.isoformat() if row.updated_at else None,
                "data": row.data,
            }

    _emit(asyncio.run(_run()), as_json=as_json)


@cli.command("analyze")
def analyze(
    resume_id: str = typer.Argument(..., help="Resume UUID (v7)"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Placeholder for US14 (DeepSeek analysis)."""
    typer.echo(
        f"analyze: not yet implemented (US14 T152). resume_id={resume_id}",
        err=True,
    )
    if as_json:
        typer.echo(
            json.dumps(
                {
                    "resume_id": resume_id,
                    "status": "not_implemented",
                    "reason": "US14 T152 ships the analyze endpoint",
                }
            )
        )
    raise typer.Exit(code=1)


@cli.command("duplicate")
def duplicate(
    resume_id: str = typer.Argument(..., help="Resume UUID (v7) to duplicate"),
    email: str = typer.Option(..., "--user", help="Owner email (must own the resume)"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Duplicate a v2 resume under the same owner."""

    async def _run() -> dict[str, Any]:
        from app.core.db import set_rls_user_id
        from app.modules.resumes_v2.service import ResumeV2Service

        async with get_session_context() as db:
            user = await _resolve_user(db, email)
            await set_rls_user_id(db, user.id)
            svc = ResumeV2Service(db)
            from uuid import UUID
            try:
                rid = UUID(resume_id)
            except ValueError:
                typer.echo(f"invalid uuid: {resume_id}", err=True)
                raise typer.Exit(code=2)
            try:
                copy = await svc.duplicate_resume(rid, user_id=user.id)
                await db.commit()
                return {
                    "id": str(copy.id),
                    "name": copy.name,
                    "slug": copy.slug,
                    "version": int(copy.version),
                    "is_public": bool(copy.is_public),
                    "is_locked": bool(copy.is_locked),
                }
            except Exception as e:
                await db.rollback()
                return {"error": str(e)}

    _emit(asyncio.run(_run()), as_json=as_json)


@cli.command("dump-schema")
def dump_schema(
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Print the data-schema markdown (US1 T026)."""
    schema_path = (
        Path(__file__).resolve().parents[4]
        / "specs"
        / "032-resume-renderer-v2"
        / "contracts"
        / "02-resume-data-schema.md"
    )
    if not schema_path.exists():
        typer.echo(f"schema file missing: {schema_path}", err=True)
        raise typer.Exit(code=2)
    content = schema_path.read_text(encoding="utf-8")
    if as_json:
        typer.echo(
            json.dumps({"path": str(schema_path), "length": len(content)})
        )
    else:
        typer.echo(content)


# Register under the top-level CLI.
def register(parent: typer.Typer) -> None:
    """Mount as ``<parent> resumes-v2 ...``."""
    parent.add_typer(cli, name="resumes-v2")


__all__ = ["cli", "register"]


if __name__ == "__main__":  # pragma: no cover
    cli()
