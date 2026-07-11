"""CLI: resume-derive run|status|validate-pages (REQ-055 / Constitution II)."""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from uuid import UUID

import typer

from app.modules.resume_derive.page_count import count_pdf_pages

app = typer.Typer(name="resume-derive", help="REQ-055 resume derive CLI")


@app.command("validate-pages")
def validate_pages(
    pdf: Path = typer.Option(None, "--pdf", exists=True, dir_okay=False),
    expect: int = typer.Option(..., "--expect", min=1, max=3),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    if pdf is None:
        typer.echo("ERROR: --pdf required", err=True)
        raise typer.Exit(2)
    raw = pdf.read_bytes()
    actual = count_pdf_pages(raw)
    payload = {"actual": actual, "expected": expect}
    if json_out:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(f"actual={actual} expected={expect}")
    raise typer.Exit(0 if actual == expect else 3)


@app.command("status")
def status_cmd(
    run_id: str = typer.Option(..., "--run-id"),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    async def _run() -> int:
        from app.core.db import get_session_factory
        from app.modules.resume_derive.models import ResumeDeriveRun

        factory = get_session_factory()
        async with factory() as session:
            row = await session.get(ResumeDeriveRun, UUID(run_id))
            if row is None:
                typer.echo("NOT_FOUND", err=True)
                return 2
            payload = {
                "run_id": str(row.id),
                "status": row.status,
                "phase": row.phase,
                "derived_resume_id": str(row.derived_resume_id) if row.derived_resume_id else None,
            }
            typer.echo(json.dumps(payload) if json_out else payload)
            return 0

    raise typer.Exit(asyncio.run(_run()))


@app.command("run")
def run_cmd(
    user_id: str = typer.Option(..., "--user-id"),
    job_id: str = typer.Option(..., "--job-id"),
    pages: int = typer.Option(..., "--pages", min=1, max=3),
    template: str = typer.Option("pikachu", "--template"),
    async_mode: bool = typer.Option(False, "--async"),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    async def _run() -> int:
        from app.core.db import get_session_factory
        from app.modules.resume_derive.service import DeriveError, ResumeDeriveService
        from app.workers.tasks.resume_derive import execute_resume_derive

        factory = get_session_factory()
        async with factory() as session:
            # set RLS
            from sqlalchemy import text

            await session.execute(
                text("SELECT set_config('app.user_id', :uid, true)"),
                {"uid": user_id},
            )
            svc = ResumeDeriveService(session)
            try:
                run = await svc.start_run(
                    user_id=UUID(user_id),
                    job_id=UUID(job_id),
                    target_page_count=pages,
                    template_id=template,
                )
            except DeriveError as exc:
                typer.echo(json.dumps({"error": exc.code, "message": exc.message}), err=True)
                return 2

            if not async_mode:
                result = await execute_resume_derive(
                    {}, run_id=str(run.id), user_id=str(run.user_id)
                )
                payload = {"run_id": str(run.id), **result}
            else:
                payload = {"run_id": str(run.id), "status": run.status}

            typer.echo(json.dumps(payload) if json_out else payload)
            return 0

    raise typer.Exit(asyncio.run(_run()))


@app.command("dump-evidence-meta")
def dump_evidence_meta(
    scenario: str = typer.Option(..., "--scenario"),
    measured: int = typer.Option(..., "--measured"),
    allowed: bool = typer.Option(..., "--allowed"),
    out: Path = typer.Option(
        Path("docs/evidence/056-derive-prod-hardening/pages"),
        "--out",
        help="Evidence directory",
    ),
) -> None:
    """Write a JSON stub for REQ-056 page evidence pack (contracts/cli.md)."""
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{scenario}.json"
    from datetime import datetime, timezone

    payload = {
        "scenario_id": scenario,
        "measured_pages": measured,
        "export_allowed": allowed,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "result": "pass" if allowed else "fail",
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    typer.echo(str(path))


if __name__ == "__main__":
    app()
