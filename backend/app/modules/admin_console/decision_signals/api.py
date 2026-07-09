"""REQ-044 US1 — Decision Signals FastAPI router (FR-007~FR-010).

Mounted at ``/api/v1/admin-console/command-center`` by ``app.main``.

Endpoints:

- ``GET /signals`` — prioritized decision-signal queue
  (FR-007~FR-010 + SC-001/002).
- ``GET /overview`` — 4 KPI tiles for the workspace header.
- ``GET /health`` — module liveness (placeholder).

Auth: admin-only via :func:`app.modules.admin_console.auth.require_admin`.

Error mapping:

- 403 ``admin_required``
- 200 + empty signals + ``quiet_steady_state=True`` (FR-010)
- 500 unexpected (default FastAPI handler)
"""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.modules.admin_console.auth import require_admin
from app.modules.admin_console.decision_signals import service
from app.modules.admin_console.decision_signals.schemas import (
    CommandCenterOverviewResponse,
    DecisionSignalListResponse,
)
from app.api.deps import get_current_user_id_optional as _resolve_user_id_from_jwt

log = structlog.get_logger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# DB session dependency (unused for the seed-only Phase 1 path, kept
# for Phase 2 batch 2 compatibility)
# ---------------------------------------------------------------------------


async def _noop_session():
    """Phase 1 has no DB dependency for the seeded signal surface.

    Phase 2 batch 2 will replace this with the real async session
    dependency when ``list_decision_signals`` is wired to the
    pm_dashboard metric snapshot repository.
    """
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="DB session not wired for decision_signals Phase 1 (seed-only)",
    )


# ---------------------------------------------------------------------------
# Endpoint: GET /signals
# ---------------------------------------------------------------------------


@router.get(
    "/signals",
    response_model=DecisionSignalListResponse,
    status_code=200,
    responses={
        200: {"description": "Prioritized decision-signal queue"},
        403: {"description": "Admin required"},
    },
)
async def get_decision_signals(
    _user_id: Annotated[UUID, Depends(_resolve_user_id_from_jwt)],
    _cap: Annotated[bool, Depends(require_admin)],
    limit: int = Query(50, ge=1, le=200),
) -> DecisionSignalListResponse:
    """Return the prioritized decision-signal queue (FR-007~FR-010)."""
    log.info(
        "command_center.signals.request",
        limit=limit,
    )
    result = service.list_decision_signals()
    if limit < result.total:
        result = result.model_copy(
            update={"signals": result.signals[:limit], "total": len(result.signals[:limit])}
        )
    return result


# ---------------------------------------------------------------------------
# Endpoint: GET /overview
# ---------------------------------------------------------------------------


@router.get(
    "/overview",
    response_model=CommandCenterOverviewResponse,
    status_code=200,
    responses={
        200: {"description": "4 KPI tiles for the workspace header"},
        403: {"description": "Admin required"},
    },
)
async def get_command_center_overview(
    _user_id: Annotated[UUID, Depends(_resolve_user_id_from_jwt)],
    _cap: Annotated[bool, Depends(require_admin)],
) -> CommandCenterOverviewResponse:
    """Return the 4 KPI tiles (Product / AI Quality / AI Cost / System)."""
    return service.get_command_center_overview()


# ---------------------------------------------------------------------------
# Endpoint: GET /health
# ---------------------------------------------------------------------------


@router.get(
    "/health",
    status_code=200,
    responses={200: {"description": "Module liveness"}},
)
async def health() -> dict[str, str]:
    """Module liveness check (parity with /admin-console/observability/health)."""
    return {"status": "ok", "module": "decision_signals"}


__all__ = ["router"]