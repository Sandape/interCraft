"""ARQ task: immutable, cancellable resume derive execution (REQ-059)."""
from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select, text

from app.agents.graphs.resume_derive import run_resume_derive_async
from app.core.db import get_session_factory
from app.core.ids import new_uuid_v7
from app.modules.resume_derive.metrics import (
    calibrate_rounds,
    derive_duration_seconds,
    derive_runs_total,
)
from app.modules.resume_derive.models import ResumeDeriveRun
from app.modules.resume_derive.themes import apply_derive_theme
from app.modules.resumes_v2.models import ResumeV2

logger = logging.getLogger(__name__)
_TERMINAL = {"succeeded", "partial_success", "needs_guidance", "failed", "cancelled", "canceled"}


async def _bind_tenant(session: Any, user_id: str) -> None:
    await session.execute(
        text("SELECT set_config('app.user_id', :uid, true)"), {"uid": user_id}
    )


async def execute_resume_derive(
    ctx: dict,
    *,
    run_id: str,
    user_id: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Execute only the input snapshot accepted by the API.

    `user_id` is intentionally carried in the trusted ARQ message so the
    worker can bind PostgreSQL RLS before its first tenant-scoped read.
    """
    _ = (ctx, kwargs)
    if not user_id:
        return {"error": "missing_tenant_context", "run_id": run_id}

    started = time.monotonic()
    factory = get_session_factory()
    async with factory() as session:
        await _bind_tenant(session, user_id)
        run_uuid = UUID(run_id)
        run = await session.get(ResumeDeriveRun, run_uuid)
        if run is None or str(run.user_id) != user_id:
            return {"error": "run_not_found", "run_id": run_id}
        if run.status in _TERMINAL:
            return {
                "run_id": run_id,
                "status": run.status,
                "idempotent_replay": True,
                "derived_resume_id": str(run.derived_resume_id) if run.derived_resume_id else None,
            }
        if run.cancel_requested_at is not None:
            run.status = "cancelled"
            run.finished_at = datetime.now(UTC)
            await session.commit()
            return {"run_id": run_id, "status": "cancelled"}

        run.status = "running"
        run.phase = "load_snapshots"
        run.component_status = {
            **(run.component_status or {}),
            "derived_resume": "running",
        }
        run.updated_at = datetime.now(UTC)
        await session.commit()

        # Commit resets SET LOCAL; bind again before the next tenant read/write.
        await _bind_tenant(session, user_id)
        root_snapshot = dict(run.root_snapshot or {})
        job_snapshot = dict(run.job_snapshot or {})
        if not root_snapshot or not job_snapshot:
            run.status = "failed"
            run.error_code = "MISSING_INPUT_SNAPSHOT"
            run.error_message = "Immutable input snapshot is missing."
            run.finished_at = datetime.now(UTC)
            await session.commit()
            derive_runs_total.labels(status="failed").inc()
            return {"error": "missing_input_snapshot", "run_id": run_id}

        state = {
            "run_id": run_id,
            "user_id": user_id,
            "job_id": str(run.job_id) if run.job_id else None,
            "root_resume_id": str(run.root_resume_id),
            "root_version": int(run.root_version),
            "root_data": root_snapshot.get("data") or {},
            "jd_text": job_snapshot.get("requirements_md") or "",
            "job_company": job_snapshot.get("company") or "",
            "job_position": job_snapshot.get("position") or "",
            "target_page_count": int(run.target_page_count),
            "template_id": run.template_id,
            "calibrate_round": 0,
            "input_fingerprint": run.input_fingerprint,
        }

        try:
            result = await run_resume_derive_async(state)
        except Exception as exc:
            logger.exception(
                "resume_intelligence.run.failed run_id=%s category=graph_failure", run_id
            )
            await _bind_tenant(session, user_id)
            locked = (
                await session.execute(
                    select(ResumeDeriveRun)
                    .where(ResumeDeriveRun.id == run_uuid)
                    .with_for_update()
                    .execution_options(populate_existing=True)
                )
            ).scalar_one_or_none()
            if locked is not None:
                if locked.cancel_requested_at is not None:
                    locked.status = "cancelled"
                    locked.error_code = None
                    locked.error_message = None
                else:
                    locked.status = "failed"
                    locked.error_code = "GRAPH_FAILED"
                    locked.error_message = type(exc).__name__
                locked.finished_at = datetime.now(UTC)
                await session.commit()
            derive_runs_total.labels(status="failed").inc()
            return {"error": "graph_failed", "run_id": run_id}

        await _bind_tenant(session, user_id)
        locked = (
            await session.execute(
                select(ResumeDeriveRun)
                .where(ResumeDeriveRun.id == run_uuid)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        ).scalar_one_or_none()
        if locked is None:
            return {"error": "run_not_found", "run_id": run_id}
        if locked.cancel_requested_at is not None or locked.status in {"cancelled", "canceled"}:
            locked.status = "cancelled"
            locked.phase = "cancelled"
            locked.finished_at = datetime.now(UTC)
            locked.component_status = {
                **(locked.component_status or {}),
                "derived_resume": "skipped",
                "analysis": "skipped",
                "suggestions": "skipped",
            }
            await session.commit()
            derive_runs_total.labels(status="cancelled").inc()
            return {"run_id": run_id, "status": "cancelled"}

        status = str(result.get("status") or "failed")
        if status not in {"succeeded", "partial_success", "needs_guidance"}:
            locked.status = "failed"
            locked.phase = str(result.get("phase") or "failed")
            locked.error_code = str(result.get("error_code") or "DERIVE_FAILED")
            locked.error_message = str(result.get("error_message") or "Validation failed")[:500]
            locked.component_status = {
                **(locked.component_status or {}),
                "derived_resume": "failed",
                "analysis": "skipped",
                "suggestions": "skipped",
            }
            locked.finished_at = datetime.now(UTC)
            await session.commit()
            derive_runs_total.labels(status="failed").inc()
            return {"run_id": run_id, "status": "failed", "error": locked.error_code}

        if locked.job_id is None:
            locked.status = "failed"
            locked.error_code = "JOB_CONTEXT_UNAVAILABLE"
            locked.error_message = "The live job was deleted before publication."
            locked.finished_at = datetime.now(UTC)
            await session.commit()
            return {"run_id": run_id, "status": "failed", "error": locked.error_code}

        derived_data = result.get("derived_data") or {}
        if not isinstance(derived_data, dict) or not derived_data:
            locked.status = "failed"
            locked.error_code = "EMPTY_DERIVED_BODY"
            locked.error_message = "Validated derived body was empty."
            locked.finished_at = datetime.now(UTC)
            await session.commit()
            return {"run_id": run_id, "status": "failed", "error": locked.error_code}
        apply_derive_theme(derived_data, locked.template_id)

        page_report = result.get("page_report") or {}
        measured = int(page_report.get("measured") or 0) or None
        derived_id = new_uuid_v7()
        derived = ResumeV2(
            id=derived_id,
            user_id=locked.user_id,
            name=f"{job_snapshot.get('company') or '岗位'}-{job_snapshot.get('position') or '定制'}-{locked.target_page_count}p",
            slug=f"derived-{str(derived_id)[:8]}",
            tags=["derived"],
            is_public=False,
            is_locked=False,
            password_hash=None,
            data=derived_data,
            version=0,
            resume_kind="derived",
            root_resume_id=locked.root_resume_id,
            job_id=locked.job_id,
            root_version_at_derive=int(locked.root_version),
            target_page_count=int(locked.target_page_count),
            actual_page_count=measured,
            derive_meta={
                "input_fingerprint": locked.input_fingerprint,
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
        await session.flush()

        locked.derived_resume_id = derived_id
        locked.status = status
        locked.phase = "done" if status == "succeeded" else status
        locked.calibrate_round = int(result.get("calibrate_round") or page_report.get("rounds") or 0)
        locked.progress_pct = 100
        locked.artifacts = {
            "jd_parse": result.get("jd_parse"),
            "takeaway_notes": result.get("takeaway_notes"),
            "page_report": page_report,
            "suggestions": result.get("suggestions"),
        }
        locked.component_status = {
            **(locked.component_status or {}),
            "derived_resume": "succeeded",
            "analysis": "pending" if status != "partial_success" else "failed",
            "suggestions": "pending" if status != "partial_success" else "failed",
        }
        locked.error_code = result.get("error_code")
        locked.error_message = result.get("error_message")
        locked.published_at = datetime.now(UTC)
        locked.finished_at = datetime.now(UTC)
        await session.commit()

        # Activation contract: a published derived resume immediately starts
        # its version-bound job-fit analysis. Failure keeps the safe draft as
        # explicit partial success rather than pretending all artifacts exist.
        final_run = locked
        try:
            await _bind_tenant(session, user_id)
            from app.modules.resume_intelligence.service import (
                ResumeIntelligenceService,
            )

            analysis = await ResumeIntelligenceService(session).start_analysis(
                user_id=locked.user_id,
                resume_id=derived_id,
                mode="job_fit",
                client_version=0,
                job_id=locked.job_id,
                force=True,
            )
            await _bind_tenant(session, user_id)
            refreshed = await session.get(ResumeDeriveRun, run_uuid)
            if refreshed is not None:
                final_run = refreshed
                refreshed.analysis_id = analysis.id
                refreshed.component_status = {
                    **(refreshed.component_status or {}),
                    "analysis": "pending",
                    "suggestions": "pending",
                }
                await session.commit()
        except Exception as exc:
            logger.warning(
                "resume_intelligence.analysis.enqueue_failed run_id=%s category=%s",
                run_id,
                type(exc).__name__,
            )
            await session.rollback()
            await _bind_tenant(session, user_id)
            refreshed = await session.get(ResumeDeriveRun, run_uuid)
            if refreshed is not None:
                final_run = refreshed
                refreshed.status = "partial_success"
                refreshed.component_status = {
                    **(refreshed.component_status or {}),
                    "analysis": "failed",
                    "suggestions": "failed",
                }
                refreshed.error_code = "ANALYSIS_ENQUEUE_FAILED"
                await session.commit()

        derive_runs_total.labels(status=final_run.status).inc()
        calibrate_rounds.observe(float(final_run.calibrate_round))
        derive_duration_seconds.observe(time.monotonic() - started)
        logger.info(
            "resume_intelligence.run.published run_id=%s status=%s derived_resume_id=%s",
            run_id,
            final_run.status,
            derived_id,
        )
        return {
            "run_id": run_id,
            "status": final_run.status,
            "derived_resume_id": str(derived_id),
            "actual_page_count": measured,
        }
