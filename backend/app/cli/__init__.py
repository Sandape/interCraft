"""Top-level CLI for InterCraft backend (Constitution II)."""
from __future__ import annotations

import asyncio
import sys

import typer

app = typer.Typer(help="InterCraft top-level CLI")


@app.command("serve")
def serve(
    host: str = typer.Option("0.0.0.0", "--host"),
    port: int = typer.Option(8000, "--port"),
    reload: bool = typer.Option(True, "--reload/--no-reload"),
) -> None:
    """Run the FastAPI app via uvicorn."""
    import uvicorn

    uvicorn.run("app.main:app", host=host, port=port, reload=reload)


@app.command("migrate")
def migrate(
    action: str = typer.Option("upgrade", "--action", help="upgrade | downgrade | stamp | current"),
    revision: str = typer.Option("head", "--to"),
) -> None:
    """Run Alembic migrations."""
    from alembic import command
    from alembic.config import Config

    cfg = Config("alembic.ini")
    if action == "upgrade":
        command.upgrade(cfg, revision)
    elif action == "downgrade":
        command.downgrade(cfg, revision)
    elif action == "stamp":
        command.stamp(cfg, revision)
    elif action == "current":
        command.current(cfg)
    else:
        typer.echo(f"unknown action: {action}", err=True)
        raise typer.Exit(code=2)


@app.command("seed")
def seed() -> None:
    """Create the demo user from `backend/scripts/seed.py`."""
    from scripts import seed as _seed  # type: ignore

    if hasattr(_seed, "run"):
        asyncio.run(_seed.run())  # type: ignore[attr-defined]
    else:
        typer.echo("scripts/seed.py has no async `run()` entry", err=True)
        raise typer.Exit(code=1)


@app.command("reset-db")
def reset_db(yes: bool = typer.Option(False, "--yes", "-y")) -> None:
    """DANGER: drop and recreate the database. Refuses on `APP_ENV=production`."""
    from scripts import reset_db as _reset  # type: ignore

    if hasattr(_reset, "run"):
        asyncio.run(_reset.run(yes=yes))  # type: ignore[attr-defined]
    else:
        typer.echo("scripts/reset_db.py has no async `run()` entry", err=True)
        raise typer.Exit(code=1)


@app.command("replay")
def replay(
    fixture: str = typer.Argument(..., help="Path to a JSON fixture"),
) -> None:
    """Replay a captured request fixture (Constitution V observability)."""
    from app.modules.auth.cli import cmd_replay

    sys.argv = ["auth", "replay", fixture]
    cmd_replay(fixture=fixture, as_json=True)


# REQ-061 — mount runtime / metering CLI groups when available.
try:
    from app.modules.ai_runtime.cli import app as ai_runtime_cli

    app.add_typer(ai_runtime_cli, name="ai-runtime")
except Exception:  # pragma: no cover
    pass

try:
    from app.modules.ai_metering.cli import app as ai_metering_cli

    app.add_typer(ai_metering_cli, name="ai-metering")
except Exception:  # pragma: no cover
    pass


if __name__ == "__main__":  # pragma: no cover
    app()
