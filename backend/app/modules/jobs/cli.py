"""Job tracking CLI."""
from __future__ import annotations

import asyncio
import json
from uuid import UUID

import typer

cli = typer.Typer(help="Job tracking (M10)")


@cli.command("list")
def list_jobs(
    user_id: str = typer.Option(..., "--user-id", help="UUID of user"),
    status: str | None = typer.Option(None, "--status"),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    uid = UUID(user_id)
    async def _run() -> None:
        from app.core.db import get_session_factory
        from app.modules.jobs.repository import JobRepository
        factory = get_session_factory()
        async with factory() as session:
            repo = JobRepository(session)
            items = await repo.list(uid, status=status)
            if json_out:
                out = [{"id": str(j.id), "company": j.company, "position": j.position, "status": j.status} for j in items]
                typer.echo(json.dumps(out, indent=2, ensure_ascii=False))
            else:
                for j in items:
                    typer.echo(f"  [{j.status}] {j.company} · {j.position}")
    asyncio.run(_run())


@cli.command("replay")
def replay(
    user_id: str = typer.Option(..., "--user-id", help="UUID of user"),
    scenario: str = typer.Option("lifecycle", "--scenario", help="Scenario: lifecycle | status-machine | stats"),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Replay idempotent job lifecycle scenarios for observability (Constitution V)."""
    uid = UUID(user_id)
    async def _run() -> None:
        from app.core.db import get_session_factory
        from app.modules.jobs.repository import JobRepository
        from app.modules.jobs.service import JobService
        from app.modules.tasks.service import TaskService
        from app.modules.activities.service import ActivityService

        factory = get_session_factory()
        async with factory() as session:
            job_repo = JobRepository(session)
            task_svc = TaskService(session)
            activity_svc = ActivityService(session)
            job_svc = JobService(session, job_repo, task_svc, activity_svc)

            if scenario == "lifecycle":
                job = await job_svc.create(uid, company="Replay Corp", position="Replay Role")
                job = await job_svc.update_status(uid, job.id, "screening")
                job = await job_svc.update_status(uid, job.id, "interview")
                job = await job_svc.update_status(uid, job.id, "offer")
                result = {"job_id": str(job.id), "final_status": job.status, "status_history": job.status_history}
            elif scenario == "status-machine":
                job = await job_svc.create(uid, company="SM Corp", position="SM Role")
                try:
                    await job_svc.update_status(uid, job.id, "offer")  # illegal: applied → offer
                    result = {"error": "expected 409, got success"}
                except Exception as exc:
                    result = {"expected_409": True, "detail": str(exc)}
            elif scenario == "stats":
                counts = await job_repo.stats(uid)
                result = {"counts": counts}
            else:
                result = {"error": f"Unknown scenario: {scenario}"}

            if json_out:
                typer.echo(json.dumps(result, indent=2, ensure_ascii=False, default=str))
            else:
                typer.echo(str(result))
    asyncio.run(_run())


__all__ = ["cli"]
