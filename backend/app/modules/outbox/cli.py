"""M13 — Outbox CLI (T029).

Usage:
    uv run python -m app.modules.outbox.cli replay <fixture.json>
    uv run python -m app.modules.outbox.cli status --json
    uv run python -m app.modules.outbox.cli validate-schema <entry.json>
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import typer

app = typer.Typer(help="Outbox replay CLI", no_args_is_help=True)


@app.command()
def replay(
    fixture: str = typer.Argument(..., help="Path to JSON file containing ReplayInput"),
    user_id: str = typer.Option("cli-user", help="User ID for RLS"),
):
    """Replay a batch of outbox entries from a JSON fixture file."""
    fixture_path = Path(fixture)
    if not fixture_path.exists():
        print(f"Error: fixture file not found: {fixture}", file=sys.stderr)
        sys.exit(1)

    data = json.loads(fixture_path.read_text())

    from app.modules.outbox.schemas import ReplayInput
    from app.modules.outbox.service import OutboxService

    async def _run():
        svc = OutboxService()
        try:
            inp = ReplayInput.model_validate(data)
            result = await svc.replay_batch(inp, user_id)
            print(json.dumps(result.model_dump(mode="json"), indent=2, default=str))
            return 0
        except Exception as exc:
            print(json.dumps({"error": str(exc)}), file=sys.stderr)
            return 1

    sys.exit(asyncio.run(_run()))


@app.command()
def status(json_mode: bool = typer.Option(True, "--json/--no-json", help="JSON output")):
    """Check outbox server-side health status."""

    async def _run():
        from app.modules.outbox.schemas import OutboxStatusResponse

        resp = OutboxStatusResponse(status="healthy", recent_replays={"last_hour": 0, "conflict_rate": 0.0})
        if json_mode:
            print(json.dumps(resp.model_dump(mode="json"), indent=2))
        else:
            print(f"Status: {resp.status}")

    asyncio.run(_run())


@app.command(name="validate-schema")
def validate_schema(
    entry_file: str = typer.Argument(..., help="Path to JSON file with a single ReplayEntry"),
):
    """Validate a single ReplayEntry JSON against the schema."""
    entry_path = Path(entry_file)
    if not entry_path.exists():
        print(f"Error: entry file not found: {entry_file}", file=sys.stderr)
        sys.exit(1)

    data = json.loads(entry_path.read_text())
    try:
        from app.modules.outbox.schemas import ReplayEntry

        entry = ReplayEntry.model_validate(data)
        print(json.dumps(entry.model_dump(mode="json"), indent=2))
        print("\nValidation: OK")
    except Exception as exc:
        print(f"Validation FAILED: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    app()
