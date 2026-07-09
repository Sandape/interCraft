"""Research module CLI commands (REQ-053 FR-025)."""
from __future__ import annotations

import asyncio
import json
from uuid import UUID

import typer

cli = typer.Typer(help="Interview Research (REQ-053)")


@cli.command("trigger-research")
def trigger_research(
    job_id: str = typer.Option(..., "--job-id", help="UUID of job to research"),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """REQ-053 FR-025(b): Manually trigger a research task for debugging."""
    uid = UUID(job_id)

    async def _run() -> None:
        from app.core.db import get_session_factory
        from app.modules.jobs.repository import JobRepository
        from app.modules.research.repository import ResearchTaskRepository
        from app.modules.research.service import ResearchService

        factory = get_session_factory()
        async with factory() as session:
            job_repo = JobRepository(session)
            task_repo = ResearchTaskRepository(session)
            svc = ResearchService(session)

            # Find job (without RLS — admin/debug path; user_id is fetched from job)
            from sqlalchemy import select
            from app.modules.jobs.models import Job
            res = await session.execute(select(Job).where(Job.id == uid))
            job = res.scalar_one_or_none()
            if job is None:
                result = {"error": "job_not_found", "job_id": str(uid)}
            elif job.interview_time is None:
                result = {"error": "no_interview_time", "job_id": str(uid)}
            else:
                task_id = await task_repo.create(
                    job_id=job.id,
                    user_id=job.user_id,
                    interview_time=job.interview_time,
                )
                # Execute synchronously (don't enqueue to ARQ from CLI)
                outcome = await svc.execute_research_task(task_id)
                result = {"job_id": str(uid), "task_id": str(task_id), "outcome": outcome}

            if json_out:
                typer.echo(json.dumps(result, indent=2, ensure_ascii=False, default=str))
            else:
                typer.echo(str(result))

    asyncio.run(_run())


@cli.command("research-stats")
def research_stats(
    user_id: str | None = typer.Option(None, "--user-id", help="Filter by user UUID"),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """REQ-053 FR-025(c): View research task statistics."""
    uid = UUID(user_id) if user_id else None

    async def _run() -> None:
        from app.core.db import get_session_factory
        from app.modules.research.repository import ResearchTaskRepository

        factory = get_session_factory()
        async with factory() as session:
            repo = ResearchTaskRepository(session)
            if uid:
                stats = await repo.stats_by_user(uid)
            else:
                # Global stats — aggregate across all users
                from sqlalchemy import text
                res = await session.execute(
                    text("SELECT status, COUNT(*) FROM interview_research_tasks GROUP BY status")
                )
                rows = res.fetchall()
                by_status = {r[0]: r[1] for r in rows}
                stats = {
                    "total_tasks": sum(by_status.values()),
                    "by_status": by_status,
                    "total_reports": 0,
                    "average_rating": None,
                }

            if json_out:
                typer.echo(json.dumps(stats, indent=2, ensure_ascii=False, default=str))
            else:
                typer.echo(str(stats))

    asyncio.run(_run())


__all__ = ["cli"]