"""JobService — business logic with task trigger (DEC-P2-6)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import INTERVIEW_STATUSES, JOB_TRANSITIONS, JOB_STATUS_CN
from app.modules.activities.repository import ActivityRepository
from app.modules.jobs.models import Job
from app.modules.jobs.repository import JobRepository
from app.modules.tasks.repository import TaskRepository

# REQ-053: Clock-skew tolerance for "future time" validation (FR-008).
INTERVIEW_TIME_FUTURE_TOLERANCE = timedelta(minutes=5)


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
        await self._invalidate_dashboard(user_id)

        return job

    async def patch(self, id: UUID, user_id: UUID, data: dict) -> Job:
        job = await self.get(id, user_id)
        # 019 — when binding a branch, verify it belongs to the same user.
        if "branch_id" in data and data["branch_id"] is not None:
            from app.modules.resumes.repository import ResumeRepository
            from app.modules.resumes_v2.repository import ResumeV2Repository

            branch_repo = ResumeRepository(self.session)
            branch = await branch_repo.get(data["branch_id"], user_id=user_id)
            if branch is None:
                resume_v2_repo = ResumeV2Repository(self.session)
                branch = await resume_v2_repo.get(data["branch_id"], user_id=user_id)
            if branch is None:
                raise HTTPException(
                    status_code=404,
                    detail="Branch not found or not owned by current user",
                )
        # REQ-053: interview_time validation in patch path (FR-008).
        if "interview_time" in data:
            self._validate_interview_time(
                data["interview_time"],
                current_status=job.status,
            )
        patched = await self.repo.patch(id, user_id, data) or job
        await self._invalidate_dashboard(user_id)
        return patched

    async def update_status(
        self,
        id: UUID,
        user_id: UUID,
        to: str,
        note: str = "",
        interview_time: datetime | None = None,
    ) -> Job:
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

        # REQ-053: FR-003 — interview_time required for interview-round states.
        if to in INTERVIEW_STATUSES:
            if interview_time is None:
                raise HTTPException(
                    status_code=422,
                    detail="推进到面试轮次需要设置面试时间",
                )
            self._validate_interview_time(interview_time, current_status=to)
        elif interview_time is not None:
            # FR-008: disallow interview_time on non-interview transitions
            raise HTTPException(
                status_code=422,
                detail="非面试轮次不能设置面试时间",
            )

        now = datetime.now(timezone.utc)
        history = list(job.status_history or [])
        history.append({"from": old_status, "to": to, "at": now.isoformat(), "note": note})

        job.status = to
        job.status_history = history
        job.last_status_changed_at = now
        # REQ-053: maintain interview_time alongside status. Set on entry to
        # interview-round states; clear on terminal states.
        if to in INTERVIEW_STATUSES:
            job.interview_time = interview_time
        elif to in ("failed", "passed"):
            job.interview_time = None

        # Task triggers
        if to in ("failed",):
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

        # REQ-053 FR-011: cancel pending research tasks when interview_time changes
        # or status moves away from interview rounds. The research module is
        # optional; if not importable (during initial migration), skip silently.
        try:
            from app.modules.research.repository import ResearchTaskRepository
            research_repo = ResearchTaskRepository(self.session)
            await research_repo.cancel_pending_for_job(job.id)
        except Exception:
            # Research module not yet deployed — no tasks to cancel.
            pass

        await self.session.flush()
        await self.session.refresh(job)
        await self._invalidate_dashboard(user_id)
        return job

    async def delete(self, id: UUID, user_id: UUID) -> None:
        job = await self.get(id, user_id)
        # Archive associated task
        task = await self.task_repo.find_by_entity(user_id, "interview_prep", job.id)
        if task:
            await self.task_repo.patch(task.id, user_id, {"status": "archived"})
        # REQ-053: cancel pending research tasks on delete
        try:
            from app.modules.research.repository import ResearchTaskRepository
            research_repo = ResearchTaskRepository(self.session)
            await research_repo.cancel_pending_for_job(job.id)
        except Exception:
            pass
        await self.repo.soft_delete(id, user_id)
        await self._invalidate_dashboard(user_id)

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

    @staticmethod
    async def _invalidate_dashboard(user_id: UUID) -> None:
        try:
            from app.modules.dashboard.cache import cache_invalidate

            await cache_invalidate(user_id)
        except Exception:
            pass

    @staticmethod
    def _validate_interview_time(
        value: datetime, *, current_status: str | None = None
    ) -> None:
        """REQ-053 FR-008: interview_time must be a future time (5-min tolerance)."""
        # Normalize to UTC
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        threshold = datetime.now(timezone.utc) - INTERVIEW_TIME_FUTURE_TOLERANCE
        if value < threshold:
            raise HTTPException(
                status_code=422,
                detail="面试时间必须是将来时间",
            )
        # FR-008(c): interview_time requires an interview-round status
        if current_status is not None and current_status not in INTERVIEW_STATUSES:
            raise HTTPException(
                status_code=422,
                detail="请先将岗位状态推进到面试轮次",
            )


__all__ = ["JobService", "INTERVIEW_TIME_FUTURE_TOLERANCE"]
