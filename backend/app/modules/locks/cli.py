"""M12 — Lock CLI (T021).

Usage:
    uv run python -m app.modules.locks.cli acquire --resource-type resume_branch --resource-id <uuid> --json
    uv run python -m app.modules.locks.cli release --lock-id <uuid> --json
    uv run python -m app.modules.locks.cli status --resource-type resume_branch --resource-id <uuid> --json
    uv run python -m app.modules.locks.cli list-stale
    uv run python -m app.modules.locks.cli replay <fixture.json>
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from uuid import UUID

import typer

app = typer.Typer(help="Lock management CLI", no_args_is_help=True)


@app.command()
def acquire(
    resource_type: str = typer.Option(..., help="Resource type: resume_branch | error_question"),
    resource_id: str = typer.Option(..., help="Resource UUID"),
    user_id: str = typer.Option("cli-user", help="User ID for audit"),
    device_id: str = typer.Option("cli", help="Device fingerprint"),
    session_id: str = typer.Option("00000000-0000-0000-0000-000000000000", help="Session ID"),
    json_mode: bool = typer.Option(True, "--json/--no-json", help="JSON output"),
):
    """Acquire a pessimistic lock on a resource."""
    from app.modules.locks.schemas import AcquireInput
    from app.modules.locks.service import LockService

    async def _run():
        svc = LockService()
        try:
            result = await svc.acquire(
                user_id=user_id,
                device_id=device_id,
                session_id=session_id,
                input=AcquireInput(resource_type=resource_type, resource_id=UUID(resource_id)),
            )
            if json_mode:
                print(json.dumps(result.model_dump(mode="json"), indent=2, default=str))
            else:
                print(f"Lock acquired: {result.lock_id}")
            return 0
        except Exception as exc:
            if json_mode:
                print(json.dumps({"error": str(exc)}))
            else:
                print(f"Error: {exc}")
            return 1

    sys.exit(asyncio.run(_run()))


@app.command()
def release(
    lock_id: str = typer.Option(..., help="Lock UUID to release"),
    user_id: str = typer.Option("cli-user", help="User ID"),
    json_mode: bool = typer.Option(True, "--json/--no-json", help="JSON output"),
):
    """Release a lock by ID."""
    from app.modules.locks.service import LockService

    async def _run():
        svc = LockService()
        try:
            result = await svc.release(lock_id=lock_id, user_id=user_id)
            if json_mode:
                print(json.dumps(result.model_dump(mode="json"), indent=2, default=str))
            else:
                print(f"Lock released: {result.lock_id}")
            return 0
        except Exception as exc:
            if json_mode:
                print(json.dumps({"error": str(exc)}))
            else:
                print(f"Error: {exc}")
            return 1

    sys.exit(asyncio.run(_run()))


@app.command()
def status(
    resource_type: str = typer.Option(..., help="Resource type"),
    resource_id: str = typer.Option(..., help="Resource UUID"),
    json_mode: bool = typer.Option(True, "--json/--no-json", help="JSON output"),
):
    """Query lock status for a resource."""
    from app.modules.locks.service import LockService

    async def _run():
        svc = LockService()
        try:
            result = await svc.get_status(resource_type, resource_id)
            if json_mode:
                print(json.dumps(result.model_dump(mode="json"), indent=2, default=str))
            else:
                status = "locked" if result.locked else "unlocked"
                print(f"Resource {resource_type}/{resource_id}: {status}")
            return 0
        except Exception as exc:
            print(f"Error: {exc}")
            return 1

    sys.exit(asyncio.run(_run()))


@app.command(name="list-stale")
def list_stale(json_mode: bool = typer.Option(True, "--json/--no-json", help="JSON output")):
    """Scan for stale locks (>90s no heartbeat)."""
    from app.modules.locks.redis_store import scan_stale

    async def _run():
        try:
            stale = await scan_stale()
            if json_mode:
                print(json.dumps(stale, indent=2, default=str))
            else:
                print(f"Found {len(stale)} stale lock(s)")
                for lock in stale:
                    print(f"  - {lock.get('lock_id')} ({lock.get('resource_type')}/{lock.get('resource_id')})")
            return 0
        except Exception as exc:
            print(f"Error: {exc}")
            return 1

    sys.exit(asyncio.run(_run()))


@app.command(name="replay")
def replay(
    fixture: str = typer.Argument(..., help="Path to JSON fixture file with lock operations"),
):
    """Replay lock operations from a JSON fixture file."""
    fixture_path = Path(fixture)
    if not fixture_path.exists():
        print(f"Error: fixture file not found: {fixture}")
        sys.exit(1)

    data = json.loads(fixture_path.read_text())
    ops = data if isinstance(data, list) else data.get("operations", [])

    from app.modules.locks.schemas import AcquireInput
    from app.modules.locks.service import LockService

    async def _run():
        svc = LockService()
        results = []
        for i, op in enumerate(ops):
            op_type = op.get("type")
            try:
                if op_type == "acquire":
                    inp = AcquireInput(
                        resource_type=op["resource_type"],
                        resource_id=UUID(op["resource_id"]),
                    )
                    r = await svc.acquire(
                        user_id=op.get("user_id", "cli"),
                        device_id=op.get("device_id", "cli"),
                        session_id=op.get("session_id", "00000000-0000-0000-0000-000000000000"),
                        input=inp,
                    )
                    results.append({"index": i, "ok": True, "lock_id": r.lock_id})
                elif op_type == "release":
                    r = await svc.release(
                        lock_id=op["lock_id"],
                        user_id=op.get("user_id", "cli"),
                    )
                    results.append({"index": i, "ok": True})
                else:
                    results.append({"index": i, "ok": False, "error": f"Unknown op: {op_type}"})
            except Exception as exc:
                results.append({"index": i, "ok": False, "error": str(exc)})

        print(json.dumps(results, indent=2, default=str))
        return 0

    sys.exit(asyncio.run(_run()))


if __name__ == "__main__":
    app()
