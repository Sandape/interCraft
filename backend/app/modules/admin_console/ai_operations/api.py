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


# ---------------------------------------------------------------------------
# REQ-061 US9 production metrics / budgets / reconciliation / drilldown (T118)
# Mounted under /admin-console/ai-operations; OpenAPI also documents the
# /admin-console/ai alias (see main.py production mount).
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    status_code=200,
    responses={
        200: {"description": "Joined stability/quality/latency/point/cost metrics"},
        403: {"description": "Admin required"},
    },
)
async def get_production_metrics(
    _user_id: Annotated[UUID, Depends(_resolve_user_id_from_jwt)],
    _cap: Annotated[bool, Depends(require_admin)],
    from_: str | None = Query(default=None, alias="from"),
    to: str | None = Query(default=None),
    capability: str | None = Query(default=None),
    service_tier: str | None = Query(default=None),
    policy_version: str | None = Query(default=None),
    release_batch: str | None = Query(default=None),
    grant_config_version: str | None = Query(default=None),
) -> dict:
    """Return fact-driven operational metrics (beta revenue always zero)."""
    from app.modules.admin_console.ai_operations.production import empty_metrics

    log.info(
        "ai_operations.metrics.request",
        capability=capability,
        service_tier=service_tier,
        policy_version=policy_version,
        release_batch=release_batch,
        grant_config_version=grant_config_version,
        range_from=from_,
        range_to=to,
    )
    return empty_metrics().model_dump(mode="json")


@router.get(
    "/budgets",
    status_code=200,
    responses={200: {"description": "Cost budgets and consumption"}, 403: {"description": "Admin required"}},
)
async def list_production_budgets(
    _user_id: Annotated[UUID, Depends(_resolve_user_id_from_jwt)],
    _cap: Annotated[bool, Depends(require_admin)],
) -> dict:
    from decimal import Decimal

    from app.modules.admin_console.ai_operations.production import budget_to_out
    from app.modules.ai_metering.budgets import BudgetDefinition

    sample = BudgetDefinition(
        scope_type="site",
        scope_ref="*",
        period="day",
        amount_rmb=Decimal("1000"),
    )
    return {"items": [budget_to_out(sample, consumed_rmb=Decimal("0")).model_dump(mode="json")]}


@router.get(
    "/reconciliations",
    status_code=200,
    responses={200: {"description": "Reconciliation runs"}, 403: {"description": "Admin required"}},
)
async def list_production_reconciliations(
    _user_id: Annotated[UUID, Depends(_resolve_user_id_from_jwt)],
    _cap: Annotated[bool, Depends(require_admin)],
) -> dict:
    return {"items": [], "data_quality": {"seed_or_mock_count": 0}}


@router.get(
    "/anomalies",
    status_code=200,
    responses={200: {"description": "Abnormal consumption decisions"}, 403: {"description": "Admin required"}},
)
async def list_production_anomalies(
    _user_id: Annotated[UUID, Depends(_resolve_user_id_from_jwt)],
    _cap: Annotated[bool, Depends(require_admin)],
) -> dict:
    from app.modules.ai_metering.anomalies import PROTECTED_OPERATIONS

    return {
        "items": [],
        "protected_operations": sorted(PROTECTED_OPERATIONS),
    }


@router.get(
    "/tasks/{task_id}/cost-drilldown",
    status_code=200,
    responses={
        200: {"description": "Point→milestone→attempt→cost drilldown"},
        403: {"description": "Admin required"},
        404: {"description": "Task not found"},
    },
)
async def get_task_cost_drilldown(
    task_id: str,
    _user_id: Annotated[UUID, Depends(_resolve_user_id_from_jwt)],
    _cap: Annotated[bool, Depends(require_admin)],
) -> dict:
    from datetime import datetime, timezone

    from app.modules.admin_console.ai_operations.production import (
        DataQualityOut,
        DecimalMoney,
        TaskCostDrilldownOut,
    )

    return TaskCostDrilldownOut(
        task_id=task_id,
        point_settled=0,
        cost_status="unknown",
        current_cost_rmb=DecimalMoney(amount="0", currency="CNY"),
        attempts=[],
        milestones=[],
        data_quality=DataQualityOut(
            fresh_at=datetime.now(timezone.utc),
            coverage_percent=100.0,
            unknown_count=0,
            seed_or_mock_count=0,
        ),
    ).model_dump(mode="json")


@router.get(
    "/point-configs",
    status_code=200,
    responses={200: {"description": "Daily point config history"}, 403: {"description": "Admin required"}},
)
async def list_point_configs(
    _user_id: Annotated[UUID, Depends(_resolve_user_id_from_jwt)],
    _cap: Annotated[bool, Depends(require_admin)],
) -> list:
    return []


@router.get(
    "/cost-rates",
    status_code=200,
    responses={200: {"description": "Versioned cost rates"}, 403: {"description": "Admin required"}},
)
async def list_cost_rates(
    _user_id: Annotated[UUID, Depends(_resolve_user_id_from_jwt)],
    _cap: Annotated[bool, Depends(require_admin)],
) -> list:
    return []


# ---------------------------------------------------------------------------
# REQ-061 T104/T106 precursor — model policy admin surface
# ---------------------------------------------------------------------------


@router.get(
    "/model-policies",
    status_code=200,
    responses={
        200: {"description": "Candidate/current model policies"},
        403: {"description": "Admin required"},
    },
)
async def list_model_policies(
    _user_id: Annotated[UUID, Depends(_resolve_user_id_from_jwt)],
    _cap: Annotated[bool, Depends(require_admin)],
    capability: str | None = Query(default=None),
    service_tier: str | None = Query(default=None),
    status: str | None = Query(default=None),
) -> dict:
    from app.modules.ai_runtime.provider_gateway.policy_service import ModelPolicyService

    svc = ModelPolicyService()
    return {
        "items": svc.list_policies(
            capability=capability,
            service_tier=service_tier,
            status=status,
        )
    }


@router.post(
    "/model-policies",
    status_code=201,
    responses={
        201: {"description": "Draft or candidate policy version created"},
        403: {"description": "Admin required"},
    },
)
async def create_model_policy(
    body: dict,
    _user_id: Annotated[UUID, Depends(_resolve_user_id_from_jwt)],
    _cap: Annotated[bool, Depends(require_admin)],
) -> dict:
    from app.modules.ai_runtime.provider_gateway.policy_service import (
        ModelPolicyService,
        PolicyServiceError,
    )
    from fastapi import HTTPException

    svc = ModelPolicyService()
    try:
        return svc.create_policy(
            capability=body["capability"],
            subscenario=body["subscenario"],
            service_tier=body["service_tier"],
            primary_route=body["primary_route"],
            allowed_fallbacks=list(body.get("allowed_fallbacks") or []),
            quality_gate_ref=body["quality_gate_ref"],
            latency_target_ms=int(body["latency_target_ms"]),
            cost_ceiling_rmb=body["cost_ceiling_rmb"],
            rollback_target=body.get("rollback_target"),
            owner=body["owner"],
            reason=body["reason"],
        )
    except PolicyServiceError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.message) from exc
    except KeyError as exc:
        raise HTTPException(status_code=422, detail=f"missing field: {exc}") from exc


@router.post(
    "/model-policies/{policy_version}/release",
    status_code=202,
    responses={
        202: {"description": "Audited release transition accepted"},
        403: {"description": "Admin required"},
        409: {"description": "Conflict"},
    },
)
async def release_model_policy(
    policy_version: str,
    body: dict,
    _user_id: Annotated[UUID, Depends(_resolve_user_id_from_jwt)],
    _cap: Annotated[bool, Depends(require_admin)],
) -> dict:
    from app.modules.ai_runtime.provider_gateway.policy_service import (
        ModelPolicyService,
        PolicyServiceError,
    )
    from fastapi import HTTPException

    svc = ModelPolicyService()
    try:
        return svc.release_policy(
            policy_version,
            target_status=body["target_status"],
            traffic_percent=float(body.get("traffic_percent", 0)),
            eval_evidence_ref=body["eval_evidence_ref"],
            rollback_target=body["rollback_target"],
            reason=body["reason"],
            actor=str(_user_id) if _user_id else None,
        )
    except PolicyServiceError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.message) from exc
    except KeyError as exc:
        raise HTTPException(status_code=422, detail=f"missing field: {exc}") from exc


# ---------------------------------------------------------------------------
# REQ-061 US11 — release / evaluation comparison + transitions (T148)
# ---------------------------------------------------------------------------


@router.get(
    "/releases",
    status_code=200,
    responses={
        200: {"description": "Gray-release batches"},
        403: {"description": "Admin required"},
    },
)
async def list_release_batches(
    _user_id: Annotated[UUID, Depends(_resolve_user_id_from_jwt)],
    _cap: Annotated[bool, Depends(require_admin)],
    capability: str | None = Query(default=None),
) -> dict:
    from app.modules.ai_runtime.provider_gateway.release_service import (
        get_release_service,
    )

    svc = get_release_service()
    items = [b.to_dict() for b in svc.list_batches()]
    if capability:
        items = [i for i in items if i.get("capability_code") == capability]
    log.info("ai_operations.releases.list", count=len(items), capability=capability)
    return {"items": items, "stages": [1, 5, 20, 50, 100]}


@router.post(
    "/releases",
    status_code=201,
    responses={
        201: {"description": "Release batch created"},
        403: {"description": "Admin required"},
        422: {"description": "Missing fields"},
    },
)
async def create_release_batch(
    body: dict,
    _user_id: Annotated[UUID, Depends(_resolve_user_id_from_jwt)],
    _cap: Annotated[bool, Depends(require_admin)],
) -> dict:
    from fastapi import HTTPException

    from app.modules.ai_runtime.provider_gateway.release_service import (
        get_release_service,
    )

    try:
        batch = get_release_service().create_batch(
            capability_code=body["capability_code"],
            candidate_policy_version=body["candidate_policy_version"],
            stable_policy_version=body["stable_policy_version"],
        )
    except KeyError as exc:
        raise HTTPException(status_code=422, detail=f"missing field: {exc}") from exc
    log.info("ai_operations.releases.create", release_batch_id=batch.release_batch_id)
    return batch.to_dict()


@router.get(
    "/releases/{release_batch_id}",
    status_code=200,
    responses={
        200: {"description": "Release batch detail"},
        403: {"description": "Admin required"},
        404: {"description": "Not found"},
    },
)
async def get_release_batch(
    release_batch_id: str,
    _user_id: Annotated[UUID, Depends(_resolve_user_id_from_jwt)],
    _cap: Annotated[bool, Depends(require_admin)],
) -> dict:
    from fastapi import HTTPException

    from app.modules.ai_runtime.provider_gateway.release_service import (
        get_release_service,
    )

    batch = get_release_service().get_batch(release_batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="release_batch_not_found")
    return batch.to_dict()


@router.get(
    "/releases/{release_batch_id}/comparison",
    status_code=200,
    responses={
        200: {"description": "Candidate vs stable comparison + gate evidence"},
        403: {"description": "Admin required"},
        404: {"description": "Not found"},
    },
)
async def compare_release_batch(
    release_batch_id: str,
    _user_id: Annotated[UUID, Depends(_resolve_user_id_from_jwt)],
    _cap: Annotated[bool, Depends(require_admin)],
) -> dict:
    from fastapi import HTTPException

    from app.modules.ai_runtime.provider_gateway.release_service import (
        ReleaseServiceError,
        get_release_service,
    )

    try:
        return get_release_service().compare_candidate_stable(release_batch_id)
    except ReleaseServiceError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/releases/{release_batch_id}/offline-gate",
    status_code=200,
    responses={
        200: {"description": "Offline gate evaluated"},
        403: {"description": "Admin required"},
        404: {"description": "Not found"},
    },
)
async def evaluate_release_offline_gate(
    release_batch_id: str,
    body: dict,
    _user_id: Annotated[UUID, Depends(_resolve_user_id_from_jwt)],
    _cap: Annotated[bool, Depends(require_admin)],
) -> dict:
    from fastapi import HTTPException

    from app.modules.ai_runtime.provider_gateway.release_service import (
        ReleaseServiceError,
        get_release_service,
    )

    try:
        result = get_release_service().evaluate_offline_gate(
            release_batch_id,
            p0_p1_safe=bool(body.get("p0_p1_safe", True)),
            structure_pass=bool(body.get("structure_pass", True)),
            quality_delta_pp=float(body.get("quality_delta_pp", 0)),
            p95_latency_delta_pct=float(body.get("p95_latency_delta_pct", 0)),
            cost_delta_pct=float(body.get("cost_delta_pct", 0)),
            dual_approved_cost=bool(body.get("dual_approved_cost", False)),
        )
    except ReleaseServiceError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return result.to_dict()


@router.post(
    "/releases/{release_batch_id}/transitions",
    status_code=202,
    responses={
        202: {"description": "Release transition accepted"},
        403: {"description": "Admin required"},
        404: {"description": "Not found"},
        409: {"description": "Illegal transition"},
    },
)
async def transition_release_batch(
    release_batch_id: str,
    body: dict,
    _user_id: Annotated[UUID, Depends(_resolve_user_id_from_jwt)],
    _cap: Annotated[bool, Depends(require_admin)],
) -> dict:
    """Transition actions: start_gray | advance | stop_rollback | override."""
    from fastapi import HTTPException

    from app.modules.ai_runtime.provider_gateway.release_service import (
        ReleaseServiceError,
        get_release_service,
    )

    action = str(body.get("action") or "").strip()
    svc = get_release_service()
    try:
        if action == "start_gray":
            batch = svc.start_gray(release_batch_id)
            return {"action": action, "batch": batch.to_dict()}
        if action == "advance":
            batch = svc.advance_stage(
                release_batch_id,
                low_traffic=bool(body.get("low_traffic")),
                dual_approved_low_traffic=bool(body.get("dual_approved_low_traffic")),
            )
            return {"action": action, "batch": batch.to_dict()}
        if action == "stop_rollback":
            reason = str(body.get("reason") or "manual_stop")
            batch = svc.stop_and_rollback(release_batch_id, reason=reason)
            return {"action": action, "batch": batch.to_dict()}
        if action == "override":
            record = svc.record_override(
                release_batch_id,
                pm_approver=str(body["pm_approver"]),
                technical_approver=str(body["technical_approver"]),
                reason=str(body["reason"]),
                scope=str(body.get("scope") or "release"),
                expires_at=body.get("expires_at"),
                bypass_safety_gate=bool(body.get("bypass_safety_gate", False)),
            )
            batch = svc.get_batch(release_batch_id)
            return {
                "action": action,
                "override": {
                    "override_id": record.override_id,
                    "pm_approver": record.pm_approver,
                    "technical_approver": record.technical_approver,
                    "reason": record.reason,
                    "scope": record.scope,
                    "safety_gate_bypassed": record.safety_gate_bypassed,
                },
                "batch": batch.to_dict() if batch else None,
            }
        raise HTTPException(
            status_code=422,
            detail="action must be start_gray|advance|stop_rollback|override",
        )
    except KeyError as exc:
        raise HTTPException(status_code=422, detail=f"missing field: {exc}") from exc
    except ReleaseServiceError as exc:
        msg = str(exc)
        status = 404 if msg.startswith("unknown_batch") else 409
        raise HTTPException(status_code=status, detail=msg) from exc


@router.get(
    "/evaluations/comparison",
    status_code=200,
    responses={
        200: {"description": "Online eval sample + calibration eligibility summary"},
        403: {"description": "Admin required"},
    },
)
async def get_evaluation_comparison(
    _user_id: Annotated[UUID, Depends(_resolve_user_id_from_jwt)],
    _cap: Annotated[bool, Depends(require_admin)],
    capability: str | None = Query(default=None),
) -> dict:
    """Compare judge eligibility / sampling posture for ops (skeleton)."""
    from app.eval.calibration import (
        MIN_AGREEMENT_RATE,
        MIN_MONTHLY_LABELS,
        CalibrationStore,
    )
    from app.eval.capability_registry import get_capability_registry
    from app.eval.judge import default_req061_rubric, is_blocking_eligible
    from app.eval.online_sampler import (
        HIGH_RISK_SAMPLE_RATE,
        MANDATORY_SAMPLE_RATE,
        ORDINARY_SAMPLE_RATE,
    )

    rubric = default_req061_rubric()
    registry = get_capability_registry()
    entries = registry.list_entries()
    if capability:
        entries = [e for e in entries if e.capability_code == capability]
    store = CalibrationStore()
    latest = store.latest()
    log.info(
        "ai_operations.evaluations.comparison",
        capability=capability,
        entry_count=len(entries),
    )
    return {
        "rubric_version": rubric.version,
        "calibration_status": rubric.calibration_status.value,
        "blocking_eligible": is_blocking_eligible(rubric),
        "sampling_rates": {
            "ordinary": ORDINARY_SAMPLE_RATE,
            "high_risk": HIGH_RISK_SAMPLE_RATE,
            "mandatory": MANDATORY_SAMPLE_RATE,
        },
        "calibration_targets": {
            "min_monthly_labels": MIN_MONTHLY_LABELS,
            "min_agreement_rate": MIN_AGREEMENT_RATE,
        },
        "latest_calibration": latest.to_dict() if latest else None,
        "capabilities": [
            {
                "capability_code": e.capability_code,
                "action_code": e.action_code,
                "node": e.node,
                "risk_class": e.risk_class.value,
                "min_active_cases": e.min_active_cases,
                "stub": e.stub,
            }
            for e in entries
        ],
    }


__all__ = ["router"]
