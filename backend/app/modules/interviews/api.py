"""Interview sessions API — Phase 4 full CRUD (T030).

Phase 2: GET list/get only.
Phase 4: POST create/start/answers, GET report, cursor pagination.
REQ-048 (US1): mode-aware validation in ``POST /interview-sessions``.
REQ-048 (US4 / T087): GET ``/{id}/card`` returns the rendered doubao
card image (4:3 / 9:16) with 7-day cache.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import Response as FastAPIResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import db_session_user_dep, get_current_user_id
from app.modules.interviews.schemas import (
    InterviewPlanDegradeIn,
    InterviewSessionCreate,
    InterviewSessionCreateOut,
    InterviewSessionListOut,
    InterviewSessionOut,
)
from app.modules.interviews.service import InterviewSessionService

router = APIRouter(prefix="/interview-sessions", tags=["interview-sessions"])


async def _get_service(session: AsyncSession = Depends(db_session_user_dep)) -> InterviewSessionService:
    return InterviewSessionService(session)


# ---- Phase 2: list / get (unchanged core) ----

@router.get("", response_model=InterviewSessionListOut)
async def list_sessions(
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=50),
    user_id: UUID = Depends(get_current_user_id),
    svc: InterviewSessionService = Depends(_get_service),
) -> dict:
    data = await svc.list(user_id, status=status, limit=limit)
    return {"data": data}


# ---- Phase 4: create ----

@router.get("/mode-recommendation")
async def mode_recommendation(
    user_id: UUID = Depends(get_current_user_id),
    svc: InterviewSessionService = Depends(_get_service),
) -> dict:
    """REQ-048 US1 — return the count of active error questions for the
    「快速补漏」 button gating (AC-02).

    Returns ``{"data": {"available": int, "required": 5}}``. If the user
    has < 5 active errors, the frontend disables the quick_drill button
    and surfaces the AC-02b tooltip.
    """
    available = await svc._count_active_errors(user_id)
    return {"data": {"available": available, "required": 5}}


@router.get("/quick-drill/preview")
async def quick_drill_preview(
    jd_text: str | None = Query(default=None, max_length=2000),
    user_id: UUID = Depends(get_current_user_id),
    svc: InterviewSessionService = Depends(_get_service),
) -> dict:
    """REQ-048 US2 T059 — preview the 5 drill candidates before commit.

    Runs the hybrid pipeline (BM25 + cosine + rerank) with caching so
    the subsequent ``POST /api/v1/interviews`` commit reuses the same
    candidates (AC-09 cache hit on commit).

    Response envelope:
        {"data": {"candidates": [...], "cache_key": str, "degraded": bool}}
    """
    from app.agents.interview.nodes.drill_selector import select_drill_candidates

    candidates = await select_drill_candidates(
        user_id=str(user_id),
        jd_text=jd_text or "",
        top_k=5,
    )
    return {
        "data": {
            "candidates": candidates,
            "cache_key": f"preview:{hash((jd_text or '', len(candidates)))}",
            "degraded": False,
        }
    }


@router.get("/{id}", response_model=InterviewSessionOut)
async def get_session(
    id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    svc: InterviewSessionService = Depends(_get_service),
) -> InterviewSessionOut:
    return await svc.get(id, user_id)


@router.post("", response_model=InterviewSessionCreateOut, status_code=201)
async def create_session(
    body: InterviewSessionCreate,
    user_id: UUID = Depends(get_current_user_id),
    svc: InterviewSessionService = Depends(_get_service),
) -> dict:
    """Create an interview session and initialize LangGraph thread.

    REQ-048 mode-aware validation:
    - mode='quick_drill' + user error_count < 5 → 422 INSUFFICIENT_ERROR_POOL (AC-02)
    - mode='full' + max_questions not in [10, 15] → 422 INVALID_MAX_QUESTIONS
    - mode='doubao' + use_variants=true → 422 INVALID_COMBINATION
    """
    try:
        result = await svc.create(user_id, body)
    except ValueError as exc:
        # REQ-048 — mode validation errors as 422 with structured detail.
        code = str(exc.args[0]) if exc.args else "INVALID_INTERVIEW_MODE"
        details = exc.args[1] if len(exc.args) > 1 and isinstance(exc.args[1], dict) else {}
        messages = {
            "INSUFFICIENT_ERROR_POOL": "Not enough active error questions for quick drill",
            "INVALID_MAX_QUESTIONS": "Full interview max_questions must be 10 or 15",
            "INVALID_COMBINATION": "use_variants is only valid for quick_drill mode",
            "MISSING_INTERVIEW_TARGET": "job_id or position/company is required",
        }
        raise HTTPException(
            status_code=422,
            detail={
                "error": {
                    "code": code,
                    "message": messages.get(code, code),
                    "details": details,
                }
            },
        ) from exc
    # 020 (FIX-007, D-006): route the ORM through the Pydantic response
    # schema so the response_model actually applies. Without this, the
    # dict-wrapped ORM bypasses FastAPI's response_model enforcement
    # and leaks 9+ ORM-only fields (position, company, mode, …).
    return {
        "data": InterviewSessionCreateOut.model_validate({"data": result}).model_dump()["data"]
    }


# ---- Phase 4: start ----

@router.post("/{id}/start", status_code=202)
async def start_session(
    id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    svc: InterviewSessionService = Depends(_get_service),
) -> dict:
    """Start the interview, triggering LangGraph intake node."""
    result = await svc.start(id, user_id)
    return {"data": result}


@router.post("/{id}/plan", status_code=200)
async def generate_plan(
    id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    svc: InterviewSessionService = Depends(_get_service),
) -> dict:
    """Generate or read the session interview_plan without entering Q/A."""
    result = await svc.generate_plan(id, user_id)
    return {"data": result}


@router.post("/{id}/plan/degrade", status_code=200)
async def confirm_plan_degrade(
    id: UUID,
    body: InterviewPlanDegradeIn,
    user_id: UUID = Depends(get_current_user_id),
    svc: InterviewSessionService = Depends(_get_service),
) -> dict:
    """REQ-058 — confirm continuing interview without a ready plan."""
    result = await svc.confirm_plan_degrade(id, user_id, confirm=body.confirm)
    return {"data": result}


# ---- Phase 4: report ----

@router.get("/{id}/report")
async def get_report(
    id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    svc: InterviewSessionService = Depends(_get_service),
) -> dict:
    """Get the interview report for a completed session."""
    report = await svc.get_report(id, user_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found or interview not completed")
    return {"data": report}


# ---- Phase 4: submit answer ----

@router.post("/{id}/answers", status_code=200)
async def submit_answer(
    id: UUID,
    body: dict,
    user_id: UUID = Depends(get_current_user_id),
    svc: InterviewSessionService = Depends(_get_service),
) -> dict:
    """Submit an answer for the current interview question."""
    answer = body.get("content", "")
    sequence_no = body.get("sequence_no", 0)
    result = await svc.submit_answer(id, user_id, answer, sequence_no)
    return {"data": result}


# ---- Phase 4: resume (US2) ----

@router.get("/{id}/resume")
async def resume_session(
    id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    svc: InterviewSessionService = Depends(_get_service),
) -> dict:
    """Get resume information for an in-progress interview."""
    result = await svc.resume(id, user_id)
    return {"data": result}


# ---- soft delete ----

@router.delete("/{id}", status_code=204)
async def delete_session(
    id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    svc: InterviewSessionService = Depends(_get_service),
) -> Response:
    """Soft-delete an interview session (any status). Sets deleted_at."""
    await svc.delete(id, user_id)
    return Response(status_code=204)


# ---- REQ-048 US4 / T087 — Doubao card render endpoint ----


@router.get("/{id}/card")
async def get_card(
    id: UUID,
    size_variant: str = Query(default="4_3", pattern="^(4_3|9_16)$"),
    user_id: UUID = Depends(get_current_user_id),
    svc: InterviewSessionService = Depends(_get_service),
) -> FastAPIResponse:
    """REQ-048 US4 / T087 — Render the doubao card for ``id``.

    The endpoint contract:
    - 200 with image/jpeg body on success
    - 422 ``INTERVIEW_PLAN_NOT_READY`` when Planner hasn't run yet
      (AC-22 Edge-6) — typically ``mode='full'`` / ``mode='quick_drill'``
      sessions, or doubao sessions where Planner failed
    - 500 ``CARD_RENDER_FAILED`` when the renderer raises (AC-22 Edge-7)
    - ``X-Card-Cache-Hit: true`` header when served from Redis (AC-24)
    """
    try:
        result = await svc.render_card(
            session_id=id,
            user_id=user_id,
            size_variant=size_variant,
        )
    except ValueError as exc:
        # INTERVIEW_PLAN_NOT_READY
        raise HTTPException(
            status_code=422,
            detail={
                "error": {
                    "code": exc.args[0] if exc.args else "INTERVIEW_PLAN_NOT_READY",
                    "message": str(exc),
                }
            },
        ) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "CARD_RENDER_FAILED",
                    "message": str(exc),
                }
            },
        ) from exc

    headers = {
        "X-Card-Cache-Hit": "true" if result.get("cache_hit") else "false",
        "X-Card-Size-Variant": result.get("size_variant", size_variant),
        "X-Card-Bytes": str(result.get("bytes_total", 0)),
        "X-Card-Sha256": result.get("sha256_hex", ""),
    }
    return FastAPIResponse(
        content=result["image_bytes"],
        media_type="image/jpeg",
        headers=headers,
    )


__all__ = ["router"]
