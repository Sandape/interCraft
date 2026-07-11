"""FastAPI routes for resume derive (REQ-055)."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Header, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import db_session_user_dep, get_current_user_id
from app.modules.resume_derive.schemas import (
    DeriveRunAcceptedOut,
    DeriveRunOut,
    DeriveStartIn,
    ExportGateOut,
    ResumeGuidanceIn,
    SuggestionApplyIn,
    SuggestionPreviewIn,
    SupplementIn,
)
from app.modules.resume_derive.service import DeriveError, ResumeDeriveService

router = APIRouter(prefix="/v2", tags=["resume-derive"])


def _err(exc: DeriveError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status,
        content={"error": exc.code, "message": exc.message},
    )


@router.get("/resumes/root")
async def get_root_resume(
    session: AsyncSession = Depends(db_session_user_dep),
    user_id: UUID = Depends(get_current_user_id),
):
    svc = ResumeDeriveService(session)
    row = await svc.get_root(user_id)
    if row is None:
        return JSONResponse(status_code=404, content={"error": "NOT_FOUND", "message": "No root resume"})
    return _resume_payload(row)


@router.post("/resumes/root", status_code=status.HTTP_201_CREATED)
async def create_root_resume(
    body: dict,
    session: AsyncSession = Depends(db_session_user_dep),
    user_id: UUID = Depends(get_current_user_id),
):
    svc = ResumeDeriveService(session)
    try:
        row = await svc.create_root(
            user_id=user_id,
            name=str(body.get("name") or "根简历"),
            slug=str(body.get("slug") or "root-resume"),
            data=body.get("data"),
        )
        await session.commit()
        return _resume_payload(row)
    except DeriveError as exc:
        return _err(exc)


@router.post("/resumes/{resume_id}/promote-root")
async def promote_root(
    resume_id: UUID,
    session: AsyncSession = Depends(db_session_user_dep),
    user_id: UUID = Depends(get_current_user_id),
):
    svc = ResumeDeriveService(session)
    try:
        row = await svc.promote_to_root(user_id=user_id, source_id=resume_id)
        await session.commit()
        return _resume_payload(row)
    except DeriveError as exc:
        return _err(exc)


@router.post("/resumes/derive", status_code=status.HTTP_202_ACCEPTED)
async def start_derive(
    body: DeriveStartIn,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    session: AsyncSession = Depends(db_session_user_dep),
    user_id: UUID = Depends(get_current_user_id),
):
    svc = ResumeDeriveService(session)
    try:
        run = await svc.start_run(
            user_id=user_id,
            job_id=body.job_id,
            target_page_count=int(body.target_page_count),
            template_id=body.template_id,
            root_resume_id=body.root_resume_id,
            idempotency_key=idempotency_key,
        )
        return ResumeDeriveService.start_response_payload(run)
    except DeriveError as exc:
        return _err(exc)


@router.get("/resumes/derive-runs/{run_id}")
async def get_derive_run(
    run_id: UUID,
    session: AsyncSession = Depends(db_session_user_dep),
    user_id: UUID = Depends(get_current_user_id),
):
    svc = ResumeDeriveService(session)
    try:
        run = await svc.get_run(run_id, user_id=user_id)
        return ResumeDeriveService.status_response_payload(run)
    except DeriveError as exc:
        return _err(exc)


@router.post("/resumes/derive-runs/{run_id}")
async def cancel_derive_run(
    run_id: UUID,
    session: AsyncSession = Depends(db_session_user_dep),
    user_id: UUID = Depends(get_current_user_id),
):
    svc = ResumeDeriveService(session)
    try:
        run = await svc.cancel_run(run_id, user_id=user_id)
        return ResumeDeriveService.status_response_payload(run)
    except DeriveError as exc:
        return _err(exc)


@router.post("/resumes/derive-runs/{run_id}/resume-guidance", status_code=status.HTTP_202_ACCEPTED)
async def resume_guidance(
    run_id: UUID,
    body: ResumeGuidanceIn,
    session: AsyncSession = Depends(db_session_user_dep),
    user_id: UUID = Depends(get_current_user_id),
):
    """Re-enqueue derive with guidance hints (MVP: restart run with overrides)."""
    svc = ResumeDeriveService(session)
    try:
        run = await svc.get_run(run_id, user_id=user_id)
        if run.status != "needs_guidance":
            raise DeriveError(409, "NOT_IN_GUIDANCE", "Run is not in needs_guidance.")
        pages = int(body.target_page_count or run.target_page_count)
        template = body.template_id or run.template_id
        new_run = await svc.start_run(
            user_id=user_id,
            job_id=run.job_id,
            target_page_count=pages,
            template_id=template,
            root_resume_id=run.root_resume_id,
            idempotency_key=None,
        )
        return DeriveRunAcceptedOut(run_id=new_run.id, status=new_run.status)
    except DeriveError as exc:
        return _err(exc)


@router.get("/resumes/{resume_id}/export-gate", response_model=ExportGateOut)
async def export_gate(
    resume_id: UUID,
    session: AsyncSession = Depends(db_session_user_dep),
    user_id: UUID = Depends(get_current_user_id),
):
    svc = ResumeDeriveService(session)
    try:
        gate = await svc.export_gate(resume_id, user_id=user_id)
        return ExportGateOut(**gate)
    except DeriveError as exc:
        return _err(exc)


@router.get("/resumes/{resume_id}/derive-rationale")
async def derive_rationale(
    resume_id: UUID,
    session: AsyncSession = Depends(db_session_user_dep),
    user_id: UUID = Depends(get_current_user_id),
):
    svc = ResumeDeriveService(session)
    from app.modules.resumes_v2.repository import ResumeV2Repository

    row = await ResumeV2Repository(session).get(resume_id, user_id=user_id)
    if row is None:
        return JSONResponse(status_code=404, content={"error": "NOT_FOUND", "message": "Not found"})
    meta = row.derive_meta or {}
    return {
        "takeaway_notes": meta.get("takeaway_notes") or [],
        "selection_plan": meta.get("selection_plan") or {},
        "unused_materials": meta.get("unused_materials") or [],
        "jd_parse": meta.get("jd_parse") or {},
        "supplement_questions": meta.get("supplement_questions") or [],
        "pending_claims": ((row.data or {}).get("metadata") or {}).get("derive", {}).get("pendingClaims") or [],
    }


@router.get("/resumes/{resume_id}/derive-suggestions")
async def list_derive_suggestions(
    resume_id: UUID,
    session: AsyncSession = Depends(db_session_user_dep),
    user_id: UUID = Depends(get_current_user_id),
):
    """Legacy derive_meta suggestions (REQ-055/056). Prefer REQ-059 analysis suggestions."""
    from app.modules.resumes_v2.repository import ResumeV2Repository

    row = await ResumeV2Repository(session).get(resume_id, user_id=user_id)
    if row is None:
        return JSONResponse(status_code=404, content={"error": "NOT_FOUND", "message": "Not found"})
    return {"suggestions": (row.derive_meta or {}).get("suggestions") or []}


@router.post("/resumes/{resume_id}/suggestions/preview")
async def preview_suggestion(
    resume_id: UUID,
    body: SuggestionPreviewIn,
    session: AsyncSession = Depends(db_session_user_dep),
    user_id: UUID = Depends(get_current_user_id),
):
    svc = ResumeDeriveService(session)
    try:
        return await svc.preview_suggestion(
            resume_id,
            user_id=user_id,
            suggestion_id=body.suggestion_id,
            client_version=body.client_version,
        )
    except DeriveError as exc:
        return _err(exc)


@router.post("/resumes/{resume_id}/suggestions/apply")
async def apply_suggestion(
    resume_id: UUID,
    body: SuggestionApplyIn,
    session: AsyncSession = Depends(db_session_user_dep),
    user_id: UUID = Depends(get_current_user_id),
):
    svc = ResumeDeriveService(session)
    try:
        row = await svc.apply_suggestion(
            resume_id,
            user_id=user_id,
            suggestion_id=body.suggestion_id,
            client_version=body.client_version,
            preview_token=body.preview_token,
        )
        return _resume_payload(row)
    except DeriveError as exc:
        return _err(exc)


@router.post("/resumes/{resume_id}/supplements")
async def post_supplements(
    resume_id: UUID,
    body: SupplementIn,
    session: AsyncSession = Depends(db_session_user_dep),
    user_id: UUID = Depends(get_current_user_id),
):
    svc = ResumeDeriveService(session)
    try:
        row = await svc.apply_supplements(
            resume_id,
            user_id=user_id,
            answers=[a.model_dump() for a in body.answers],
            sync_target=body.sync_target,
        )
        return _resume_payload(row)
    except DeriveError as exc:
        return _err(exc)


def _resume_payload(row) -> dict:
    return {
        "id": str(row.id),
        "user_id": str(row.user_id),
        "name": row.name,
        "slug": row.slug,
        "tags": list(row.tags or []),
        "is_public": bool(row.is_public),
        "is_locked": bool(row.is_locked),
        "password_set": bool(row.password_hash),
        "version": int(row.version),
        "resume_kind": getattr(row, "resume_kind", "standard"),
        "root_resume_id": str(row.root_resume_id) if getattr(row, "root_resume_id", None) else None,
        "job_id": str(row.job_id) if getattr(row, "job_id", None) else None,
        "root_version_at_derive": getattr(row, "root_version_at_derive", None),
        "target_page_count": getattr(row, "target_page_count", None),
        "actual_page_count": getattr(row, "actual_page_count", None),
        "derive_meta": getattr(row, "derive_meta", None) or {},
        "data": row.data,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }
