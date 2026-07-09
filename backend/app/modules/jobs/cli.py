"""Job tracking CLI."""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from uuid import UUID

import typer
from sqlalchemy import text

cli = typer.Typer(help="Job tracking (M10)")


# REQ-053: Old -> New status mapping for the state model migration.
OLD_TO_NEW_STATUS: dict[str, str] = {
    "applied": "applied",      # no change
    "test": "test",            # no change
    "oa": "interview_1",
    "hr": "interview_2",
    "offer": "passed",
    "rejected": "failed",
    "withdrawn": "failed",
}


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


@cli.command("migrate-status")
def migrate_status(
    dry_run: bool = typer.Option(True, "--dry-run/--execute", help="Preview (dry-run) vs execute the migration"),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """REQ-053: Migrate job.status and status_history from old 7-state model to new 7-state model.

    Old statuses: applied, test, oa, hr, offer, rejected, withdrawn
    New statuses: applied, test, interview_1, interview_2, interview_3, failed, passed

    Mapping:
      - oa         -> interview_1
      - hr         -> interview_2
      - offer      -> passed
      - rejected   -> failed    (history.note preserves "原状态: rejected")
      - withdrawn  -> failed    (history.note preserves "原状态: withdrawn")
    """
    async def _run() -> None:
        from app.core.db import get_session_factory
        factory = get_session_factory()
        async with factory() as session:
            # Fetch all jobs
            result = await session.execute(
                text(
                    """SELECT id, company, position, status, status_history
                    FROM jobs WHERE deleted_at IS NULL
                    ORDER BY created_at"""
                )
            )
            rows = result.fetchall()

            # Compute planned changes
            planned: list[dict] = []
            for r in rows:
                old_status = r[3]
                new_status = OLD_TO_NEW_STATUS.get(old_status)
                if new_status is None:
                    # Unknown status (already migrated or unexpected)
                    continue
                if new_status == old_status:
                    continue
                # Transform status_history: replace from/to values, preserve original in note
                new_history = []
                for entry in (r[4] or []):
                    e_from = OLD_TO_NEW_STATUS.get(entry.get("from"), entry.get("from"))
                    e_to = OLD_TO_NEW_STATUS.get(entry.get("to"), entry.get("to"))
                    note = entry.get("note", "") or ""
                    if entry.get("to") in ("rejected", "withdrawn") and "原状态" not in note:
                        note = f"{note} 原状态: {entry.get('to')}".strip()
                    new_entry = dict(entry)
                    new_entry["from"] = e_from
                    new_entry["to"] = e_to
                    if note:
                        new_entry["note"] = note
                    new_history.append(new_entry)
                planned.append(
                    {
                        "job_id": str(r[0]),
                        "company": r[1],
                        "position": r[2],
                        "old_status": old_status,
                        "new_status": new_status,
                        "history_changes": len(new_history),
                    }
                )

            summary = {
                "dry_run": dry_run,
                "total_jobs_scanned": len(rows),
                "jobs_to_migrate": len(planned),
                "planned": planned,
            }

            # If execute, apply changes within a transaction
            if not dry_run and planned:
                for p in planned:
                    # Compute the matching transformed history again (idempotent)
                    row_result = await session.execute(
                        text("SELECT status_history FROM jobs WHERE id = :jid"),
                        {"jid": p["job_id"]},
                    )
                    hist_row = row_result.fetchone()
                    new_history = []
                    for entry in (hist_row[0] if hist_row else []) or []:
                        e_from = OLD_TO_NEW_STATUS.get(entry.get("from"), entry.get("from"))
                        e_to = OLD_TO_NEW_STATUS.get(entry.get("to"), entry.get("to"))
                        note = entry.get("note", "") or ""
                        if entry.get("to") in ("rejected", "withdrawn") and "原状态" not in note:
                            note = f"{note} 原状态: {entry.get('to')}".strip()
                        new_entry = dict(entry)
                        new_entry["from"] = e_from
                        new_entry["to"] = e_to
                        if note:
                            new_entry["note"] = note
                        new_history.append(new_entry)

                    await session.execute(
                        text(
                            """UPDATE jobs
                            SET status = :new_status, status_history = CAST(:hist AS jsonb)
                            WHERE id = :jid"""
                        ),
                        {
                            "new_status": p["new_status"],
                            "hist": json.dumps(new_history, ensure_ascii=False),
                            "jid": p["job_id"],
                        },
                    )
                await session.commit()

            if json_out:
                typer.echo(json.dumps(summary, indent=2, ensure_ascii=False, default=str))
            else:
                typer.echo(
                    f"{'[DRY-RUN] ' if dry_run else '[EXECUTED] '}"
                    f"scanned={summary['total_jobs_scanned']} "
                    f"to_migrate={summary['jobs_to_migrate']}"
                )
                for p in planned:
                    typer.echo(
                        f"  {p['old_status']:>10} -> {p['new_status']:<11}  {p['company']} · {p['position']}  ({p['job_id']})"
                    )
    asyncio.run(_run())


__all__ = ["cli", "OLD_TO_NEW_STATUS"]
