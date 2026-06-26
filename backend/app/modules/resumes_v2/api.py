"""M032 — Resume v2 FastAPI router.

14 endpoints (per contracts/01-rest-api.md §1-6). US1 (T022) implements
the 5 CRUD endpoints (list / create / get / update / delete) with
optimistic concurrency + lock + legacy-format guards. The lock endpoint
is also implemented because T018's `test_put_when_locked_returns_423`
needs to set the lock state. The remaining 8 endpoints (duplicate,
sharing, statistics, analyze, public, events, export) remain 501 stubs
until later US phases ship.

Mount point: ``/api/v1/v2`` (added in ``backend/app/main.py`` and
``backend/app/api/v1/__init__.py``).
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Query, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import db_session_user_dep, get_current_user_id, get_current_user_id_optional
from app.core.db import get_db_session_no_rls
from app.core.logging import get_logger
from app.observability import record_llm_span_attributes, span as otel_span
from app.modules.resumes_v2.schemas import (
    ExportRenderIn,
    ResumeV2CreateIn,
    ResumeV2ListOut,
    ResumeV2Out,
    ResumeV2UpdateIn,
    SharingIn,
)
from app.modules.resumes_v2.service import ResumeV2Service, ServiceError

router = APIRouter(prefix="/v2", tags=["resumes-v2"])

# T177: structured logger with consistent fields. Each call site emits
# (request_id, user_id, resume_id?, version?, ...) — context vars for
# request_id/user_id are populated by middleware; we add resume_id +
# version explicitly per spec.
_log = get_logger("resumes_v2")


def _not_implemented(operation: str) -> JSONResponse:
    """Return the standard 501 stub for endpoints that ship in later US."""
    return JSONResponse(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        content={
            "error": "NOT_IMPLEMENTED",
            "message": f"{operation} is not yet implemented (REQ-032, Wave 3 stub).",
        },
    )


def _err_response(status: int, code: str, message: str) -> JSONResponse:
    """Return a flat ``{"error": code, "message": ...}`` JSONResponse."""
    return JSONResponse(status_code=status, content={"error": code, "message": message})


def _resume_to_out(row, *, include_data: bool = True) -> dict[str, Any]:
    """Project an ORM row to the contracts/01-rest-api.md §1.3 shape.

    ``include_data=False`` strips the (potentially large) data blob for
    list responses (§1.1).
    """
    payload: dict[str, Any] = {
        "id": str(row.id),
        "user_id": str(row.user_id),
        "name": row.name,
        "slug": row.slug,
        "tags": list(row.tags or []),
        "is_public": bool(row.is_public),
        "is_locked": bool(row.is_locked),
        "password_set": bool(row.password_hash),
        "version": int(row.version),
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }
    if include_data:
        payload["data"] = row.data
    return payload


def _list_item_to_out(row) -> dict[str, Any]:
    """Project an ORM row to the contracts/01-rest-api.md §1.1 list shape."""
    return {
        "id": str(row.id),
        "name": row.name,
        "slug": row.slug,
        "tags": list(row.tags or []),
        "is_public": bool(row.is_public),
        "is_locked": bool(row.is_locked),
        "version": int(row.version),
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


# ─────────────────────────────────────────────────────────────────────────────
# §1 Resume CRUD
# ─────────────────────────────────────────────────────────────────────────────


@router.get("/resumes", response_model=ResumeV2ListOut)
async def list_resumes(
    search: str | None = Query(default=None, max_length=128),
    tags: str | None = Query(default=None, max_length=512),
    is_public: bool | None = Query(default=None),
    sort: str = Query(default="updated", pattern="^(updated|created|name)$"),
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(db_session_user_dep),
):
    """GET /api/v1/v2/resumes — list the current user's v2 resumes."""
    svc = ResumeV2Service(db)
    rows = await svc.repo.list(
        user_id,
        search=search,
        is_public=is_public,
        sort=sort,
    )
    if tags:
        wanted = {t.strip() for t in tags.split(",") if t.strip()}
        rows = [r for r in rows if wanted.issubset(set(r.tags or []))]
    return {"data": [_list_item_to_out(r) for r in rows]}


@router.post("/resumes", status_code=status.HTTP_201_CREATED)
async def create_resume(
    payload: ResumeV2CreateIn,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(db_session_user_dep),
):
    """POST /api/v1/v2/resumes — create a new v2 resume."""
    svc = ResumeV2Service(db)
    try:
        row = await svc.create_resume(
            user_id=user_id,
            name=payload.name,
            slug=payload.slug,
            template=payload.template,
            from_sample=payload.from_sample,
        )
    except ServiceError as e:
        return e.to_response()
    await db.commit()
    # T177: structured log on create
    _log.info(
        "resume_v2.create",
        resume_id=str(row.id),
        version=int(row.version),
        template=payload.template,
        from_sample=payload.from_sample,
    )
    # Envelope response per E2E test contract: clients expect
    # `{ "resume": {...} }` so that the create/duplicate endpoints
    # share a uniform shape across v2. Spec §1.2 says "same shape as
    # 1.3", but the in-flight frontend + E2E tests use `{resume: ...}`.
    # We wrap to match the client until the spec is amended.
    return {"resume": _resume_to_out(row, include_data=True)}


@router.get("/resumes/{resume_id}", response_model=ResumeV2Out)
async def get_resume(
    resume_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(db_session_user_dep),
):
    """GET /api/v1/v2/resumes/{id} — fetch a single resume.

    T125 — v1 legacy detection. If the row's `data` JSONB has
    `data_format_version == 'v1'`, return 400 LEGACY_FORMAT so the
    frontend can show a read-only banner + redirect suggestion. New
    v2 resumes do not have this key (defaults are v2-shaped).
    """
    svc = ResumeV2Service(db)
    try:
        row = await svc.get_resume(resume_id, user_id=user_id)
    except ServiceError as e:
        return e.to_response()
    # Inspect the JSONB blob for the legacy marker. Defensive: any
    # non-dict payload (extremely unlikely with current writers) is
    # treated as v2 to avoid masking real errors.
    data_blob = row.data if isinstance(row.data, dict) else {}
    fmt = data_blob.get("data_format_version") if isinstance(data_blob, dict) else None
    if fmt == "v1":
        return _err_response(
            400,
            "LEGACY_FORMAT",
            "该简历使用旧版格式,请创建新版 v2 简历。",
        )
    return _resume_to_out(row, include_data=True)


@router.put("/resumes/{resume_id}")
async def update_resume(
    resume_id: UUID,
    payload: ResumeV2UpdateIn,
    if_match: str | None = Header(default=None, alias="If-Match"),
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(db_session_user_dep),
):
    """PUT /api/v1/v2/resumes/{id} — optimistic concurrency update."""
    if if_match is None or if_match == "":
        return _err_response(400, "MISSING_IF_MATCH", "If-Match header is required for PUT.")
    try:
        if_match_int = int(if_match)
    except (TypeError, ValueError):
        return _err_response(400, "INVALID_IF_MATCH", "If-Match must be an integer version.")

    # REQ-039: `data` is now a raw `dict` (not `ResumeDataV2Pydantic`),
    # so the service layer can do deep-merge on partial PUTs. No
    # `model_dump` round-trip needed.
    data_dict = payload.data

    # T178: OTel span around PUT update
    with otel_span(
        "v2.resume.update",
        **{"resume.id": str(resume_id), "resume.if_match": if_match_int},
    ):
        svc = ResumeV2Service(db)
        try:
            updated, conflict_latest = await svc.update_resume(
                resume_id,
                user_id=user_id,
                if_match=if_match_int,
                name=payload.name,
                tags=payload.tags,
                data=data_dict,
            )
        except ServiceError as e:
            return e.to_response()

    if updated is None:
        assert conflict_latest is not None
        # T177: structured log on update conflict
        _log.warning(
            "resume_v2.update.conflict",
            resume_id=str(resume_id),
            sent_version=if_match_int,
            latest_version=int(conflict_latest.version),
        )
        return JSONResponse(
            status_code=409,
            content={
                "error": "VERSION_CONFLICT",
                "message": f"Stored version is {conflict_latest.version}, you sent {if_match_int}.",
                "latest_version": int(conflict_latest.version),
                "latest_data": conflict_latest.data,
                "latest_updated_at": (
                    conflict_latest.updated_at.isoformat() if conflict_latest.updated_at else None
                ),
            },
        )
    await db.commit()
    return _resume_to_out(updated, include_data=True)


@router.delete("/resumes/{resume_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_resume(
    resume_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(db_session_user_dep),
):
    """DELETE /api/v1/v2/resumes/{id} — soft delete (cascades)."""
    svc = ResumeV2Service(db)
    try:
        await svc.delete_resume(resume_id, user_id=user_id)
    except ServiceError as e:
        return e.to_response()
    await db.commit()
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Lock endpoint — implemented (T018 needs it to set up the locked state)
# ─────────────────────────────────────────────────────────────────────────────


@router.put("/resumes/{resume_id}/lock")
async def set_lock(
    resume_id: UUID,
    payload: dict[str, Any],
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(db_session_user_dep),
):
    """PUT /api/v1/v2/resumes/{id}/lock — toggle lock. Independent of version."""
    locked = bool(payload.get("locked"))
    svc = ResumeV2Service(db)
    current = await svc.repo.get(resume_id, user_id=user_id)
    if current is None:
        owner = await svc.repo.get_owner_id(resume_id)
        if owner is not None and owner != user_id:
            return _err_response(403, "NOT_OWNER", "You do not own this resume.")
        return _err_response(404, "NOT_FOUND", "Resume not found.")
    ok = await svc.repo.set_lock(resume_id, user_id=user_id, is_locked=locked)
    if not ok:
        return _err_response(404, "NOT_FOUND", "Resume not found.")
    await db.commit()
    return {"is_locked": locked}


# ─────────────────────────────────────────────────────────────────────────────
# §2–5: side actions, public access, SSE, export (stubs for later US)
# ─────────────────────────────────────────────────────────────────────────────


@router.post("/resumes/{resume_id}/duplicate")
async def duplicate_resume(
    resume_id: UUID,
    accept_language: str | None = Header(default=None, alias="Accept-Language"),
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(db_session_user_dep),
):
    """POST /api/v1/v2/resumes/{id}/duplicate — T158.

    Deep-copies the resume's ``data`` JSONB, generates a new UUIDv7,
    assigns slug ``<orig>-copy-N`` (N = 1 + max existing N), suffixes
    the name with ``" (Copy)"`` (or ``"（副本）"`` for ``zh-CN`` Accept-Language),
    and resets ``is_public=false``, ``is_locked=false``,
    ``password_hash=null``. No statistics or analysis row is copied.

    Response shape: ``{"resume": {…full resume data…}}`` so it matches
    the create endpoint envelope (locked E2E contract).
    """
    svc = ResumeV2Service(db)
    try:
        copy = await svc.duplicate_resume(
            resume_id, user_id=user_id, accept_language=accept_language
        )
    except ServiceError as e:
        return e.to_response()
    await db.commit()
    # T177: structured log on duplicate
    _log.info(
        "resume_v2.duplicate",
        resume_id=str(resume_id),
        new_resume_id=str(copy.id),
        new_slug=copy.slug,
    )
    return {"resume": _resume_to_out(copy, include_data=True)}


@router.put("/resumes/{resume_id}/sharing")
async def set_sharing(
    resume_id: UUID,
    payload: SharingIn,
    user_id: UUID = Depends(get_current_user_id_optional),
    db: AsyncSession = Depends(db_session_user_dep),
):
    """PUT /api/v1/v2/resumes/{id}/sharing — enable/disable public + password (T141).

    Body: ``{"is_public": bool, "password": str | null}``.
      - When ``password`` is a non-empty string, the service bcrypt-hashes
        it at cost 12 and stores the hash. Validation: 6..64 chars.
      - When ``password`` is ``null``, the stored hash is cleared (which
        also requires ``is_public=true`` per the table CHECK constraint).

    Returns: ``{"is_public", "password_set", "public_url"}``. The
    ``public_url`` is ``/r/{display_name}/{slug}`` when public, else ``null``.
    """
    if user_id is None:
        return _err_response(401, "UNAUTHENTICATED", "Authentication required.")
    svc = ResumeV2Service(db)
    try:
        result = await svc.set_sharing(
            resume_id,
            user_id=user_id,
            is_public=payload.is_public,
            password=payload.password,
        )
    except ServiceError as e:
        return e.to_response()
    await db.commit()
    # Fire SSE event so connected editors refresh their Sharing panel.
    # We swallow the failure path — the contract is best-effort.
    await svc.emit_public_changed(
        resume_id=resume_id,
        user_id=user_id,
        is_public=result["is_public"],
        password_set=result["password_set"],
        public_url=result["public_url"],
    )
    return result


@router.get("/resumes/{resume_id}/statistics")
async def get_statistics(
    resume_id: UUID,
    user_id: UUID = Depends(get_current_user_id_optional),
    db: AsyncSession = Depends(db_session_user_dep),
):
    """GET /api/v1/v2/resumes/{id}/statistics — counters + timestamps (T145).

    Per spec §2.4: empty ``{views:0, downloads:0, ...}`` when is_public=false
    (the row does not exist). Returns 404 NOT_FOUND when the resume
    does not exist OR is not owned by the caller.
    """
    if user_id is None:
        return _err_response(401, "UNAUTHENTICATED", "Authentication required.")
    svc = ResumeV2Service(db)
    try:
        await svc.get_resume(resume_id, user_id=user_id)
    except ServiceError as e:
        return e.to_response()
    row = await svc.repo.get_statistics(resume_id)
    if row is None:
        return {"views": 0, "downloads": 0, "last_viewed_at": None, "last_downloaded_at": None}
    return {
        "views": int(row.views),
        "downloads": int(row.downloads),
        "last_viewed_at": row.last_viewed_at.isoformat() if row.last_viewed_at else None,
        "last_downloaded_at": row.last_downloaded_at.isoformat() if row.last_downloaded_at else None,
    }


@router.post("/resumes/{resume_id}/analyze")
async def analyze_resume(
    resume_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(db_session_user_dep),
):
    """POST /api/v1/v2/resumes/{id}/analyze — T152.

    Calls DeepSeek V4 Pro to analyze the resume. The LLM client is
    invoked with our own 3-attempt retry loop (1s/2s/4s exponential
    backoff). On the 3rd failure the row is stored with
    ``status='failed'`` + ``failure_reason``; on success it is
    UPSERTed with the analysis JSONB.

    Per FR-091a there is NO in-memory cache. Each call hits DeepSeek
    fresh; the UPSERT is a storage-layer (not a cache) semantic so the
    latest row wins.

    On both success and failure the ``analysis.completed`` SSE event
    is emitted (T155) so connected editors can refresh their Analysis
    panel.
    """
    svc = ResumeV2Service(db)
    # T178: OTel span around AI analysis call
    with otel_span(
        "v2.resume.analyze",
        **{"resume.id": str(resume_id), "llm.model": "deepseek-v4-pro"},
    ) as _analyze_span:
        try:
            result = await svc.analyze_resume(resume_id, user_id=user_id)
        except ServiceError as e:
            return e.to_response()
        # T178: emit token usage + retry count metrics
        record_llm_span_attributes(
            _analyze_span,
            **{"llm.retry_count": int(result.get("retry_count") or 0)},
        )
    await db.commit()

    # T155: emit SSE event so connected editors refresh.
    overall_score = None
    if result.get("analysis") and isinstance(result["analysis"], dict):
        overall_score = int(result["analysis"].get("overallScore") or 0)
    await svc.emit_analysis_completed(
        resume_id=resume_id,
        status=result.get("status") or "failed",
        overall_score=overall_score,
    )

    # Return the persisted row.
    row = await svc.repo.get_analysis(resume_id)
    if row is None:
        return _err_response(500, "ANALYZE_STORE_FAILED", "Failed to load stored analysis.")
    return {
        "status": row.status,
        "analysis": row.analysis,
        "failure_reason": row.failure_reason,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


@router.get("/resumes/{resume_id}/analysis")
async def get_analysis(
    resume_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(db_session_user_dep),
):
    """GET /api/v1/v2/resumes/{id}/analysis — T153.

    Returns the latest analysis row (UPSERT — one row per resume) or
    404 if the resume has never been analyzed. Ownership pre-flight
    returns 404 vs 403 per the v2 contract.
    """
    svc = ResumeV2Service(db)
    try:
        row = await svc.get_analysis(resume_id, user_id=user_id)
    except ServiceError as e:
        return e.to_response()
    if row is None:
        return _err_response(404, "NOT_FOUND", "No analysis for this resume yet.")
    return {
        "status": row.status,
        "analysis": row.analysis,
        "failure_reason": row.failure_reason,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


# ─────────────────────────────────────────────────────────────────────────────
# §4 Public access (T142–T144) — no auth required
# ─────────────────────────────────────────────────────────────────────────────


def _public_url(display_name: str | None, slug: str | None) -> str | None:
    if not display_name or not slug:
        return None
    return f"/r/{display_name}/{slug}"


async def _resolve_public_resume(
    svc: ResumeV2Service,
    username: str,
    slug: str,
) -> tuple[Any, JSONResponse | None]:
    """Resolve a username/slug to a resume row, or return a JSON error.

    Returns ``(row, None)`` on success, ``(None, response)`` on a 404 /
    not-found error so the caller can short-circuit. Used by the
    public GET + verify-password + PDF endpoints.
    """
    row = await svc.repo.get_by_username_and_slug(username=username, slug=slug)
    if row is None:
        return None, _err_response(404, "NOT_FOUND", "Resume not found.")
    if not row.is_public:
        return None, _err_response(404, "NOT_FOUND", "Resume not found.")
    return row, None


@router.get("/public/{username}/{slug}")
async def public_view(
    username: str,
    slug: str,
    request: Request,
    user_id: UUID | None = Depends(get_current_user_id_optional),
    db: AsyncSession = Depends(get_db_session_no_rls),
):
    """GET /api/v1/v2/public/{username}/{slug} — read-only public resume.

    No auth required. If the resume is password-protected and the
    caller does not present a valid ``v2_public_pw_<hash>`` cookie,
    returns 401 ``PASSWORD_REQUIRED``. On success, increments the
    ``views`` counter unless the caller is the owner.
    """
    svc = ResumeV2Service(db)
    row, err = await _resolve_public_resume(svc, username, slug)
    if err is not None:
        return err
    if row.password_hash:
        cookies = request.cookies
        cookie_name = _public_pw_cookie_name(row.password_hash)
        if not cookies.get(cookie_name):
            return _err_response(
                401,
                "PASSWORD_REQUIRED",
                "This resume is password-protected.",
            )
    # Increment views (owner visit is a no-op per spec).
    if user_id is None or user_id != row.user_id:
        await svc.repo.increment_views(row.id)
        await svc.ensure_statistics_row(row.id)
    return _resume_to_out(row, include_data=True)


@router.post("/public/{username}/{slug}/verify-password")
async def public_verify_password(
    username: str,
    slug: str,
    response: Response,
    payload: dict[str, Any],
    db: AsyncSession = Depends(get_db_session_no_rls),
):
    """POST /api/v1/v2/public/{username}/{slug}/verify-password — T143.

    Body: ``{"password": str}``. On success: 200 ``{"ok": true}`` +
    HttpOnly ``v2_public_pw_<hash>`` cookie (SameSite=Lax, Path=/,
    Max-Age=600 seconds = 10 minutes). 401 on bad password.
    """
    svc = ResumeV2Service(db)
    row, err = await _resolve_public_resume(svc, username, slug)
    if err is not None:
        return err
    if not row.password_hash:
        return _err_response(401, "PASSWORD_REQUIRED", "This resume has no password.")
    password = payload.get("password") if isinstance(payload, dict) else None
    if not isinstance(password, str) or not password:
        return _err_response(400, "INVALID_PASSWORD", "Password is required.")
    from app.core.security import verify_password

    if not verify_password(password, row.password_hash):
        return _err_response(401, "PASSWORD_INVALID", "Incorrect password.")
    cookie_name = _public_pw_cookie_name(row.password_hash)
    response.set_cookie(
        key=cookie_name,
        value="1",
        max_age=600,
        httponly=True,
        samesite="lax",
        path="/",
        secure=False,
    )
    return {"ok": True}


@router.get("/public/{username}/{slug}/pdf")
async def public_pdf(
    username: str,
    slug: str,
    request: Request,
    user_id: UUID | None = Depends(get_current_user_id_optional),
    db: AsyncSession = Depends(get_db_session_no_rls),
):
    """GET /api/v1/v2/public/{username}/{slug}/pdf — public PDF download (T144).

    Same cookie flow as ``public_view``. On success: increments
    ``downloads`` (if caller is not the owner) and returns a JSON
    envelope instructing the client to POST the rendered HTML to
    ``/api/v1/export/render`` (per Wave 12 / US15 client contract).

    We deliberately do NOT render server-side here — the export
    gateway is the single source of truth for PDF rendering.
    Instead, we return the HTML so the client can either:
      (a) POST to /api/v1/export/render (server-side render), or
      (b) use the browser to print-to-PDF client-side.

    For a minimal first cut we just return the HTML so callers can
    proceed. The full PDF path will be wired in Wave 16 (US14).
    """
    svc = ResumeV2Service(db)
    row, err = await _resolve_public_resume(svc, username, slug)
    if err is not None:
        return err
    if row.password_hash:
        cookies = request.cookies
        cookie_name = _public_pw_cookie_name(row.password_hash)
        if not cookies.get(cookie_name):
            return _err_response(
                401,
                "PASSWORD_REQUIRED",
                "This resume is password-protected.",
            )
    if user_id is None or user_id != row.user_id:
        await svc.repo.increment_downloads(row.id)
        await svc.ensure_statistics_row(row.id)
    # Hand back the data so the caller (typically the public page's
    # "Download PDF" button) can re-render via the export gateway.
    return {
        "resume_id": str(row.id),
        "slug": row.slug,
        "data": row.data,
        "render_url": "/api/v1/export/render",
    }


def _public_pw_cookie_name(password_hash: str) -> str:
    """Build a deterministic cookie name keyed off the password hash.

    The bcrypt hash includes a random salt, so the cookie name is
    effectively per-password. When the password is changed, the
    hash changes, the cookie name changes, and the old cookie
    becomes stale automatically (no server-side invalidation needed).
    """
    import hashlib

    h = hashlib.sha256(password_hash.encode("utf-8")).hexdigest()[:12]
    return f"v2_public_pw_{h}"


@router.post("/export/render", response_model=None)
async def export_render(
    payload: ExportRenderIn,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(db_session_user_dep),
):
    """POST /api/v1/v2/export/render — REQ-036 (US10 T106).

    Body: ``{"html": "...", "format": "pdf"|"png"|"jpeg"|"json",
    "resume_id": "<uuid>?"}``.

    Behavior per contracts/01-rest-api.md §6:
      - ``format: "json"`` → return the resume's full ``ResumeDataV2``
        document as ``application/json`` (ignores ``html``).
      - ``format: "pdf" | "png" | "jpeg"`` → delegate to the existing
        027 export gateway renderer (``render_resume``) so preview↔PDF
        parity is preserved (single rendering path).
      - When ``resume_id`` is supplied, the caller must own the resume;
        on success the ``downloads`` counter is incremented and the
        statistics row is ensured (same shape as the public PDF flow).

    Errors:
      - 400 ``EMPTY_CONTENT`` / ``INVALID_FORMAT`` /
        ``CONTENT_TOO_LARGE`` — pre-render validation.
      - 400 ``MISSING_RESUME_ID`` — when ``format=json`` and no
        ``resume_id`` is supplied (no data to return).
      - 403 ``NOT_OWNER`` — caller is not the owner of ``resume_id``.
      - 404 ``NOT_FOUND`` — ``resume_id`` does not exist.
      - 500 ``RENDERING_FAILED`` — Playwright/gateway raised.
    """
    # T178: OTel span around the whole render pipeline
    with otel_span(
        "v2.resume.export.render",
        **{"pdf.format": payload.format, "resume.id": str(payload.resume_id or "")},
    ):
        fmt = payload.format
        html = (payload.html or "").strip()
        content_size = len(payload.html.encode("utf-8"))

        # ── pre-render validation ────────────────────────────────────
        # PDF/PNG/JPEG need HTML. JSON uses the resume's stored data
        # so empty html is fine — but we still need a resume_id.
        if fmt in {"pdf", "png", "jpeg"}:
            if not html:
                return _err_response(
                    400, "EMPTY_CONTENT", "Resume content is empty."
                )
            if content_size > 1_000_000:
                return _err_response(
                    413, "CONTENT_TOO_LARGE", "Resume content is too large."
                )
        if fmt == "json" and payload.resume_id is None:
            return _err_response(
                400,
                "MISSING_RESUME_ID",
                "resume_id is required when format=json.",
            )

        # ── ownership pre-flight + counter increment ────────────────
        # When a resume_id is supplied we re-use the standard
        # ``get_resume`` helper so 404 vs 403 stays consistent with
        # the rest of the v2 API.
        svc = ResumeV2Service(db)
        resume_row = None
        if payload.resume_id is not None:
            try:
                resume_row = await svc.get_resume(
                    payload.resume_id, user_id=user_id
                )
            except ServiceError as e:
                return e.to_response()
            # Increment downloads + ensure stats row exist. Owner
            # downloads also count per spec §2.4.
            # NOTE: ensure_statistics_row MUST run BEFORE
            # increment_downloads — the UPDATE is a no-op when no
            # statistics row exists yet, so flipping the order makes
            # the increment a permanent no-op on first download.
            await svc.ensure_statistics_row(resume_row.id)
            await svc.repo.increment_downloads(resume_row.id)
            # Commit so a separate session (e.g. another API call
            # reading /statistics) sees the counter bump. Mirrors
            # the commit pattern of every other mutation endpoint.
            await db.commit()

        # ── format dispatch ──────────────────────────────────────────
        if fmt == "json":
            # JSON download returns the full ResumeDataV2 document.
            assert resume_row is not None
            # T177: structured log on successful JSON export
            _log.info(
                "resume_v2.export.json",
                resume_id=str(resume_row.id),
                user_id=str(user_id),
            )
            return JSONResponse(
                status_code=200,
                content=resume_row.data,
                headers={
                    "Content-Disposition": (
                        f'attachment; filename="resume-{resume_row.id}.json"'
                    ),
                },
            )

        # PDF/PNG/JPEG: delegate to the 027 gateway renderer. We do
        # NOT re-implement the Playwright pipeline — single source of
        # truth for preview↔PDF parity (per 027 contract).
        from src.services.pdf_renderer.renderer import render_resume
        from src.services.pdf_renderer.sanitize import sanitize_html

        sanitized = sanitize_html(payload.html)
        try:
            result = await render_resume(sanitized, fmt)
        except Exception as exc:  # pragma: no cover - host-specific failures
            _log.error(
                "resume_v2.export.render.failed",
                resume_id=str(payload.resume_id or ""),
                format=fmt,
                error=str(exc),
            )
            return _err_response(
                500,
                "RENDERING_FAILED",
                f"Rendering failed: {exc}",
            )

        content_types = {
            "pdf": "application/pdf",
            "png": "image/png",
            "jpeg": "image/jpeg",
        }
        # T177: structured log on successful render
        _log.info(
            "resume_v2.export.render",
            resume_id=str(payload.resume_id or ""),
            format=fmt,
            output_size_bytes=len(result),
        )
        filename_suffix = (
            str(resume_row.id) if resume_row is not None else "anonymous"
        )
        return Response(
            content=result,
            media_type=content_types[fmt],
            headers={
                "Content-Disposition": (
                    f'attachment; filename="resume-{filename_suffix}.{fmt}"'
                ),
            },
        )


__all__ = ["router"]
