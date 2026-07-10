"""ARQ task: execute_resume_derive (REQ-055)."""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from app.agents.graphs.resume_derive import run_resume_derive
from app.core.db import get_session_factory
from app.core.ids import new_uuid_v7
from app.modules.resume_derive.metrics import (
    calibrate_rounds,
    derive_duration_seconds,
    derive_runs_total,
)
from app.modules.resumes_v2.models import ResumeV2

logger = logging.getLogger(__name__)


async def execute_resume_derive(
    ctx: dict, *, run_id: str, **kwargs: Any
) -> dict[str, Any]:
    """Load run + root + job, run pipeline, persist derived resume snapshot.

    ``**kwargs`` swallows ARQ framework kwargs (notably ``trace_ctx`` injected
    by ``enqueue_job``), matching ``execute_research_task``.
    """
    _ = kwargs  # reserved for future trace propagation
    started = time.monotonic()
    factory = get_session_factory()
    async with factory() as session:
        from app.modules.jobs.models import Job
        from app.modules.resume_derive.models import ResumeDeriveRun
        from app.modules.resume_derive.repository import ResumeDeriveRepository

        run_uuid = UUID(run_id)
        run = await session.get(ResumeDeriveRun, run_uuid)
        if run is None:
            return {"error": "run_not_found", "run_id": run_id}

        # Bind RLS before any tenant-scoped reads (resumes_v2 / jobs).
        # Must happen before get(root)/get(job); empty app.user_id → uuid "".
        from sqlalchemy import text

        await session.execute(
            text("SELECT set_config('app.user_id', :uid, true)"),
            {"uid": str(run.user_id)},
        )

        run.status = "running"
        run.phase = "parse_jd"
        run.updated_at = datetime.now(timezone.utc)
        await session.commit()

        # Re-bind after commit (SET LOCAL is transaction-scoped).
        await session.execute(
            text("SELECT set_config('app.user_id', :uid, true)"),
            {"uid": str(run.user_id)},
        )

        root = await session.get(ResumeV2, run.root_resume_id)
        job = await session.get(Job, run.job_id)
        if root is None or job is None:
            run.status = "failed"
            run.error_code = "MISSING_INPUT"
            run.error_message = "root or job missing"
            run.finished_at = datetime.now(timezone.utc)
            await session.commit()
            derive_runs_total.labels(status="failed").inc()
            return {"error": "missing_input"}

        state = {
            "run_id": run_id,
            "user_id": str(run.user_id),
            "job_id": str(run.job_id),
            "root_resume_id": str(run.root_resume_id),
            "root_version": int(run.root_version),
            "root_data": root.data or {},
            "jd_text": job.requirements_md or "",
            "job_company": job.company or "",
            "job_position": job.position or "",
            "target_page_count": int(run.target_page_count),
            "template_id": run.template_id,
            "calibrate_round": 0,
        }

        try:
            result = run_resume_derive(state)  # type: ignore[arg-type]
        except Exception as exc:
            logger.exception("execute_resume_derive failed: %s", exc)
            run.status = "failed"
            run.error_code = "LLM_FAILED"
            run.error_message = str(exc)[:500]
            run.finished_at = datetime.now(timezone.utc)
            await session.commit()
            derive_runs_total.labels(status="failed").inc()
            return {"error": str(exc)}

        derived_data = result.get("derived_data") or {}
        page_report = result.get("page_report") or {}
        measured = int(page_report.get("measured") or 0) or None
        status = result.get("status") or "failed"

        derived_id = new_uuid_v7()
        derived = ResumeV2(
            id=derived_id,
            user_id=run.user_id,
            name=f"{job.company}-{job.position}-{run.target_page_count}p",
            slug=f"derived-{str(derived_id)[:8]}",
            tags=["derived"],
            is_public=False,
            is_locked=False,
            password_hash=None,
            data=derived_data,
            version=0,
            resume_kind="derived",
            root_resume_id=root.id,
            job_id=job.id,
            root_version_at_derive=int(run.root_version),
            target_page_count=int(run.target_page_count),
            actual_page_count=measured if status == "succeeded" else measured,
            derive_meta={
                "jd_parse": result.get("jd_parse"),
                "selection_plan": result.get("selection_plan"),
                "takeaway_notes": result.get("takeaway_notes"),
                "suggestions": result.get("suggestions"),
                "supplement_questions": result.get("supplement_questions"),
                "page_report": page_report,
                "unused_materials": result.get("unused_materials"),
            },
        )
        session.add(derived)
        await session.flush()  # ensure resumes_v2 row exists before FK on derive run

        run.derived_resume_id = derived_id
        run.status = status if status in ("succeeded", "needs_guidance", "failed") else "failed"
        run.phase = "done" if run.status == "succeeded" else (result.get("phase") or run.status)
        run.calibrate_round = int(result.get("calibrate_round") or page_report.get("rounds") or 0)
        run.progress_pct = 100 if run.status == "succeeded" else 90
        run.artifacts = {
            "jd_parse": result.get("jd_parse"),
            "takeaway_notes": result.get("takeaway_notes"),
            "page_report": page_report,
            "suggestions": result.get("suggestions"),
        }
        run.error_code = result.get("error_code")
        run.error_message = result.get("error_message")
        run.finished_at = datetime.now(timezone.utc)
        await session.commit()

        derive_runs_total.labels(status=run.status).inc()
        calibrate_rounds.observe(float(run.calibrate_round))
        derive_duration_seconds.observe(time.monotonic() - started)

        return {
            "run_id": run_id,
            "status": run.status,
            "derived_resume_id": str(derived_id),
            "actual_page_count": measured,
        }
