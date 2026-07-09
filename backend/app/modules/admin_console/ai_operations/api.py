"""REQ-044 US3 — AI Operations FastAPI router (FR-016~FR-020).

Mounted by ``app.main`` at ``/api/v1/admin-console/ai-operations`` with
9 endpoints (workspace surface; seed-driven for the Phase 1 deliverable).

Auth: admin-only via :func:`app.modules.admin_console.auth.require_admin`.

Endpoints:

- ``GET /kpis`` — workspace header 4 KPI tiles (FR-016, AC-16.1).
- ``GET /volume-by-feature`` — per-area call/success/failure (FR-016,
  AC-16.2).
- ``GET /failure-categories`` — failure pie (FR-016, AC-16.3).
- ``GET /latency-bands`` — p50/p95/p99 per area (FR-016, AC-16.4).
- ``GET /token-usage`` — input vs output tokens (FR-016, AC-16.5).
- ``GET /cost-summary`` — total + per-area cost (FR-016, AC-16.6 + EC-3).
- ``GET /version-selector`` — 4 dimensions × known + unknown
  (FR-017, AC-17.1, EC-2).
- ``GET /quality-issues`` — AI quality issue list with 8 FR-018 links
  (AC-18.1/18.2).
- ``GET /cost-quality-flag`` — cost-quality tradeoff alert
  (FR-019, AC-19.1/19.2).
- ``GET /eval-badcase-summary`` — eval + badcase card (FR-020,
  AC-20.1/20.2).
- ``GET /health`` — module liveness.

Error mapping:

- 403 ``admin_required``
- 500 unexpected (default FastAPI handler)
"""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_user_id_optional as _resolve_user_id_from_jwt
from app.modules.admin_console.ai_operations import service
from app.modules.admin_console.ai_operations.schemas import (
    AIQualityIssueListResponse,
    BadcasePromotionRequest,
    BadcasePromotionResponse,
    CostQualityFlag,
    CostSummaryResponse,
    EvalBadcaseSummary,
    ExperimentCompareRequest,
    ExperimentCompareResponse,
    FailureCategoryResponse,
    KPIBundleResponse,
    LatencyBands,
    PromptProposalCreateRequest,
    PromptProposalResponse,
    TokenUsageResponse,
    VersionSelectorResponse,
    VolumeByFeatureResponse,
)
from app.modules.admin_console.auth import require_admin

log = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------


router = APIRouter()


# ---------------------------------------------------------------------------
# Endpoint: GET /kpis
# ---------------------------------------------------------------------------


@router.get(
    "/kpis",
    response_model=KPIBundleResponse,
    status_code=200,
    responses={
        200: {"description": "4 KPI tiles (total_volume / success_rate / p95_latency / total_cost)"},
        403: {"description": "Admin required"},
    },
)
async def get_kpis(
    _user_id: Annotated[UUID, Depends(_resolve_user_id_from_jwt)],
    _cap: Annotated[bool, Depends(require_admin)],
) -> KPIBundleResponse:
    """Return the workspace KPI bundle (FR-016 + AC-16.1)."""
    log.info("ai_operations.kpis.request")
    return service.get_kpis()


# ---------------------------------------------------------------------------
# Endpoint: GET /volume-by-feature
# ---------------------------------------------------------------------------


@router.get(
    "/volume-by-feature",
    response_model=VolumeByFeatureResponse,
    status_code=200,
    responses={
        200: {"description": "Per-area AI task volume (bar chart)"},
        403: {"description": "Admin required"},
    },
)
async def get_volume_by_feature(
    _user_id: Annotated[UUID, Depends(_resolve_user_id_from_jwt)],
    _cap: Annotated[bool, Depends(require_admin)],
    feature_area: str | None = Query(
        default=None,
        max_length=64,
        description=(
            "Optional FeatureArea filter (Phase 2 batch 3 uses this; "
            "Phase 1 returns the full 4-area payload)."
        ),
    ),
) -> VolumeByFeatureResponse:
    """Return per-area AI task volume (FR-016 + AC-16.2)."""
    log.info(
        "ai_operations.volume_by_feature.request",
        feature_area=feature_area,
    )
    return service.get_volume_by_feature()


# ---------------------------------------------------------------------------
# Endpoint: GET /failure-categories
# ---------------------------------------------------------------------------


@router.get(
    "/failure-categories",
    response_model=FailureCategoryResponse,
    status_code=200,
    responses={
        200: {"description": "Failure-category breakdown (pie chart)"},
        403: {"description": "Admin required"},
    },
)
async def get_failure_categories(
    _user_id: Annotated[UUID, Depends(_resolve_user_id_from_jwt)],
    _cap: Annotated[bool, Depends(require_admin)],
) -> FailureCategoryResponse:
    """Return failure category breakdown (FR-016 + AC-16.3)."""
    log.info("ai_operations.failure_categories.request")
    return service.get_failure_categories()


# ---------------------------------------------------------------------------
# Endpoint: GET /latency-bands
# ---------------------------------------------------------------------------


@router.get(
    "/latency-bands",
    response_model=LatencyBands,
    status_code=200,
    responses={
        200: {"description": "p50/p95/p99 latency bands per FeatureArea"},
        403: {"description": "Admin required"},
    },
)
async def get_latency_bands(
    _user_id: Annotated[UUID, Depends(_resolve_user_id_from_jwt)],
    _cap: Annotated[bool, Depends(require_admin)],
    feature_area: str | None = Query(
        default=None,
        max_length=64,
        description=(
            "Optional FeatureArea filter (Phase 2 batch 3 narrows the "
            "line chart to one area; Phase 1 returns all 4 areas)."
        ),
    ),
) -> LatencyBands:
    """Return p50/p95/p99 latency per FeatureArea (FR-016 + AC-16.4)."""
    log.info(
        "ai_operations.latency_bands.request",
        feature_area=feature_area,
    )
    return service.get_latency_bands()


# ---------------------------------------------------------------------------
# Endpoint: GET /token-usage
# ---------------------------------------------------------------------------


@router.get(
    "/token-usage",
    response_model=TokenUsageResponse,
    status_code=200,
    responses={
        200: {"description": "Per-area token usage (input vs output stacked bar)"},
        403: {"description": "Admin required"},
    },
)
async def get_token_usage(
    _user_id: Annotated[UUID, Depends(_resolve_user_id_from_jwt)],
    _cap: Annotated[bool, Depends(require_admin)],
) -> TokenUsageResponse:
    """Return token-usage breakdown (FR-016 + AC-16.5)."""
    log.info("ai_operations.token_usage.request")
    return service.get_token_usage()


# ---------------------------------------------------------------------------
# Endpoint: GET /cost-summary
# ---------------------------------------------------------------------------


@router.get(
    "/cost-summary",
    response_model=CostSummaryResponse,
    status_code=200,
    responses={
        200: {"description": "Cost summary (total + per FeatureArea breakdown)"},
        403: {"description": "Admin required"},
    },
)
async def get_cost_summary(
    _user_id: Annotated[UUID, Depends(_resolve_user_id_from_jwt)],
    _cap: Annotated[bool, Depends(require_admin)],
) -> CostSummaryResponse:
    """Return cost summary card (FR-016 + AC-16.6 + EC-3).

    ``stale=True`` when the last-reconciled date is older than 14
    days (EC-3 surface for the "cost estimate outdated" flag).
    """
    log.info("ai_operations.cost_summary.request")
    return service.get_cost_summary()


# ---------------------------------------------------------------------------
# Endpoint: GET /version-selector
# ---------------------------------------------------------------------------


@router.get(
    "/version-selector",
    response_model=VersionSelectorResponse,
    status_code=200,
    responses={
        200: {"description": "4 version dimensions + known values + unknown counts"},
        403: {"description": "Admin required"},
    },
)
async def get_version_selector(
    _user_id: Annotated[UUID, Depends(_resolve_user_id_from_jwt)],
    _cap: Annotated[bool, Depends(require_admin)],
) -> VersionSelectorResponse:
    """Return version-selector availability (FR-017 + AC-17.1 + EC-2)."""
    log.info("ai_operations.version_selector.request")
    return service.get_version_selector()


# ---------------------------------------------------------------------------
# Endpoint: GET /quality-issues
# ---------------------------------------------------------------------------


@router.get(
    "/quality-issues",
    response_model=AIQualityIssueListResponse,
    status_code=200,
    responses={
        200: {"description": "AI quality issue list (each carries 8 FR-018 link fields)"},
        403: {"description": "Admin required"},
    },
)
async def get_quality_issues(
    _user_id: Annotated[UUID, Depends(_resolve_user_id_from_jwt)],
    _cap: Annotated[bool, Depends(require_admin)],
) -> AIQualityIssueListResponse:
    """Return the AI quality issue list (FR-018 + AC-18.1/18.2)."""
    log.info("ai_operations.quality_issues.request")
    return service.list_quality_issues()


# ---------------------------------------------------------------------------
# Endpoint: GET /cost-quality-flag
# ---------------------------------------------------------------------------


@router.get(
    "/cost-quality-flag",
    response_model=CostQualityFlag,
    status_code=200,
    responses={
        200: {"description": "Cost-quality tradeoff flag (FR-019)"},
        403: {"description": "Admin required"},
    },
)
async def get_cost_quality_flag(
    _user_id: Annotated[UUID, Depends(_resolve_user_id_from_jwt)],
    _cap: Annotated[bool, Depends(require_admin)],
) -> CostQualityFlag:
    """Return the cost-quality tradeoff flag (FR-019 + AC-19.1/19.2)."""
    log.info("ai_operations.cost_quality_flag.request")
    return service.get_cost_quality_flag()


# ---------------------------------------------------------------------------
# Endpoint: GET /eval-badcase-summary
# ---------------------------------------------------------------------------


@router.get(
    "/eval-badcase-summary",
    response_model=EvalBadcaseSummary,
    status_code=200,
    responses={
        200: {"description": "Eval + badcase summary card (FR-020)"},
        403: {"description": "Admin required"},
    },
)
async def get_eval_badcase_summary(
    _user_id: Annotated[UUID, Depends(_resolve_user_id_from_jwt)],
    _cap: Annotated[bool, Depends(require_admin)],
) -> EvalBadcaseSummary:
    """Return the eval + badcase summary card (FR-020 + AC-20.1/20.2)."""
    log.info("ai_operations.eval_badcase_summary.request")
    return service.get_eval_badcase_summary()


# ---------------------------------------------------------------------------
# Endpoint: POST /experiment-compare
# ---------------------------------------------------------------------------


@router.post(
    "/experiment-compare",
    response_model=ExperimentCompareResponse,
    status_code=200,
    responses={
        200: {"description": "Baseline/candidate eval comparison"},
        403: {"description": "Admin required"},
    },
)
async def post_experiment_compare(
    request: ExperimentCompareRequest,
    _user_id: Annotated[UUID, Depends(_resolve_user_id_from_jwt)],
    _cap: Annotated[bool, Depends(require_admin)],
) -> ExperimentCompareResponse:
    """Compare baseline and candidate eval reports for PM/admin review."""
    log.info("ai_operations.experiment_compare.request")
    return service.compare_eval_reports(
        baseline=request.baseline,
        candidate=request.candidate,
        min_quality_delta=request.min_quality_delta,
    )


# ---------------------------------------------------------------------------
# Endpoint: POST /badcase-promotions
# ---------------------------------------------------------------------------


@router.post(
    "/badcase-promotions",
    response_model=BadcasePromotionResponse,
    status_code=200,
    responses={
        200: {"description": "Promote badcase into eval dataset lifecycle"},
        403: {"description": "Admin required"},
    },
)
async def post_badcase_promotion(
    request: BadcasePromotionRequest,
    _user_id: Annotated[UUID, Depends(_resolve_user_id_from_jwt)],
    _cap: Annotated[bool, Depends(require_admin)],
) -> BadcasePromotionResponse:
    """Promote a governed badcase into candidate/report-only eval data."""
    log.info("ai_operations.badcase_promotion.request")
    return service.promote_badcase_for_eval(
        badcase=request.badcase,
        lifecycle=request.lifecycle,
        dataset_version=request.dataset_version,
        export_policy_decision_id=request.export_policy_decision_id,
        reviewer=request.reviewer,
        reason=request.reason,
    )


# ---------------------------------------------------------------------------
# Endpoint: POST /prompt-proposals
# ---------------------------------------------------------------------------


@router.post(
    "/prompt-proposals",
    response_model=PromptProposalResponse,
    status_code=200,
    responses={
        200: {"description": "Create prompt proposal for human review"},
        403: {"description": "Admin required"},
    },
)
async def post_prompt_proposal(
    request: PromptProposalCreateRequest,
    _user_id: Annotated[UUID, Depends(_resolve_user_id_from_jwt)],
    _cap: Annotated[bool, Depends(require_admin)],
) -> PromptProposalResponse:
    """Create a prompt proposal. This endpoint never auto-deploys changes."""
    log.info("ai_operations.prompt_proposal.request")
    return service.create_prompt_proposal_for_review(
        source_run_ids=request.source_run_ids,
        source_case_ids=request.source_case_ids,
        target_graph=request.target_graph,
        target_node=request.target_node,
        candidate_fingerprint=request.candidate_fingerprint,
        expected_impact=request.expected_impact,
    )


# ---------------------------------------------------------------------------
# Endpoint: GET /health
# ---------------------------------------------------------------------------


@router.get(
    "/health",
    status_code=200,
    responses={200: {"description": "Module liveness"}},
)
async def health() -> dict[str, str]:
    """Module liveness check (parity with /command-center/health)."""
    return {"status": "ok", "module": "ai_operations"}


__all__ = ["router"]
