"""Ability dimension CLI — seed + list."""
from __future__ import annotations

import asyncio
import json
from uuid import UUID

import typer

from app.core.db import get_session_factory

cli = typer.Typer(help="Ability dimensions (M09)")


@cli.command("seed")
def seed(
    user_id: str = typer.Option(..., "--user-id", help="UUID of the user to seed dimensions for"),
) -> None:
    """Seed 6 ability dimensions for a new user."""
    uid = UUID(user_id)

    async def _run() -> None:
        from app.modules.abilities.repository import AbilityDimensionRepository

        factory = get_session_factory()
        async with factory() as session:
            repo = AbilityDimensionRepository(session)
            dims = await repo.seed_for_new_user(uid)
            await session.commit()
            for d in dims:
                typer.echo(f"  {d.dimension_key}: actual={d.actual_score} ideal={d.ideal_score}")
            typer.echo(f"Seeded {len(dims)} dimensions for user {user_id}")

    asyncio.run(_run())


@cli.command("list")
def list_dims(
    user_id: str = typer.Option(..., "--user-id", help="UUID of the user"),
    json_out: bool = typer.Option(False, "--json", help="JSON output"),
) -> None:
    """List ability dimensions for a user."""
    uid = UUID(user_id)

    async def _run() -> None:
        from app.modules.abilities.repository import AbilityDimensionRepository

        factory = get_session_factory()
        async with factory() as session:
            repo = AbilityDimensionRepository(session)
            dims = await repo.list_for_user(uid)
            if json_out:
                out = [{
                    "id": str(d.id),
                    "dimension_key": d.dimension_key,
                    "actual_score": float(d.actual_score),
                    "ideal_score": float(d.ideal_score),
                    "is_active": d.is_active,
                    "sub_scores": d.sub_scores,
                } for d in dims]
                typer.echo(json.dumps(out, indent=2, ensure_ascii=False))
            else:
                for d in dims:
                    active = "✓" if d.is_active else "✗"
                    typer.echo(f"  {d.dimension_key} [{active}] actual={d.actual_score} ideal={d.ideal_score}")

    asyncio.run(_run())


__all__ = ["cli"]
