"""REQ-033 US1 — PM Dashboard API routes (T073).

FastAPI router for the PM Dashboard V1 endpoints (US1):

- ``GET /api/v1/pm-dashboard/health`` — process-local liveness (T022
  placeholder, retained).
- ``GET /api/v1/pm-dashboard/metrics/overview`` — product overview panel.
- ``GET /api/v1/pm-dashboard/metrics/funnel`` — core funnel panel.

Both metrics endpoints:

- Accept the shared ``DashboardFilter`` query params (date range +
  optional version dimensions).
- Return a top-level envelope: ``{"panels": [...], "freshness_at": ...,
  "request_id": "..."}``.
- Map ``ValueError`` → 400 (bad filter), missing/invalid required →
  422 (FastAPI's default validation), internal → 500.

Auth: ``require_pm`` is a stub dependency that returns ``user_id``. In
production this will resolve the user from the session cookie and verify
the PM role; for MVP a fixed ``user_id`` is returned so the contract is
end-to-end testable without auth infra. Tests override it via
``app.dependency_overrides``.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, AsyncIterator, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_session_no_rls, set_rls_user_id
from app.modules.pm_dashboard import service as dashboard_service
from app.modules.pm_dashboard.schemas import DashboardFilter, PanelResponse

router = APIRouter()


# ---------------------------------------------------------------------------
# Auth stub (T073)
# ---------------------------------------------------------------------------


async def require_pm() -> UUID:
    """Stub PM auth dependency.

    MVP behaviour: always raises 401. Tests override this dependency
    via ``app.dependency_overrides[require_pm] = ...`` to inject a real
    ``user_id``. A production-grade resolver will land in a later US
    and replace this body.
    """
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="pm auth not configured for this environment",
    )


# ---------------------------------------------------------------------------
# DB session dependency with RLS pre-set
# ---------------------------------------------------------------------------


async def _db_session_with_rls(
    user_id: UUID = Depends(require_pm),
) -> AsyncIterator[AsyncSession]:
    """Yield an async session whose RLS GUC is bound to ``user_id``.

    Wraps :func:`app.core.db.get_db_session_no_rls` and explicitly
    ``SET LOCAL app.user_id`` so the product_events / badcases rows are
    scoped to the caller's user.
    """
    async for session in get_db_session_no_rls():
        await set_rls_user_id(session, user_id)
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        return


# ---------------------------------------------------------------------------
# Helper — parse a DashboardFilter from query params
# ---------------------------------------------------------------------------


def _parse_filters(
    date_range_start: str,
    date_range_end: str,
    environment: Optional[str] = None,
    release_stage: Optional[str] = None,
    app_version: Optional[str] = None,
    prompt_fingerprint: Optional[str] = None,
    rubric_version: Optional[str] = None,
    model: Optional[str] = None,
    experiment_id: Optional[str] = None,
    graph: Optional[str] = None,
    node: Optional[str] = None,
) -> DashboardFilter:
    """Build a DashboardFilter from query strings, mapping errors to 400/422.

    - Bad date strings → 400 (parse error from the service layer).
    - Bad enum values (Pydantic) → 422 (FastAPI validation).
    """
    # Try to parse dates as ISO 8601 first; surface failures as 400.
    try:
        start_dt = datetime.fromisoformat(date_range_start.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "INVALID_DATE", "message": str(exc)},
        ) from exc
    try:
        end_dt = datetime.fromisoformat(date_range_end.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "INVALID_DATE", "message": str(exc)},
        ) from exc

    try:
        return DashboardFilter(
            date_range_start=start_dt,
            date_range_end=end_dt,
            environment=environment,
            release_stage=release_stage,
            app_version=app_version,
            prompt_fingerprint=prompt_fingerprint,
            rubric_version=rubric_version,
            model=model,
            experiment_id=experiment_id,
            graph=graph,
            node=node,
        )
    except ValidationError as exc:
        # Pydantic validation error → 422 with structured body.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "VALIDATION_ERROR", "message": str(exc)},
        ) from exc


# ---------------------------------------------------------------------------
# T022 — process-local liveness
# ---------------------------------------------------------------------------


@router.get("/health", status_code=200)
async def health() -> dict[str, str]:
    """Process-local liveness check for the pm_dashboard router."""
    return {"status": "ok", "module": "pm_dashboard", "stage": "us1"}


# ---------------------------------------------------------------------------
# T073 — overview + funnel endpoints
# ---------------------------------------------------------------------------


@router.get("/metrics/overview")
async def get_overview(
    date_range_start: str = Query(
        ...,
        description="Inclusive ISO 8601 lower bound for the period.",
    ),
    date_range_end: str = Query(
        ...,
        description="Exclusive ISO 8601 upper bound for the period.",
    ),
    environment: Optional[str] = Query(default=None),
    release_stage: Optional[str] = Query(default=None),
    app_version: Optional[str] = Query(default=None),
    prompt_fingerprint: Optional[str] = Query(default=None),
    rubric_version: Optional[str] = Query(default=None),
    model: Optional[str] = Query(default=None),
    experiment_id: Optional[str] = Query(default=None),
    graph: Optional[str] = Query(default=None),
    node: Optional[str] = Query(default=None),
    session: AsyncSession = Depends(_db_session_with_rls),
) -> dict[str, Any]:
    """Return the product overview panel (FR-002)."""
    filters = _parse_filters(
        date_range_start=date_range_start,
        date_range_end=date_range_end,
        environment=environment,
        release_stage=release_stage,
        app_version=app_version,
        prompt_fingerprint=prompt_fingerprint,
        rubric_version=rubric_version,
        model=model,
        experiment_id=experiment_id,
        graph=graph,
        node=node,
    )
    try:
        panels: list[PanelResponse[Any]] = await dashboard_service.get_overview(
            session, filters
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "INVALID_FILTER", "message": str(exc)},
        ) from exc

    freshness = panels[0].freshness_at if panels else "unknown"
    return {
        "panels": [p.model_dump(by_alias=True, mode="json") for p in panels],
        "freshness_at": freshness,
        "request_id": str(panels[0].metric_id) if panels else "",
    }


@router.get("/metrics/funnel")
async def get_funnel(
    date_range_start: str = Query(
        ...,
        description="Inclusive ISO 8601 lower bound for the period.",
    ),
    date_range_end: str = Query(
        ...,
        description="Exclusive ISO 8601 upper bound for the period.",
    ),
    environment: Optional[str] = Query(default=None),
    release_stage: Optional[str] = Query(default=None),
    app_version: Optional[str] = Query(default=None),
    prompt_fingerprint: Optional[str] = Query(default=None),
    rubric_version: Optional[str] = Query(default=None),
    model: Optional[str] = Query(default=None),
    experiment_id: Optional[str] = Query(default=None),
    graph: Optional[str] = Query(default=None),
    node: Optional[str] = Query(default=None),
    session: AsyncSession = Depends(_db_session_with_rls),
) -> dict[str, Any]:
    """Return the core funnel panel (FR-006)."""
    filters = _parse_filters(
        date_range_start=date_range_start,
        date_range_end=date_range_end,
        environment=environment,
        release_stage=release_stage,
        app_version=app_version,
        prompt_fingerprint=prompt_fingerprint,
        rubric_version=rubric_version,
        model=model,
        experiment_id=experiment_id,
        graph=graph,
        node=node,
    )
    try:
        panels: list[PanelResponse[Any]] = await dashboard_service.get_funnel(
            session, filters
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "INVALID_FILTER", "message": str(exc)},
        ) from exc

    freshness = panels[0].freshness_at if panels else "unknown"
    return {
        "panel": panels[0].model_dump(by_alias=True, mode="json")
        if panels
        else None,
        "freshness_at": freshness,
        "request_id": str(panels[0].metric_id) if panels else "",
    }


# ---------------------------------------------------------------------------
# T087 - Resume Diagnosis endpoint (US2)
# ---------------------------------------------------------------------------


@router.get("/metrics/resume-diagnosis")
async def get_resume_diagnosis(
    date_range_start: str = Query(
        ...,
        description="Inclusive ISO 8601 lower bound for the period.",
    ),
    date_range_end: str = Query(
        ...,
        description="Exclusive ISO 8601 upper bound for the period.",
    ),
    environment: Optional[str] = Query(default=None),
    release_stage: Optional[str] = Query(default=None),
    app_version: Optional[str] = Query(default=None),
    prompt_fingerprint: Optional[str] = Query(default=None),
    rubric_version: Optional[str] = Query(default=None),
    model: Optional[str] = Query(default=None),
    experiment_id: Optional[str] = Query(default=None),
    graph: Optional[str] = Query(default=None),
    node: Optional[str] = Query(default=None),
    session: AsyncSession = Depends(_db_session_with_rls),
) -> dict[str, Any]:
    """Return the resume diagnosis panel (US2 FR).

    Surfaces the 5 core metrics:
    - success rate (count + rate)
    - report views (count)
    - suggestions shown (count)
    - suggestions accepted (count)
    - acceptance rate + score delta (avg after - avg before)

    Same filter set as overview/funnel. Empty window returns 0 values
    + ``quality_flags.partial_data=true`` + ``freshness_at="unknown"``
    per SC-009.

    Error mapping (mirrors US1):
    - ``ValueError`` -> 400 (bad filter)
    - missing/invalid required -> 422 (FastAPI Query validation)
    """
    filters = _parse_filters(
        date_range_start=date_range_start,
        date_range_end=date_range_end,
        environment=environment,
        release_stage=release_stage,
        app_version=app_version,
        prompt_fingerprint=prompt_fingerprint,
        rubric_version=rubric_version,
        model=model,
        experiment_id=experiment_id,
        graph=graph,
        node=node,
    )
    try:
        panels: list[PanelResponse[Any]] = (
            await dashboard_service.get_resume_diagnosis(session, filters)
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "INVALID_FILTER", "message": str(exc)},
        ) from exc

    freshness = panels[0].freshness_at if panels else "unknown"
    return {
        "panel": panels[0].model_dump(by_alias=True, mode="json")
        if panels
        else None,
        "freshness_at": freshness,
        "request_id": str(panels[0].metric_id) if panels else "",
    }


__all__ = ["require_pm", "router"]