"""JobService — business logic with task trigger (DEC-P2-6)."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import JOB_TRANSITIONS, JOB_STATUS_CN
from app.modules.activities.repository import ActivityRepository
from app.modules.jobs.models import Job
from app.modules.jobs.repository import JobRepository
from app.modules.tasks.repository import TaskRepository


class JobService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = JobRepository(session)
        self.task_repo = TaskRepository(session)
        self.activity_repo = ActivityRepository(session)

    async def list(self, user_id: UUID, **filters) -> list:
        return await self.repo.list(user_id, **filters)

    async def get(self, id: UUID, user_id: UUID) -> Job:
        job = await self.repo.get(id, user_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        return job

    async def create(self, user_id: UUID, data: dict) -> Job:
        now = datetime.now(timezone.utc)
        job = Job(
            user_id=user_id,
            company=data["company"],
            position=data["position"],
            jd_url=data.get("jd_url"),
            branch_id=data.get("branch_id"),
            notes_md=data.get("notes_md"),
            # 019 — extended job fields
            base_location=data.get("base_location") or "",
            requirements_md=data.get("requirements_md"),
            employment_type=data.get("employment_type") or "unspecified",
            salary_range_text=data.get("salary_range_text"),
            headcount=data.get("headcount"),
            status="applied",
            status_history=[{"from": None, "to": "applied", "at": now.isoformat(), "note": ""}],
            last_status_changed_at=now,
        )
        job = await self.repo.create(job)

        # Trigger interview_prep task (DEC-P2-6)
        await self.task_repo.find_or_create(
            user_id, "interview_prep",
            f"准备 {job.company} · {job.position} 面试",
            related_entity_type="job", related_entity_id=job.id,
        )

        # Log activity
        await self._log(user_id, "job_created", {"job_id": str(job.id), "company": job.company, "position": job.position})

        return job

    async def patch(self, id: UUID, user_id: UUID, data: dict) -> Job:
        job = await self.get(id, user_id)
        # 019 — when binding a branch, verify it belongs to the same user.
        if "branch_id" in data and data["branch_id"] is not None:
            from app.modules.resumes.repository import ResumeRepository
            branch_repo = ResumeRepository(self.session)
            branch = await branch_repo.get(data["branch_id"], user_id=user_id)
            if branch is None:
                raise HTTPException(
                    status_code=404,
                    detail="Branch not found or not owned by current user",
                )
        return await self.repo.patch(id, user_id, data) or job

    async def update_status(self, id: UUID, user_id: UUID, to: str, note: str = "") -> Job:
        job = await self.get(id, user_id)
        old_status = job.status

        # Validate transition
        allowed = JOB_TRANSITIONS.get(old_status, set())
        if to not in allowed:
            raise HTTPException(
                status_code=409,
                detail={
                    "error": {
                        "code": "invalid_status_transition",
                        "message": f"Cannot transition from '{old_status}' to '{to}'.",
                        "details": {"from": old_status, "to": to},
                    }
                },
            )

        now = datetime.now(timezone.utc)
        history = list(job.status_history or [])
        history.append({"from": old_status, "to": to, "at": now.isoformat(), "note": note})

        job.status = to
        job.status_history = history
        job.last_status_changed_at = now

        # Task triggers
        if to in ("rejected", "withdrawn"):
            task = await self.task_repo.find_by_entity(user_id, "interview_prep", job.id)
            if task:
                await self.task_repo.patch(task.id, user_id, {"status": "archived"})
        else:
            task = await self.task_repo.find_by_entity(user_id, "interview_prep", job.id)
            status_cn = JOB_STATUS_CN.get(to, to)
            if task:
                await self.task_repo.patch(
                    task.id, user_id,
                    {"title": f"准备 {job.company} · {job.position} 面试 · {status_cn}"},
                )

        await self._log(user_id, "job_status_changed", {
            "job_id": str(job.id), "company": job.company, "position": job.position,
            "from_status": old_status, "to_status": to,
        })

        await self.session.flush()
        await self.session.refresh(job)
        return job

    async def delete(self, id: UUID, user_id: UUID) -> None:
        job = await self.get(id, user_id)
        # Archive associated task
        task = await self.task_repo.find_by_entity(user_id, "interview_prep", job.id)
        if task:
            await self.task_repo.patch(task.id, user_id, {"status": "archived"})
        await self.repo.soft_delete(id, user_id)

    async def stats(self, user_id: UUID) -> dict:
        return await self.repo.stats(user_id)

    async def timeline(self, id: UUID, user_id: UUID) -> dict:
        job = await self.get(id, user_id)
        import json
        return {"job_id": job.id, "status_history": list(job.status_history or [])}

    async def _log(self, user_id: UUID, type: str, payload: dict) -> None:
        from app.modules.activities.models import Activity
        activity = Activity(user_id=user_id, type=type, actor_type="user", payload_json=payload)
        await self.activity_repo.log(activity)


__all__ = ["JobService"]
