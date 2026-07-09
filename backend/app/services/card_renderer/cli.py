"""[REQ-048 T083] Card renderer CLI.

typer-based CLI surface mirroring the embedding service pattern:

- ``render --plan <file.json> --size 4_3|9_16`` — render an
  InterviewPlan JSON file to a JPG envelope (stdout JSON).
- ``cache-stats`` — print card_cache Redis stats.
- ``cache-purge`` — delete all ``card_cache:*`` keys.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer

from app.services.card_renderer.renderer import CardRenderer


app = typer.Typer(help="Card renderer CLI")


@app.command()
def render(
    plan: str = typer.Option(..., "--plan", help="Path to InterviewPlan JSON file"),
    size: str = typer.Option("4_3", "--size", help="Size variant: 4_3 or 9_16"),
    out: str = typer.Option("", "--out", help="Optional output JPG path (else JSON to stdout)"),
) -> None:
    """Render an InterviewPlan JSON file to a JPG envelope."""
    plan_path = Path(plan)
    if not plan_path.exists():
        raise typer.BadParameter(f"plan file not found: {plan}")
    with plan_path.open("r", encoding="utf-8") as f:
        plan_data: dict[str, Any] = json.load(f)
    result = CardRenderer()
    import asyncio

    rendered = asyncio.run(result.render(plan_data, size_variant=size))
    if out:
        Path(out).write_bytes(rendered.image_bytes)
        typer.echo(
            json.dumps(
                {
                    "out": out,
                    "size_variant": rendered.size_variant,
                    "bytes_total": rendered.bytes_total,
                    "sha256_hex": rendered.sha256_hex,
                },
                ensure_ascii=False,
            )
        )
    else:
        typer.echo(json.dumps(rendered.to_dict(), ensure_ascii=False))


@app.command("cache-stats")
def cache_stats() -> None:
    """Print card_cache Redis stats."""
    from app.services.card_renderer.cache import cache_stats as _stats

    import asyncio

    try:
        import redis.asyncio as redis

        async def _run() -> dict:
            client = redis.from_url("redis://localhost:6379/0")
            try:
                return await _stats(client)
            finally:
                await client.aclose()

        result = asyncio.run(_run())
        typer.echo(json.dumps(result, ensure_ascii=False))
    except Exception as exc:  # noqa: BLE001
        typer.echo(json.dumps({"error": str(exc), "key_count": 0}, ensure_ascii=False))


@app.command("cache-purge")
def cache_purge() -> None:
    """Purge all card_cache:* keys."""
    import redis.asyncio as redis

    from app.services.card_renderer.cache import CARD_CACHE_KEY_PREFIX

    import asyncio

    async def _run() -> int:
        client = redis.from_url("redis://localhost:6379/0")
        removed = 0
        try:
            async for key in client.scan_iter(match=f"{CARD_CACHE_KEY_PREFIX}:*"):
                await client.delete(key)
                removed += 1
        finally:
            await client.aclose()
        return removed

    removed = asyncio.run(_run())
    typer.echo(json.dumps({"removed": removed}, ensure_ascii=False))


__all__ = ["app"]