"""HTTP API for REQ-059 immutable resume intelligence."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Header, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import db_session_user_dep, get_current_user_id
from app.modules.resume_intelligence.repository import ResumeIntelligenceRepository
from app.modules.resume_intelligence.schemas import (
    AnalysisRunIn,
    ApplyBatchIn,
    ConfirmSupplementIn,
    FeedbackIn,
    PreviewBatchIn,
    SuggestionStatusIn,
    UndoChangeSetIn,
)
from app.modules.resume_intelligence.service import (
    IntelligenceError,
    ResumeIntelligenceService,
)
from app.modules.resumes_v2.repository import ResumeV2Repository

router = APIRouter(prefix="/v2", tags=["resume-intelligence"])


def _error(exc: IntelligenceError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status,
        content={
            "code": exc.code,
            "message": exc.message,
            "retryable": exc.retryable,
            "details": exc.details,
        },
    )


def _not_found(message: str) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={"code": "NOT_FOUND", "message": message, "retryable": False},
    )


@router.post(
    "/resumes/{resume_id}/intelligence-runs",
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_analysis(
    resume_id: UUID,
    body: AnalysisRunIn,
    session: AsyncSession = Depends(db_session_user_dep),
    user_id: UUID = Depends(get_current_user_id),
):
    service = ResumeIntelligenceService(session)
    try:
        row = await service.start_analysis(
            user_id=user_id,
            resume_id=resume_id,
            mode=body.mode.value,
            client_version=body.client_version,
            job_id=body.job_id,
            force=body.force,
        )
        return ResumeIntelligenceService.start_response_payload(row)
    except IntelligenceError as exc:
        return _error(exc)


@router.get("/resume-intelligence/runs/{analysis_id}")
async def get_analysis_run(
    analysis_id: UUID,
    session: AsyncSession = Depends(db_session_user_dep),
    user_id: UUID = Depends(get_current_user_id),
):
    row = await ResumeIntelligenceRepository(session).get_analysis(
        analysis_id, user_id=user_id
    )
    if row is None:
        return _not_found("Run not found.")
    return ResumeIntelligenceService.run_status_payload(row)


@router.post("/resume-intelligence/runs/{run_id}/cancel")
async def cancel_run(
    run_id: UUID,
    session: AsyncSession = Depends(db_session_user_dep),
    user_id: UUID = Depends(get_current_user_id),
):
    try:
        return await ResumeIntelligenceService(session).cancel_run(
            user_id=user_id, run_id=run_id
        )
    except IntelligenceError as exc:
        return _error(exc)


@router.get("/resumes/{resume_id}/analyses")
async def list_analyses(
    resume_id: UUID,
    mode: str | None = None,
    session: AsyncSession = Depends(db_session_user_dep),
    user_id: UUID = Depends(get_current_user_id),
):
    resume = await ResumeV2Repository(session).get(resume_id, user_id=user_id)
    if resume is None:
        return _not_found("Resume not found.")
    rows = await ResumeIntelligenceRepository(session).list_analyses(
        resume_id, user_id=user_id, mode=mode
    )
    service = ResumeIntelligenceService(session)
    return {"items": [service.analysis_payload(row, current_version=resume.version) for row in rows]}


@router.get("/resumes/{resume_id}/analyses/current")
async def current_analysis(
    resume_id: UUID,
    mode: str,
    session: AsyncSession = Depends(db_session_user_dep),
    user_id: UUID = Depends(get_current_user_id),
):
    resume = await ResumeV2Repository(session).get(resume_id, user_id=user_id)
    if resume is None:
        return _not_found("Resume not found.")
    rows = await ResumeIntelligenceRepository(session).list_analyses(
        resume_id, user_id=user_id, mode=mode
    )
    if not rows:
        return _not_found("No analysis.")
    return ResumeIntelligenceService.analysis_payload(rows[0], current_version=resume.version)


@router.get("/analyses/{analysis_id}")
async def get_analysis(
    analysis_id: UUID,
    session: AsyncSession = Depends(db_session_user_dep),
    user_id: UUID = Depends(get_current_user_id),
):
    row = await ResumeIntelligenceRepository(session).get_analysis(
        analysis_id, user_id=user_id
    )
    if row is None:
        return _not_found("Analysis not found.")
    resume = await ResumeV2Repository(session).get(row.resume_id, user_id=user_id)
    return ResumeIntelligenceService.analysis_payload(
        row, current_version=resume.version if resume else None
    )


@router.get("/analyses/{analysis_id}/compare")
async def compare_analysis(
    analysis_id: UUID,
    target_analysis_id: UUID,
    session: AsyncSession = Depends(db_session_user_dep),
    user_id: UUID = Depends(get_current_user_id),
):
    try:
        return await ResumeIntelligenceService(session).compare_analyses(
            user_id=user_id,
            before_analysis_id=analysis_id,
            after_analysis_id=target_analysis_id,
        )
    except IntelligenceError as exc:
        return _error(exc)


@router.post(
    "/analyses/{analysis_id}/refresh",
    status_code=status.HTTP_202_ACCEPTED,
)
async def refresh_analysis(
    analysis_id: UUID,
    session: AsyncSession = Depends(db_session_user_dep),
    user_id: UUID = Depends(get_current_user_id),
):
    """Force a new analysis from latest snapshots without mutating history."""
    repo = ResumeIntelligenceRepository(session)
    row = await repo.get_analysis(analysis_id, user_id=user_id)
    if row is None:
        return _not_found("Analysis not found.")
    resume = await ResumeV2Repository(session).get(row.resume_id, user_id=user_id)
    if resume is None:
        return _not_found("Resume not found.")
    try:
        refreshed = await ResumeIntelligenceService(session).start_analysis(
            user_id=user_id,
            resume_id=row.resume_id,
            mode=row.mode,
            client_version=int(resume.version),
            job_id=row.job_id,
            force=True,
        )
        return {
            "run_id": str(refreshed.id),
            "analysis_id": str(refreshed.id),
            "status": refreshed.status,
            "baseline_analysis_id": str(analysis_id),
            "status_url": f"/api/v1/v2/resume-intelligence/runs/{refreshed.id}",
        }
    except IntelligenceError as exc:
        return _error(exc)


@router.get("/analyses/{analysis_id}/suggestions")
async def list_analysis_suggestions(
    analysis_id: UUID,
    session: AsyncSession = Depends(db_session_user_dep),
    user_id: UUID = Depends(get_current_user_id),
):
    repo = ResumeIntelligenceRepository(session)
    analysis = await repo.get_analysis(analysis_id, user_id=user_id)
    if analysis is None:
        return _not_found("Analysis not found.")
    rows = await repo.list_suggestions(
        user_id=user_id, resume_id=analysis.resume_id, analysis_id=analysis.id
    )
    return {"items": [ResumeIntelligenceService.suggestion_payload(row) for row in rows]}


@router.post(
    "/analyses/{analysis_id}/suggestions/regenerate",
    status_code=status.HTTP_202_ACCEPTED,
)
async def regenerate_suggestions(
    analysis_id: UUID,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    session: AsyncSession = Depends(db_session_user_dep),
    user_id: UUID = Depends(get_current_user_id),
):
    try:
        return await ResumeIntelligenceService(session).regenerate_suggestions(
            user_id=user_id,
            analysis_id=analysis_id,
            idempotency_key=idempotency_key,
        )
    except IntelligenceError as exc:
        return _error(exc)


@router.get("/resumes/{resume_id}/suggestions")
async def list_resume_suggestions(
    resume_id: UUID,
    analysis_id: UUID,
    session: AsyncSession = Depends(db_session_user_dep),
    user_id: UUID = Depends(get_current_user_id),
):
    repo = ResumeIntelligenceRepository(session)
    analysis = await repo.get_analysis(analysis_id, user_id=user_id)
    if analysis is None or analysis.resume_id != resume_id:
        return _not_found("Analysis not found.")
    rows = await repo.list_suggestions(
        user_id=user_id, resume_id=resume_id, analysis_id=analysis_id
    )
    return {"items": [ResumeIntelligenceService.suggestion_payload(row) for row in rows]}


@router.post("/resumes/{resume_id}/suggestions/preview-batch")
async def preview_suggestion_batch(
    resume_id: UUID,
    body: PreviewBatchIn,
    session: AsyncSession = Depends(db_session_user_dep),
    user_id: UUID = Depends(get_current_user_id),
):
    try:
        return await ResumeIntelligenceService(session).preview_suggestions(
            user_id=user_id,
            resume_id=resume_id,
            analysis_id=body.analysis_id,
            suggestion_ids=body.suggestion_ids,
            client_version=body.client_version,
        )
    except IntelligenceError as exc:
        return _error(exc)


@router.patch("/suggestions/{suggestion_id}/status")
async def patch_suggestion_status(
    suggestion_id: UUID,
    body: SuggestionStatusIn,
    session: AsyncSession = Depends(db_session_user_dep),
    user_id: UUID = Depends(get_current_user_id),
):
    try:
        row = await ResumeIntelligenceService(session).update_suggestion_status(
            user_id=user_id,
            suggestion_id=suggestion_id,
            action=body.action,
            reason=body.reason,
        )
        return ResumeIntelligenceService.suggestion_payload(row)
    except IntelligenceError as exc:
        return _error(exc)


@router.post("/resume-intelligence/feedback", status_code=status.HTTP_201_CREATED)
async def submit_feedback(
    body: FeedbackIn,
    session: AsyncSession = Depends(db_session_user_dep),
    user_id: UUID = Depends(get_current_user_id),
):
    try:
        row = await ResumeIntelligenceService(session).submit_feedback(
            user_id=user_id,
            analysis_id=body.analysis_id,
            suggestion_id=body.suggestion_id,
            change_set_id=body.change_set_id,
            category=body.category,
            comment=body.comment,
        )
        return {"id": str(row.id), "analysis_id": str(row.analysis_id), "category": row.category}
    except IntelligenceError as exc:
        return _error(exc)


@router.post("/resume-intelligence/supplements/confirm")
async def confirm_supplement(
    body: ConfirmSupplementIn,
    session: AsyncSession = Depends(db_session_user_dep),
    user_id: UUID = Depends(get_current_user_id),
):
    try:
        return await ResumeIntelligenceService(session).confirm_supplement(
            user_id=user_id,
            resume_id=body.resume_id,
            question_id=body.question_id,
            text=body.text,
            scope=body.scope,
            confirmed=body.confirmed,
        )
    except IntelligenceError as exc:
        return _error(exc)


@router.post("/resumes/{resume_id}/suggestions/apply-batch")
async def apply_suggestion_batch(
    resume_id: UUID,
    body: ApplyBatchIn,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    session: AsyncSession = Depends(db_session_user_dep),
    user_id: UUID = Depends(get_current_user_id),
):
    try:
        resume, change_set = await ResumeIntelligenceService(session).apply_suggestions(
            user_id=user_id,
            resume_id=resume_id,
            preview_token=body.preview_token,
            client_version=body.client_version,
            idempotency_key=idempotency_key,
        )
        return {
            "resume": {"id": str(resume.id), "version": resume.version, "data": resume.data},
            "change_set_id": str(change_set.id),
            "applied_suggestion_ids": change_set.suggestion_ids,
            "analysis_stale": True,
            "export_gate_stale": True,
            "evidence": getattr(change_set, "_evidence", None),
            "base_resume_version": change_set.base_resume_version,
            "result_resume_version": change_set.result_resume_version,
        }
    except IntelligenceError as exc:
        return _error(exc)


@router.post("/suggestion-change-sets/{change_set_id}/undo")
async def undo_suggestion_change_set(
    change_set_id: UUID,
    body: UndoChangeSetIn,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    session: AsyncSession = Depends(db_session_user_dep),
    user_id: UUID = Depends(get_current_user_id),
):
    try:
        resume, undo = await ResumeIntelligenceService(session).undo_change_set(
            user_id=user_id,
            change_set_id=change_set_id,
            client_version=body.client_version,
            idempotency_key=idempotency_key,
        )
        return {
            "resume": {"id": str(resume.id), "version": resume.version, "data": resume.data},
            "change_set_id": str(undo.id),
            "applied_suggestion_ids": undo.suggestion_ids,
            "analysis_stale": True,
            "export_gate_stale": True,
            "evidence": getattr(undo, "_evidence", None),
            "base_resume_version": undo.base_resume_version,
            "result_resume_version": undo.result_resume_version,
        }
    except IntelligenceError as exc:
        return _error(exc)
