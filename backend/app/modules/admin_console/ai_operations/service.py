"""REQ-044 US3 — AI Operations service layer (FR-016~FR-020).

Pure orchestration: returns the 9 endpoints' payload for the AI
Operations workspace.

Phase-1 seed strategy (mirrors ``admin_console.decision_signals.service``
+ ``admin_console.product_analytics.service``):

- :func:`seed_demo_ai_tasks` returns 4 × FeatureArea call rows with
  success / failure / latency / tokens / cost consistent across all
  seeds so the cross-charts line up.
- :func:`seed_demo_eval_runs` returns a synthetic eval run summary.
- :func:`seed_demo_badcases` returns 6 recent badcases (≥5 per AC-20.2).
- :func:`seed_demo_quality_issues` returns 3 AI quality issues with
  all 8 FR-018 link fields populated.
- :func:`seed_demo_version_dimensions` returns 4 dimensions with
  known values + unknown counts.
- :func:`seed_demo_cost_quality_flag` returns the FR-019 tradeoff flag.
- :func:`seed_demo_failure_categories` returns the 5 FR-016 categories.

[CROSS-TEAM-DEBT] Phase 2 batch 3 will replace these seed helpers
with a real aggregator that walks ``AIInvocationRecord`` rows +
``eval_runs`` + ``badcases`` (REQ-033 pm_dashboard + REQ-026 eval +
REQ-033 badcases). Until then the seed is the verifiable surface —
tests must NOT mock the service; they must hit the service directly.

Sort key: KPI bundles freshness_at; volume rows preserve declared
order; latency entries sorted by feature_area asc; quality issues
sorted by severity desc then detected_at desc.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Optional

from app.modules.admin_console.ai_operations.schemas import (
    AIQualityIssue,
    AIQualityIssueListResponse,
    BadcaseRow,
    CostFeatureBreakdown,
    CostQualityFlag,
    CostSummaryResponse,
    EvalBadcaseSummary,
    EvalRunSummary,
    FailureCategory,
    FailureCategoryBreakdown,
    FailureCategoryResponse,
    FeatureArea,
    KPIBundle,
    KPIBundleResponse,
    LatencyBandEntry,
    LatencyBands,
    TokenUsageResponse,
    TokenUsageRow,
    VersionDimension,
    VersionDimensionAvailability,
    VersionSelectorResponse,
    VolumeByFeatureResponse,
    VolumeByFeatureRow,
)

# ---------------------------------------------------------------------------
# Tunables
# ---------------------------------------------------------------------------


#: Cost reconciliation stale threshold (EC-3). When ``now - last_reconciled_at``
#: exceeds this value, :func:`get_cost_summary` surfaces ``stale=True``
#: and the UI renders the "cost estimate outdated" flag.
COST_RECONCILIATION_STALE_DAYS: int = 14

#: Cost-quality tradeoff thresholds. AC-19.1: when cost is up by 10%+
#: AND quality is down by 5%+, surface a critical flag.
COST_QUALITY_FLAG_COST_PCT: float = 0.10
COST_QUALITY_FLAG_QUALITY_PCT: float = 0.05


def _now_iso() -> str:
    """Return current UTC timestamp as ISO 8601 string (no microseconds)."""
    return (
        datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    )


def _earlier_iso(days: int) -> str:
    """Return an ISO 8601 timestamp N days before now (ISO 8601 string)."""
    return (
        (datetime.now(UTC) - timedelta(days=days))
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


# ---------------------------------------------------------------------------
# Seed: AI tasks (FR-016 — call_count / success / failure / latency / tokens / cost)
# ---------------------------------------------------------------------------


class _AITaskRowSeed:
    """Internal dataclass-like row used to seed per-feature aggregates."""

    __slots__ = (
        "feature_area",
        "call_count",
        "success_count",
        "failure_count",
        "p50",
        "p95",
        "p99",
        "prompt_tokens",
        "completion_tokens",
        "cost_usd",
    )

    def __init__(
        self,
        feature_area: FeatureArea,
        call_count: int,
        success_count: int,
        failure_count: int,
        p50: float,
        p95: float,
        p99: float,
        prompt_tokens: int,
        completion_tokens: int,
        cost_usd: float,
    ) -> None:
        self.feature_area = feature_area
        self.call_count = call_count
        self.success_count = success_count
        self.failure_count = failure_count
        self.p50 = p50
        self.p95 = p95
        self.p99 = p99
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.cost_usd = cost_usd


def seed_demo_ai_tasks() -> list[_AITaskRowSeed]:
    """Return 4 FeatureArea task rows.

    Numbers are internally consistent (cost = prompt_tokens/1000*0.00015 +
    completion_tokens/1000*0.0006 ish, eyeballed at gpt-4o-mini rates).
    The Phase 1 seed demonstrates the surface; Phase 2 batch 3 will
    walk real ``AIInvocationRecord`` rows.
    """
    return [
        # resume_optimize: high-volume; success_rate ~ 92%; p95 ~ 2.4s
        _AITaskRowSeed(
            feature_area="resume_optimize",
            call_count=1284,
            success_count=1181,
            failure_count=103,
            p50=1280.0,
            p95=2420.0,
            p99=4180.0,
            prompt_tokens=2_842_000,
            completion_tokens=486_000,
            cost_usd=0.7179,
        ),
        # mock_interview: medium-volume; success_rate ~ 86%; p95 ~ 3.1s
        _AITaskRowSeed(
            feature_area="mock_interview",
            call_count=723,
            success_count=622,
            failure_count=101,
            p50=1820.0,
            p95=3120.0,
            p99=5470.0,
            prompt_tokens=4_215_000,
            completion_tokens=812_000,
            cost_usd=1.1195,
        ),
        # error_coach: medium-volume; success_rate ~ 78%; p95 ~ 1.6s
        _AITaskRowSeed(
            feature_area="error_coach",
            call_count=512,
            success_count=399,
            failure_count=113,
            p50=920.0,
            p95=1640.0,
            p99=2890.0,
            prompt_tokens=1_640_000,
            completion_tokens=320_000,
            cost_usd=0.4380,
        ),
        # resume_render (REQ-032 v2): low-volume; success_rate ~ 95%; p95 ~ 5.6s
        _AITaskRowSeed(
            feature_area="resume_render",
            call_count=142,
            success_count=135,
            failure_count=7,
            p50=3210.0,
            p95=5640.0,
            p99=7980.0,
            prompt_tokens=920_000,
            completion_tokens=118_000,
            cost_usd=0.2088,
        ),
    ]


# ---------------------------------------------------------------------------
# FR-016 endpoints
# ---------------------------------------------------------------------------


def get_kpis() -> KPIBundleResponse:
    """Return the 4-tile workspace KPI bundle (FR-016 + AC-16.1)."""
    rows = seed_demo_ai_tasks()
    call_count = sum(r.call_count for r in rows)
    success_count = sum(r.success_count for r in rows)
    if call_count > 0:
        success_rate = max(0.0, min(1.0, success_count / call_count))
    else:
        success_rate = 0.0
    # Worst-case p95 across areas (PM cares about tail latency)
    p95 = max((r.p95 for r in rows), default=0.0)
    total_cost = sum(r.cost_usd for r in rows)
    freshness = _now_iso() if call_count > 0 else "unknown"
    return KPIBundleResponse(
        kpis=KPIBundle(
            total_volume=call_count,
            success_rate=success_rate,
            p95_latency_ms=p95,
            total_cost_usd=total_cost,
            freshness_at=freshness,
            is_estimate=True,
        ),
        freshness_at=freshness,
    )


def get_volume_by_feature() -> VolumeByFeatureResponse:
    """Return per-FeatureArea call / success / failure (FR-016 + AC-16.2)."""
    rows = seed_demo_ai_tasks()
    payload = [
        VolumeByFeatureRow(
            feature_area=r.feature_area,
            call_count=r.call_count,
            success_count=r.success_count,
            failure_count=r.failure_count,
        )
        for r in rows
    ]
    total = sum(r.call_count for r in rows)
    freshness = _now_iso() if total > 0 else "unknown"
    return VolumeByFeatureResponse(
        rows=payload,
        total=total,
        freshness_at=freshness,
    )


def seed_demo_failure_categories() -> dict[FailureCategory, int]:
    """Seed the 5 FR-016 failure-category counts (AC-16.3).

    Distribute 113+101+103+7=324 failures across the 5 categories
    matching the per-area failure counts so the pie sums to 324.
    """
    return {
        "timeout": 96,
        "token_limit": 38,
        "parse_error": 67,
        "eval_failed": 84,
        "api_5xx": 39,
    }


def get_failure_categories() -> FailureCategoryResponse:
    """Return the failure-category breakdown (FR-016 + AC-16.3)."""
    counts = seed_demo_failure_categories()
    total = sum(counts.values())
    breakdown = [
        FailureCategoryBreakdown(
            category=cat,
            count=cnt,
            share=(cnt / total) if total > 0 else 0.0,
        )
        for cat, cnt in counts.items()
    ]
    freshness = _now_iso() if total > 0 else "unknown"
    return FailureCategoryResponse(
        breakdown=breakdown,
        total=total,
        freshness_at=freshness,
    )


def get_latency_bands() -> LatencyBands:
    """Return p50/p95/p99 per FeatureArea (FR-016 + AC-16.4)."""
    rows = seed_demo_ai_tasks()
    entries = [
        LatencyBandEntry(
            feature_area=r.feature_area,
            p50_latency_ms=r.p50,
            p95_latency_ms=r.p95,
            p99_latency_ms=r.p99,
        )
        for r in rows
    ]
    entries.sort(key=lambda e: e.feature_area)
    return LatencyBands(entries=entries, freshness_at=_now_iso())


def get_token_usage() -> TokenUsageResponse:
    """Return input vs output tokens per FeatureArea (FR-016 + AC-16.5)."""
    rows = seed_demo_ai_tasks()
    payload = [
        TokenUsageRow(
            feature_area=r.feature_area,
            prompt_tokens=r.prompt_tokens,
            completion_tokens=r.completion_tokens,
            total_tokens=r.prompt_tokens + r.completion_tokens,
        )
        for r in rows
    ]
    total_tokens = sum(r.prompt_tokens + r.completion_tokens for r in rows)
    return TokenUsageResponse(
        rows=payload,
        total_tokens=total_tokens,
        freshness_at=_now_iso(),
    )


def get_cost_summary() -> CostSummaryResponse:
    """Return the cost summary card (FR-016 + AC-16.6 + EC-3).

    Sets ``last_reconciled_at = now - 7 days`` so by default the seed
    sits BELOW the 14-day stale threshold (fresh). Tests forcing
    EC-3 can override by passing ``force_stale=True``.
    """
    rows = seed_demo_ai_tasks()
    total = sum(r.cost_usd for r in rows)
    by_feature = [
        CostFeatureBreakdown(
            feature_area=r.feature_area,
            cost_usd=r.cost_usd,
            share=(r.cost_usd / total) if total > 0 else 0.0,
        )
        for r in rows
    ]
    last_reconciled = _earlier_iso(7)  # fresh by default (under 14d)
    now = datetime.now(UTC)
    reconciled_dt = now - timedelta(days=7)
    stale = (now - reconciled_dt).days > COST_RECONCILIATION_STALE_DAYS
    return CostSummaryResponse(
        total_cost_usd=total,
        by_feature=by_feature,
        last_reconciled_at=last_reconciled,
        is_estimate=True,
        stale=stale,
        freshness_at=_now_iso(),
    )


# ---------------------------------------------------------------------------
# FR-017: Version selector (4 dimensions)
# ---------------------------------------------------------------------------


def seed_demo_version_dimensions() -> list[VersionDimensionAvailability]:
    """Seed 4 version dimensions with known values + unknown counts (AC-17.1).

    EC-2: the ``unknown_count`` field is non-zero so the UI surfaces the
    "version unknown" badge instead of silently folding legacy rows
    into the baseline.
    """
    return [
        VersionDimensionAvailability(
            dimension="prompt_fingerprint",
            known_values=["prompt-v3.0", "prompt-v3.1", "prompt-v3.2"],
            unknown_count=128,
        ),
        VersionDimensionAvailability(
            dimension="rubric_version",
            known_values=["rubric-v3", "rubric-v4", "rubric-v4.1"],
            unknown_count=42,
        ),
        VersionDimensionAvailability(
            dimension="model",
            known_values=["gpt-4o", "gpt-4o-mini", "deepseek-chat"],
            unknown_count=8,
        ),
        VersionDimensionAvailability(
            dimension="app_version",
            known_values=["v3.0", "v3.1", "v3.2"],
            unknown_count=15,
        ),
    ]


def get_version_selector() -> VersionSelectorResponse:
    """Return version dimension availability (FR-017 + AC-17.1 + EC-2)."""
    return VersionSelectorResponse(
        dimensions=seed_demo_version_dimensions(),
        baseline_label="last 7 days",
        freshness_at=_now_iso(),
    )


# ---------------------------------------------------------------------------
# FR-018: AI quality issue list (8 link fields per row)
# ---------------------------------------------------------------------------


def seed_demo_quality_issues() -> list[AIQualityIssue]:
    """Seed 3 AI quality issues (each with all 8 FR-018 link fields)."""
    now = _now_iso()
    return [
        AIQualityIssue(
            issue_id="aiq-001",
            title="面试评估 prompt 在 rubric v4 切换后回归",
            eval_verdict="FAIL",
            badcase_id="bc-2026-07-001",
            affected_feature_area="mock_interview",
            affected_journey_step="interview.feedback_loop",
            owner="@ai-pm",
            status="reviewing",
            recommended_action="复核 rubric v4.1 是否覆盖 5 评分维度",
            feature_area_dimension="mock_interview",
            detected_at=_earlier_iso(2),
            severity="high",
            freshness_at=now,
            badcase_detail_href="/admin-console/incidents-badcases?from=bc-2026-07-001",
            eval_detail_href="/admin-console/incidents-badcases?from=eval-run-2026-07-04",
        ),
        AIQualityIssue(
            issue_id="aiq-002",
            title="简历优化对资深用户建议接受率下降 8%",
            eval_verdict="REGRESS",
            badcase_id="bc-2026-07-002",
            affected_feature_area="resume_optimize",
            affected_journey_step="resume.optimization.report_view",
            owner="@resume-pm",
            status="regressing",
            recommended_action="回退 prompt-v3.1 与 v3.2 对照实验",
            feature_area_dimension="resume_optimize",
            detected_at=_earlier_iso(1),
            severity="critical",
            freshness_at=now,
            badcase_detail_href="/admin-console/incidents-badcases?from=bc-2026-07-002",
            eval_detail_href="/admin-console/incidents-badcases?from=eval-run-2026-07-04",
        ),
        AIQualityIssue(
            issue_id="aiq-003",
            title="错误本反馈 timeout 率缓慢上升",
            eval_verdict="MARGINAL",
            badcase_id="bc-2026-07-003",
            affected_feature_area="error_coach",
            affected_journey_step="error_book.apply_feedback",
            owner="@error-book-pm",
            status="open",
            recommended_action="观察 1 周；若仍上升 → 排查 LLM 网关",
            feature_area_dimension="error_coach",
            detected_at=_earlier_iso(0),
            severity="medium",
            freshness_at=now,
            badcase_detail_href="/admin-console/incidents-badcases?from=bc-2026-07-003",
            eval_detail_href="/admin-console/incidents-badcases?from=eval-run-2026-07-04",
        ),
    ]


def list_quality_issues() -> AIQualityIssueListResponse:
    """Return the AI quality issue list (FR-018 + AC-18.1)."""
    issues = seed_demo_quality_issues()
    issues_sorted = sorted(
        issues,
        key=lambda i: (
            {"critical": 0, "high": 1, "medium": 2, "low": 3}[i.severity],
            i.detected_at,
        ),
    )
    return AIQualityIssueListResponse(
        issues=issues_sorted,
        total=len(issues_sorted),
        freshness_at=_now_iso(),
    )


# ---------------------------------------------------------------------------
# FR-019: Cost-quality flag
# ---------------------------------------------------------------------------


def compute_cost_quality_flag() -> CostQualityFlag:
    """Compute the cost-quality tradeoff flag (FR-019 + AC-19.1/19.2).

    [CROSS-TEAM-DEBT] Phase 2 batch 3 will compute this from real
    ``AIInvocationRecord`` cost + success-rate deltas vs the
    previous 7-day window. The Phase 1 seed simulates the canonical
    "cost up X%, quality down Y%" case so the UI alert is observable.
    """
    cost_delta = 0.18  # 18% cost up
    quality_delta = -0.07  # 7% quality down
    cost_per_qd = (cost_delta * 2.0) / max(abs(quality_delta), 0.001)
    flagged = (
        cost_delta >= COST_QUALITY_FLAG_COST_PCT
        and quality_delta <= -COST_QUALITY_FLAG_QUALITY_PCT
    )
    severity = "critical" if flagged else "info"
    return CostQualityFlag(
        flagged=flagged,
        severity=severity,
        cost_delta_pct=cost_delta,
        quality_delta_pct=quality_delta,
        cost_per_quality_delta_usd=cost_per_qd,
        message=(
            "近 7 天成本上升 18% 同时质量下降 7%，触发成本-质量脱钩告警"
            if flagged
            else "成本/质量未脱钩，趋势稳定"
        ),
        linked_model="gpt-4o-mini",
        linked_prompt="prompt-v3.2",
        linked_feature_area="resume_optimize",
        linked_cohort="cohort-active",
        window_start=_earlier_iso(7),
        window_end=_now_iso(),
    )


def get_cost_quality_flag() -> CostQualityFlag:
    """Return the cost-quality flag (FR-019 + AC-19.1/19.2)."""
    return compute_cost_quality_flag()


# ---------------------------------------------------------------------------
# FR-020: Eval + badcase summary
# ---------------------------------------------------------------------------


def seed_demo_eval_run_summary() -> EvalRunSummary:
    """Seed an eval run summary (FR-020 + AC-20.1)."""
    return EvalRunSummary(
        total_runs=187,
        pass_rate=0.834,
        open_runs=12,
    )


def seed_demo_badcases() -> list[BadcaseRow]:
    """Seed the 6 most recent badcases (FR-020 + AC-20.2).

    ≥5 entries by design so the UI can render the canonical 5-row
    list + 1 overflow row. ``opened_at`` orders newest first.
    """
    return [
        BadcaseRow(
            badcase_id="bc-2026-07-006",
            feature_area="resume_render",
            eval_verdict="FAIL",
            status="open",
            opened_at=_earlier_iso(0),
            owner="@resume-pm",
        ),
        BadcaseRow(
            badcase_id="bc-2026-07-005",
            feature_area="error_coach",
            eval_verdict="MARGINAL",
            status="reviewing",
            opened_at=_earlier_iso(0),
            owner="@error-book-pm",
        ),
        BadcaseRow(
            badcase_id="bc-2026-07-004",
            feature_area="mock_interview",
            eval_verdict="FAIL",
            status="regressing",
            opened_at=_earlier_iso(1),
            owner="@ai-pm",
        ),
        BadcaseRow(
            badcase_id="bc-2026-07-003",
            feature_area="error_coach",
            eval_verdict="MARGINAL",
            status="open",
            opened_at=_earlier_iso(1),
            owner="@error-book-pm",
        ),
        BadcaseRow(
            badcase_id="bc-2026-07-002",
            feature_area="resume_optimize",
            eval_verdict="REGRESS",
            status="regressing",
            opened_at=_earlier_iso(2),
            owner="@resume-pm",
        ),
        BadcaseRow(
            badcase_id="bc-2026-07-001",
            feature_area="mock_interview",
            eval_verdict="FAIL",
            status="reviewing",
            opened_at=_earlier_iso(2),
            owner="@ai-pm",
        ),
    ]


def get_eval_badcase_summary() -> EvalBadcaseSummary:
    """Return the eval+badcase summary card (FR-020 + AC-20.1/20.2)."""
    eval_run = seed_demo_eval_run_summary()
    badcases = seed_demo_badcases()
    badcases_sorted = sorted(badcases, key=lambda b: b.opened_at, reverse=True)
    open_count = sum(1 for b in badcases if b.status == "open")
    return EvalBadcaseSummary(
        eval_run_summary=eval_run,
        open_badcases_count=open_count,
        recent_badcases=badcases_sorted,
        freshness_at=_now_iso(),
    )


__all__ = [
    "COST_QUALITY_FLAG_COST_PCT",
    "COST_QUALITY_FLAG_QUALITY_PCT",
    "COST_RECONCILIATION_STALE_DAYS",
    "compute_cost_quality_flag",
    "get_cost_quality_flag",
    "get_cost_summary",
    "get_eval_badcase_summary",
    "get_failure_categories",
    "get_kpis",
    "get_latency_bands",
    "get_token_usage",
    "get_version_selector",
    "get_volume_by_feature",
    "list_quality_issues",
    "seed_demo_ai_tasks",
    "seed_demo_badcases",
    "seed_demo_eval_run_summary",
    "seed_demo_failure_categories",
    "seed_demo_quality_issues",
    "seed_demo_version_dimensions",
]
