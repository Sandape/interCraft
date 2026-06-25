"""IRT CLI — Constitution II interface for the IRT library.

Usage examples (after wiring into `app.cli.main:app`):

    # Seed 50 items (10 per dimension) into the bank
    uv run intercraft irt seed-items

    # List seeded items for one dimension
    uv run intercraft irt list-items --dimension tech_depth --status uncalibrated

    # Estimate θ for a user on one dimension
    uv run intercraft irt estimate-theta --user-id <uuid> --dimension tech_depth

Errors to stderr. JSON output for list operations. The estimate command
prints a single `key=value` line per theta field so it's greppable
without JSON parsing.

US1 scope: estimate uses the user's most recent 200 responses across
all dimensions and emits one line per dimension that has at least 3
responses (fewer than 3 yields SE=∞ which we suppress).
"""
from __future__ import annotations

import asyncio
import json
import uuid

import structlog
import typer
from sqlalchemy import text

from app.core.db import get_session_factory
from app.modules.irt.engine import estimate_theta_mle

cli = typer.Typer(help="IRT item bank (REQ-030 US1)")

logger = structlog.get_logger("irt.cli")

# Minimum number of responses per dimension for θ estimation. Below
# this, SE is essentially infinite and the result is not actionable.
_MIN_RESPONSES: int = 3


def _validate_uuid(value: str, flag: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except (ValueError, AttributeError) as exc:
        typer.echo(f"{flag} must be a valid UUID, got: {value!r}", err=True)
        raise typer.Exit(code=2) from exc


@cli.command("seed-items")
def seed_items(
    reset: bool = typer.Option(
        False,
        "--reset",
        help="Drop and re-create all seed items (DANGEROUS — wipes all data in irt_items).",
    ),
) -> None:
    """Seed 50 hardcoded items (10 per dimension) into the bank."""

    async def _run() -> None:
        from app.modules.irt.repository import ItemRepository
        from app.modules.irt.seed import seed_all_dimensions

        factory = get_session_factory()
        async with factory() as session:
            if reset:
                # Irreversible: cascade to irt_item_responses via item_id SET NULL
                # preserves response history but removes the bank.
                await session.execute(text("DELETE FROM irt_items"))
                typer.echo("irt_items cleared (--reset)")
            repo = ItemRepository(session)
            items = seed_all_dimensions()
            inserted = await repo.upsert_seed_items(items)
            await session.commit()
            typer.echo(f"seeded {inserted}/{len(items)} items (5 dims × 10)")

    asyncio.run(_run())


@cli.command("list-items")
def list_items(
    dimension: str = typer.Option(..., "--dimension", help="dimension key"),
    status: str | None = typer.Option(
        None, "--status", help="filter by status (uncalibrated/calibrated/retired/flagged)"
    ),
    json_out: bool = typer.Option(False, "--json", help="JSON output"),
) -> None:
    """List items in one dimension, optionally filtered by status."""

    async def _run() -> None:
        from app.modules.irt.repository import ItemRepository

        factory = get_session_factory()
        async with factory() as session:
            repo = ItemRepository(session)
            items = await repo.list_for_dimension(dimension, status=status)
            if json_out:
                payload = [
                    {
                        "id": str(i.id),
                        "dimension": i.dimension,
                        "difficulty_b": float(i.difficulty_b),
                        "discrimination_a": float(i.discrimination_a),
                        "model": i.model,
                        "status": i.status,
                        "response_count": i.response_count,
                        "standard_error": float(i.standard_error),
                        "last_calibrated_at": (
                            i.last_calibrated_at.isoformat()
                            if i.last_calibrated_at
                            else None
                        ),
                    }
                    for i in items
                ]
                typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))
            else:
                typer.echo(f"  {len(items)} items in {dimension!r} (status={status})")
                for i in items:
                    typer.echo(
                        f"  - id={i.id} b={float(i.difficulty_b):+.2f} "
                        f"a={float(i.discrimination_a):.2f} "
                        f"status={i.status}"
                    )

    asyncio.run(_run())


@cli.command("estimate-theta")
def estimate_theta(
    user_id: str = typer.Option(..., "--user-id", help="user UUID"),
    dimension: str | None = typer.Option(
        None,
        "--dimension",
        help="estimate θ for one dimension; omit to fan out across all dimensions",
    ),
) -> None:
    """Estimate user θ from recent responses. Prints one line per dimension.

    Output format (stdout, key=value pairs, one per line per dimension):
        dimension=tech_depth theta=1.234 se=0.567 n_items=10 converged=true
    Errors → stderr. Exit code 0 even when no dimensions have enough data
    (silent skip — caller decides what "no data" means).
    """

    async def _run() -> None:
        from app.modules.irt.repository import ItemResponseRepository
        from app.modules.irt.seed import DIMENSIONS

        uid = _validate_uuid(user_id, "--user-id")
        factory = get_session_factory()
        async with factory() as session:
            # RLS: scope responses to this user.
            await session.execute(
                text("SELECT set_config('app.user_id', :uid, true)"),
                {"uid": str(uid)},
            )
            response_repo = ItemResponseRepository(session)
            dims = (dimension,) if dimension else DIMENSIONS

            any_output = False
            for dim in dims:
                responses = await response_repo.list_for_user(
                    uid, dimension=dim, limit=200
                )
                if len(responses) < _MIN_RESPONSES:
                    typer.echo(
                        f"# skipped {dim}: only {len(responses)} responses "
                        f"(min {_MIN_RESPONSES})",
                        err=True,
                    )
                    continue
                # Look up the item parameters for each response. The list
                # already includes the response, but we need (a, b) — go
                # back to irt_items for each.
                triples: list[tuple[float, float, int]] = []
                for r in responses:
                    if r.item_id is None:
                        continue
                    item = await response_repo.session.get(
                        __import__("app.modules.irt.models", fromlist=["Item"]).Item,
                        r.item_id,
                    )
                    if item is None:
                        continue
                    u = 1 if r.response == "correct" else 0
                    triples.append(
                        (float(item.discrimination_a), float(item.difficulty_b), u)
                    )
                if len(triples) < _MIN_RESPONSES:
                    continue
                result = estimate_theta_mle(triples)
                typer.echo(
                    f"dimension={dim} theta={result.theta:.3f} "
                    f"se={result.standard_error:.3f} n_items={result.n_items} "
                    f"converged={str(result.converged).lower()}"
                )
                any_output = True
            if not any_output:
                typer.echo(
                    "# no dimensions produced estimates; "
                    "user has fewer than 3 responses per dimension",
                    err=True,
                )

    asyncio.run(_run())


__all__ = ["cli"]


if __name__ == "__main__":  # pragma: no cover
    cli()
