"""REQ-044 US2 — Product Analytics FastAPI routers (FR-011~FR-015).

Mounted by ``app.main`` at two prefixes:

- ``/api/v1/admin-console/product-analytics`` (exported as
  ``product_analytics_router``) — question templates + funnel +
  cohorts + feature adoption.
- ``/api/v1/admin-console/users`` (exported as ``users_router``) —
  privacy-safe user lookup.

Auth: admin-only via :func:`app.modules.admin_console.auth.require_admin`.

Endpoints:

- ``GET /product-analytics/question-templates`` — 7 tab × ≥3 templates
  (FR-011, AC-11.2).
- ``GET /product-analytics/funnel`` — 5-step funnel with
  entry_conversion + comparison_delta + time_to_convert (FR-012,
  AC-12.1/12.2/12.3).
- ``GET /product-analytics/cohorts`` — cohort list (FR-013, AC-13.1).
- ``GET /product-analytics/feature-adoption`` — 5-metric grid
  (FR-014, AC-14.1/14.2/14.3).
- ``GET /product-analytics/health`` — module liveness.
- ``GET /users/{user_id}`` — privacy-safe user profile (FR-015,
  AC-15.1). Returns 404 for unknown user_ids.

Error mapping:

- 403 ``admin_required``
- 404 ``user_not_found`` for unknown ``user_id``
- 200 + empty data with explicit zero markers (FR-028 valid zero)
- 500 unexpected (default FastAPI handler)
"""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import get_current_user_id_optional as _resolve_user_id_from_jwt
from app.modules.admin_console.auth import require_admin
from app.modules.admin_console.product_analytics import service
from app.modules.admin_console.product_analytics.schemas import (
    CohortListResponse,
    FeatureAdoptionResponse,
    FunnelResponse,
    QuestionTemplateListResponse,
    UserPrivacySafe,
)

log = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------


product_analytics_router = APIRouter()
users_router = APIRouter()


# ---------------------------------------------------------------------------
# Endpoint: GET /question-templates
# ---------------------------------------------------------------------------


@product_analytics_router.get(
    "/question-templates",
    response_model=QuestionTemplateListResponse,
    status_code=200,
    responses={
        200: {"description": "≥21 question templates (3 per tab × 7 tabs)"},
        403: {"description": "Admin required"},
    },
)
async def get_question_templates(
    _user_id: Annotated[UUID, Depends(_resolve_user_id_from_jwt)],
    _cap: Annotated[bool, Depends(require_admin)],
) -> QuestionTemplateListResponse:
    """Return the curated question template list (FR-011)."""
    log.info("product_analytics.question_templates.request")
    return service.list_question_templates()


# ---------------------------------------------------------------------------
# Endpoint: GET /funnel
# ---------------------------------------------------------------------------


@product_analytics_router.get(
    "/funnel",
    response_model=FunnelResponse,
    status_code=200,
    responses={
        200: {"description": "5-step funnel with conversion + drop-off + time-to-convert"},
        403: {"description": "Admin required"},
    },
)
async def get_funnel(
    _user_id: Annotated[UUID, Depends(_resolve_user_id_from_jwt)],
    _cap: Annotated[bool, Depends(require_admin)],
    template_id: str = Query(
        "q-fun-1",
        min_length=1,
        max_length=64,
        description="Question template id (e.g. q-fun-1). Use 'funnel-empty' for EC-1.",
    ),
    cohort_id: str | None = Query(
        default=None,
        max_length=64,
        description="Optional cohort id to scope the funnel.",
    ),
    period_start: str | None = Query(
        default=None,
        max_length=64,
        description="Optional ISO 8601 period start (used by Phase 2 batch 2).",
    ),
    period_end: str | None = Query(
        default=None,
        max_length=64,
        description="Optional ISO 8601 period end (used by Phase 2 batch 2).",
    ),
) -> FunnelResponse:
    """Return a funnel payload (FR-012)."""
    log.info(
        "product_analytics.funnel.request",
        template_id=template_id,
        cohort_id=cohort_id,
        period_start=period_start,
        period_end=period_end,
    )
    return service.get_funnel(
        template_id=template_id,
        cohort_id=cohort_id,
        period_start=period_start,
        period_end=period_end,
    )


# ---------------------------------------------------------------------------
# Endpoint: GET /cohorts
# ---------------------------------------------------------------------------


@product_analytics_router.get(
    "/cohorts",
    response_model=CohortListResponse,
    status_code=200,
    responses={
        200: {"description": "Cohort list (id/name/definition/population/owner/last_computed_at)"},
        403: {"description": "Admin required"},
    },
)
async def get_cohorts(
    _user_id: Annotated[UUID, Depends(_resolve_user_id_from_jwt)],
    _cap: Annotated[bool, Depends(require_admin)],
) -> CohortListResponse:
    """Return the cohort list (FR-013)."""
    log.info("product_analytics.cohorts.request")
    return service.list_cohorts()


# ---------------------------------------------------------------------------
# Endpoint: GET /feature-adoption
# ---------------------------------------------------------------------------


@product_analytics_router.get(
    "/feature-adoption",
    response_model=FeatureAdoptionResponse,
    status_code=200,
    responses={
        200: {"description": "5-metric adoption grid per feature"},
        403: {"description": "Admin required"},
    },
)
async def get_feature_adoption(
    _user_id: Annotated[UUID, Depends(_resolve_user_id_from_jwt)],
    _cap: Annotated[bool, Depends(require_admin)],
    cohort_id: str | None = Query(
        default=None,
        max_length=64,
        description="Optional cohort id to scope the adoption grid.",
    ),
) -> FeatureAdoptionResponse:
    """Return the feature adoption grid (FR-014)."""
    log.info(
        "product_analytics.feature_adoption.request",
        cohort_id=cohort_id,
    )
    return service.get_feature_adoption(cohort_id=cohort_id)


# ---------------------------------------------------------------------------
# Endpoint: GET /health
# ---------------------------------------------------------------------------


@product_analytics_router.get(
    "/health",
    status_code=200,
    responses={200: {"description": "Module liveness"}},
)
async def health() -> dict[str, str]:
    """Module liveness check (parity with /admin-console/command-center/health)."""
    return {"status": "ok", "module": "product_analytics"}


# ---------------------------------------------------------------------------
# Endpoint: GET /users/{user_id}
# ---------------------------------------------------------------------------


@users_router.get(
    "/{user_id}",
    response_model=UserPrivacySafe,
    status_code=200,
    responses={
        200: {"description": "Privacy-safe user profile (allow-listed fields only)"},
        403: {"description": "Admin required"},
        404: {"description": "User not found"},
    },
)
async def get_user_safe_lookup(
    user_id: str,
    _caller_id: Annotated[UUID, Depends(_resolve_user_id_from_jwt)],
    _cap: Annotated[bool, Depends(require_admin)],
) -> UserPrivacySafe:
    """Return the privacy-safe profile for ``user_id`` (FR-015).

    Returns 404 ``USER_NOT_FOUND`` for unknown ids. The schema is the
    canonical FR-032 privacy allow-list — the response MUST NOT contain
    any field named ``raw_resume`` / ``raw_interview_answer`` /
    ``raw_prompt`` / ``raw_model_output`` etc.
    """
    log.info(
        "admin_console.users.lookup.request",
        user_id=user_id,
    )
    profile = service.get_user_safe(user_id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "USER_NOT_FOUND",
                "message": f"未找到 user_id={user_id} 的隐私安全档案",
                "user_id": user_id,
            },
        )
    return profile


__all__ = [
    "PRODUCT_ANALYTICS_VIEW",
    "USER_LOOKUP",
    "product_analytics_router",
    "users_router",
]