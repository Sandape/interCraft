"""Ability Profile REST API (M18).

Endpoints:
- GET    /ability-profile/dashboard          — US1: Dashboard
- POST   /ability-profile/share              — US4: Create share link
- GET    /ability-profile/share              — US4: List share links
- DELETE /ability-profile/share/{id}         — US4: Revoke share link
- GET    /ability-profile/share/{token}      — US4: Public access
- GET    /ability-profile/export-pdf         — US6: Sync PDF download (024)
- POST   /ability-profile/export             — US6: Legacy export (inline generate)
- GET    /ability-profile/exports            — US6: List exports
- GET    /ability-profile/exports/{id}       — US6: Export status
- GET    /ability-profile/exports/{id}/download — US6: Download PDF
- GET    /ability-profile/admin/{user_id}    — US7: Admin view
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import db_session_user_dep, get_current_user_id
from app.core.rate_limit import enforce_rate_limit
from app.modules.ability_profile.repository import AbilityProfileRepository
from app.modules.ability_profile.schemas import (
    AdminDashboardOut,
    DashboardOut,
    ExportListOut,
    ExportStatusOut,
    ExportTriggerOut,
    ShareLinkCreate,
    ShareLinkCreateOut,
    ShareLinkListOut,
    SharedProfileOut,
)
from app.modules.ability_profile.service import AbilityProfileService

router = APIRouter(prefix="/ability-profile", tags=["ability-profile"])


def _get_service(session: AsyncSession = Depends(db_session_user_dep)) -> AbilityProfileService:
    return AbilityProfileService(AbilityProfileRepository(session), session)


# ── US1: Dashboard ───────────────────────────────────────────────────────────

@router.get("/dashboard", response_model=DashboardOut)
async def get_dashboard(
    user_id: UUID = Depends(get_current_user_id),
    svc: AbilityProfileService = Depends(_get_service),
) -> dict:
    data = await svc.get_dashboard(user_id)
    return {"data": data}


# ── US4: Share Links ─────────────────────────────────────────────────────────

@router.post("/share", response_model=ShareLinkCreateOut, status_code=201)
async def create_share_link(
    body: ShareLinkCreate,
    request: Request,
    user_id: UUID = Depends(get_current_user_id),
    svc: AbilityProfileService = Depends(_get_service),
) -> dict:
    await enforce_rate_limit(request, scope="business", per_minute=10)
    data = await svc.create_share_link(
        user_id,
        expires_in_hours=body.expires_in_hours,
    )
    return {"data": data}


@router.get("/share", response_model=ShareLinkListOut)
async def list_share_links(
    user_id: UUID = Depends(get_current_user_id),
    svc: AbilityProfileService = Depends(_get_service),
) -> dict:
    data = await svc.list_share_links(user_id)
    return {"data": data}


@router.delete("/share/{link_id}", status_code=204, response_model=None)
async def revoke_share_link(
    link_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    svc: AbilityProfileService = Depends(_get_service),
) -> None:
    await svc.revoke_share_link(user_id, link_id)


@router.get("/share/{token}", response_model=SharedProfileOut)
async def get_shared_profile(
    token: str,
    request: Request,
    svc: AbilityProfileService = Depends(_get_service),
) -> dict:
    await enforce_rate_limit(request, scope="business", per_minute=10)
    data = await svc.get_shared_profile(token)
    return {"data": data}


# ── US6: PDF Export ──────────────────────────────────────────────────────────

@router.get("/export-pdf")
async def export_pdf(
    request: Request,
    user_id: UUID = Depends(get_current_user_id),
    svc: AbilityProfileService = Depends(_get_service),
) -> FileResponse:
    """Sync PDF download (Feature 024 FR-050)."""
    await enforce_rate_limit(request, scope="business", per_minute=5)
    return await svc.export_pdf_sync(user_id)


@router.post("/export", response_model=ExportTriggerOut, status_code=202)
async def trigger_export(
    request: Request,
    user_id: UUID = Depends(get_current_user_id),
    svc: AbilityProfileService = Depends(_get_service),
) -> dict:
    """Legacy async-shaped export; generates PDF inline (no ARQ)."""
    await enforce_rate_limit(request, scope="business", per_minute=5)
    data = await svc.trigger_export(user_id)
    return {"data": data}


@router.get("/exports", response_model=ExportListOut)
async def list_exports(
    limit: int = Query(default=10, ge=1, le=20),
    user_id: UUID = Depends(get_current_user_id),
    svc: AbilityProfileService = Depends(_get_service),
) -> dict:
    data = await svc.list_exports(user_id, limit=limit)
    return {"data": data}


@router.get("/exports/{export_id}", response_model=ExportStatusOut)
async def get_export_status(
    export_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    svc: AbilityProfileService = Depends(_get_service),
) -> dict:
    data = await svc.get_export_status(user_id, export_id)
    return {"data": data}


@router.get("/exports/{export_id}/download")
async def download_export(
    export_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    svc: AbilityProfileService = Depends(_get_service),
) -> FileResponse:
    return await svc.download_export_file(user_id, export_id)


# ── US7: Admin View ──────────────────────────────────────────────────────────

@router.get("/admin/{target_user_id}", response_model=AdminDashboardOut)
async def get_admin_dashboard(
    target_user_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    svc: AbilityProfileService = Depends(_get_service),
) -> dict:
    data = await svc.get_admin_dashboard(user_id, target_user_id)
    return {"data": data}


__all__ = ["router"]
