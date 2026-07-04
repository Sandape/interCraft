"""REQ-044 US3 — AI Operations OpenAPI contract test (FR-016~FR-020).

Locks the 10-endpoint surface + payload shapes documented in
``.claude/teams/req044/ac-matrix/REQ-044-US3.md``:

- ``GET /api/v1/admin-console/ai-operations/health``
- ``GET /api/v1/admin-console/ai-operations/kpis``
- ``GET /api/v1/admin-console/ai-operations/volume-by-feature``
- ``GET /api/v1/admin-console/ai-operations/failure-categories``
- ``GET /api/v1/admin-console/ai-operations/latency-bands``
- ``GET /api/v1/admin-console/ai-operations/token-usage``
- ``GET /api/v1/admin-console/ai-operations/cost-summary``
- ``GET /api/v1/admin-console/ai-operations/version-selector``
- ``GET /api/v1/admin-console/ai-operations/quality-issues``
- ``GET /api/v1/admin-console/ai-operations/cost-quality-flag``
- ``GET /api/v1/admin-console/ai-operations/eval-badcase-summary``

Skipped if ``DATABASE_URL`` is not configured for parity with the rest
of the 033/039/044 suites.
"""
from __future__ import annotations

import os

import pytest


def _app():
    from app.main import create_app

    return create_app()


# ---------------------------------------------------------------------------
# Route presence (OpenAPI surface)
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_ai_operations_routes_in_openapi() -> None:
    """All 10 ai-operations routes must appear."""
    if not os.getenv("DATABASE_URL"):
        pytest.skip("DATABASE_URL not configured; contract test skipped")

    app = _app()
    expected = {
        "/api/v1/admin-console/ai-operations/kpis",
        "/api/v1/admin-console/ai-operations/volume-by-feature",
        "/api/v1/admin-console/ai-operations/failure-categories",
        "/api/v1/admin-console/ai-operations/latency-bands",
        "/api/v1/admin-console/ai-operations/token-usage",
        "/api/v1/admin-console/ai-operations/cost-summary",
        "/api/v1/admin-console/ai-operations/version-selector",
        "/api/v1/admin-console/ai-operations/quality-issues",
        "/api/v1/admin-console/ai-operations/cost-quality-flag",
        "/api/v1/admin-console/ai-operations/eval-badcase-summary",
        "/api/v1/admin-console/ai-operations/health",
    }
    actual = {
        r.path
        for r in app.routes
        if hasattr(r, "path") and "/admin-console/ai-operations" in r.path
    }
    missing = expected - actual
    assert not missing, f"missing ai_operations routes: {missing}"


@pytest.mark.contract
def test_kpis_endpoint_declares_200_and_403() -> None:
    """GET /kpis must declare 200 + 403 (FR-031)."""
    if not os.getenv("DATABASE_URL"):
        pytest.skip("DATABASE_URL not configured; contract test skipped")

    app = _app()
    schema = app.openapi()
    path = schema["paths"]["/api/v1/admin-console/ai-operations/kpis"]
    get = path["get"]
    assert "200" in get["responses"]
    assert "403" in get["responses"]


# ---------------------------------------------------------------------------
# FR-016 — KPIs: 4 tiles
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_kpis_have_four_tiles() -> None:
    """AC-16.1: 4 KPI tiles (total_volume / success_rate / p95 / cost)."""
    from app.modules.admin_console.ai_operations.service import get_kpis

    result = get_kpis()
    k = result.kpis
    assert k.total_volume >= 0
    assert 0.0 <= k.success_rate <= 1.0
    assert k.p95_latency_ms >= 0.0
    assert k.total_cost_usd >= 0.0


# ---------------------------------------------------------------------------
# FR-016 — Volume by FeatureArea (4 areas)
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_volume_by_feature_has_four_areas() -> None:
    """AC-16.2: volume rows cover all 4 FR-016 FeatureArea values."""
    from app.modules.admin_console.ai_operations.service import (
        get_volume_by_feature,
    )

    result = get_volume_by_feature()
    areas = {r.feature_area for r in result.rows}
    expected = {
        "resume_optimize",
        "mock_interview",
        "error_coach",
        "resume_render",
    }
    assert areas == expected, (
        f"volume_by_feature areas mismatch: got {areas} expected {expected}"
    )


# ---------------------------------------------------------------------------
# FR-016 — Failure categories (5 categories)
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_failure_categories_has_five_classes() -> None:
    """AC-16.3: 5 FR-016 failure categories with valid shares."""
    from app.modules.admin_console.ai_operations.service import (
        get_failure_categories,
    )

    result = get_failure_categories()
    cats = {b.category for b in result.breakdown}
    expected = {"timeout", "token_limit", "parse_error", "eval_failed", "api_5xx"}
    assert cats == expected, (
        f"failure categories mismatch: got {cats} expected {expected}"
    )
    # share ∈ [0, 1]
    for b in result.breakdown:
        assert 0.0 <= b.share <= 1.0
    # total = sum of counts
    assert result.total == sum(b.count for b in result.breakdown)


# ---------------------------------------------------------------------------
# FR-016 — Latency bands: p50/p95/p99
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_latency_bands_has_p50_p95_p99() -> None:
    """AC-16.4: each latency band row carries p50 + p95 + p99."""
    from app.modules.admin_console.ai_operations.service import (
        get_latency_bands,
    )

    result = get_latency_bands()
    assert len(result.entries) == 4
    for entry in result.entries:
        assert entry.p50_latency_ms >= 0.0
        # p95 ≥ p50 (latency bands are monotonic by definition)
        assert entry.p95_latency_ms >= entry.p50_latency_ms, (
            f"p95 < p50 for {entry.feature_area}"
        )
        # p99 ≥ p95
        assert entry.p99_latency_ms >= entry.p95_latency_ms, (
            f"p99 < p95 for {entry.feature_area}"
        )


# ---------------------------------------------------------------------------
# FR-016 — Token usage: input vs output
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_token_usage_has_input_vs_output() -> None:
    """AC-16.5: each row carries prompt + completion tokens."""
    from app.modules.admin_console.ai_operations.service import get_token_usage

    result = get_token_usage()
    assert len(result.rows) == 4
    for row in result.rows:
        assert row.prompt_tokens >= 0
        assert row.completion_tokens >= 0
        assert row.total_tokens == row.prompt_tokens + row.completion_tokens
    # total_tokens = sum of row totals
    assert result.total_tokens == sum(r.total_tokens for r in result.rows)


# ---------------------------------------------------------------------------
# FR-016 — Cost summary: total + per-area breakdown
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_cost_summary_has_total_and_breakdown() -> None:
    """AC-16.6: total + per-area breakdown share consistent."""
    from app.modules.admin_console.ai_operations.service import get_cost_summary

    result = get_cost_summary()
    assert result.total_cost_usd >= 0.0
    assert len(result.by_feature) == 4
    # every share ∈ [0, 1]
    for b in result.by_feature:
        assert 0.0 <= b.share <= 1.0
        assert b.cost_usd >= 0.0


# ---------------------------------------------------------------------------
# FR-017 — Version selector: 4 dimensions
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_version_selector_has_four_dimensions() -> None:
    """AC-17.1: 4 version dimensions (prompt/rubric/model/app)."""
    from app.modules.admin_console.ai_operations.service import (
        get_version_selector,
    )

    result = get_version_selector()
    dims = {d.dimension for d in result.dimensions}
    expected = {
        "prompt_fingerprint",
        "rubric_version",
        "model",
        "app_version",
    }
    assert dims == expected, (
        f"version selector dims mismatch: got {dims} expected {expected}"
    )


@pytest.mark.contract
def test_version_selector_every_dimension_has_known_values() -> None:
    """AC-17.1: each dimension exposes known_values + unknown_count."""
    from app.modules.admin_console.ai_operations.service import (
        get_version_selector,
    )

    result = get_version_selector()
    for d in result.dimensions:
        # each dimension should have ≥1 known value
        assert len(d.known_values) >= 1, (
            f"version dim {d.dimension} has no known values"
        )
        # unknown_count ≥ 0 (allows zero for newer periods)
        assert d.unknown_count >= 0


# ---------------------------------------------------------------------------
# FR-018 — Quality issues: 8 link fields
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_quality_issues_have_eight_link_fields() -> None:
    """AC-18.1: each quality issue carries all 8 FR-018 link fields."""
    from app.modules.admin_console.ai_operations.service import (
        list_quality_issues,
    )

    result = list_quality_issues()
    assert result.total >= 1, "seed must include ≥1 quality issue"
    for issue in result.issues:
        # The 8 link fields per FR-018
        assert issue.eval_verdict
        assert issue.badcase_id
        assert issue.affected_feature_area
        assert issue.affected_journey_step
        assert issue.owner
        assert issue.status
        assert issue.recommended_action
        assert issue.feature_area_dimension


@pytest.mark.contract
def test_quality_issues_eight_field_names_in_schema() -> None:
    """AC-18.2 + FR-032: AIQualityIssue schema enumerates exactly 8 link fields."""
    from app.modules.admin_console.ai_operations.schemas import AIQualityIssue

    # AIQualityIssue MUST expose these 8 FR-018 link fields.
    required_link_fields = {
        "eval_verdict",
        "badcase_id",
        "affected_feature_area",
        "affected_journey_step",
        "owner",
        "status",
        "recommended_action",
        "feature_area_dimension",
    }
    actual_fields = set(AIQualityIssue.model_fields.keys())
    missing = required_link_fields - actual_fields
    assert not missing, (
        f"AIQualityIssue schema missing link fields: {missing}"
    )


@pytest.mark.contract
def test_quality_issues_strictly_no_sensitive_payloads() -> None:
    """FR-032: AIQualityIssue MUST NOT carry raw prompts/outputs/resumes."""
    from app.modules.admin_console.ai_operations.schemas import AIQualityIssue

    forbidden = {
        "raw_prompt",
        "raw_model_output",
        "raw_resume",
        "raw_interview_answer",
        "resume_content",
        "interview_answers",
        "prompts",
        "model_outputs",
    }
    actual_fields = set(AIQualityIssue.model_fields.keys())
    leaked = actual_fields & forbidden
    assert not leaked, f"AIQualityIssue leaked sensitive fields: {leaked}"


# ---------------------------------------------------------------------------
# FR-019 — Cost-quality flag
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_cost_quality_flag_when_quality_down() -> None:
    """AC-19.1: when quality_delta < 0 AND cost up, flag=critical."""
    from app.modules.admin_console.ai_operations.service import (
        compute_cost_quality_flag,
    )

    flag = compute_cost_quality_flag()
    # The seed simulates a canonical "cost up 18%, quality down 7%" case.
    assert flag.cost_delta_pct >= 0.10
    assert flag.quality_delta_pct < 0.0
    assert flag.flagged is True
    assert flag.severity == "critical"


@pytest.mark.contract
def test_cost_quality_flag_has_severity_and_linked() -> None:
    """AC-19.2: cost-quality flag carries severity + 4 linked dimensions."""
    from app.modules.admin_console.ai_operations.schemas import CostQualityFlag

    schema_fields = set(CostQualityFlag.model_fields.keys())
    required = {
        "flagged",
        "severity",
        "cost_delta_pct",
        "quality_delta_pct",
        "linked_model",
        "linked_prompt",
        "linked_feature_area",
        "linked_cohort",
    }
    missing = required - schema_fields
    assert not missing, f"CostQualityFlag schema missing fields: {missing}"


# ---------------------------------------------------------------------------
# FR-020 — Eval + badcase summary
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_eval_badcase_summary_has_required_fields() -> None:
    """AC-20.1: total_eval_runs + pass_rate + open_badcases_count."""
    from app.modules.admin_console.ai_operations.service import (
        get_eval_badcase_summary,
    )

    result = get_eval_badcase_summary()
    s = result.eval_run_summary
    assert s.total_runs >= 1, "seed must include ≥1 eval run"
    assert 0.0 <= s.pass_rate <= 1.0
    assert result.open_badcases_count >= 0


@pytest.mark.contract
def test_recent_badcases_list_has_five_entries() -> None:
    """AC-20.2: recent_badcases MUST have ≥5 entries."""
    from app.modules.admin_console.ai_operations.service import (
        get_eval_badcase_summary,
    )

    result = get_eval_badcase_summary()
    assert len(result.recent_badcases) >= 5, (
        f"recent_badcases has {len(result.recent_badcases)} rows; need ≥5"
    )
    for b in result.recent_badcases:
        assert b.badcase_id
        assert b.feature_area
        assert b.eval_verdict
        assert b.status
        assert b.opened_at


# ---------------------------------------------------------------------------
# SC-006 — 6 view categories each have ≥1 case
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_sc006_six_view_categories_each_have_one_case() -> None:
    """SC-006: AI operations validation covers success / failed / high-cost /
    version / eval / badcase — each represented in the seed."""
    from app.modules.admin_console.ai_operations.service import (
        get_eval_badcase_summary,
        get_failure_categories,
        get_kpis,
        get_volume_by_feature,
        get_version_selector,
        list_quality_issues,
    )

    # success + failed → volume_by_feature carries both success_count +
    # failure_count per area
    volume = get_volume_by_feature()
    assert any(r.success_count > 0 for r in volume.rows), "no success row"
    assert any(r.failure_count > 0 for r in volume.rows), "no failure row"

    # high-cost → at least one row with notable cost
    kpis = get_kpis()
    assert kpis.kpis.total_cost_usd > 0.0

    # version → version_selector has known values
    sel = get_version_selector()
    assert any(d.known_values for d in sel.dimensions)

    # eval → eval_run_summary has ≥1 run
    summary = get_eval_badcase_summary()
    assert summary.eval_run_summary.total_runs >= 1

    # badcase → recent_badcases has ≥5
    assert len(summary.recent_badcases) >= 5

    # + quality issues (eval verdict linkage + badcase linkage)
    issues = list_quality_issues()
    assert issues.total >= 1
    assert all(i.badcase_id and i.eval_verdict for i in issues.issues)

    # + failure categories cover 5 distinct classes
    fc = get_failure_categories()
    assert len({b.category for b in fc.breakdown}) == 5


# ---------------------------------------------------------------------------
# Edge Cases
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_zero_ai_tasks_surfaces_explicit_zero() -> None:
    """EC-1: zero AI tasks → count=0 explicitly, freshness_at='unknown'."""
    from app.modules.admin_console.ai_operations.schemas import (
        VolumeByFeatureResponse,
        VolumeByFeatureRow,
    )

    # Validate that the schema permits count=0 (no constraint to ≥1)
    r = VolumeByFeatureResponse(
        rows=[
            VolumeByFeatureRow(
                feature_area="resume_optimize",
                call_count=0,
                success_count=0,
                failure_count=0,
            ),
        ],
        total=0,
        freshness_at="unknown",
    )
    assert r.total == 0
    assert r.freshness_at == "unknown"


@pytest.mark.contract
def test_version_unknown_handled() -> None:
    """EC-2: version selector surfaces unknown_count (NOT silent baseline)."""
    from app.modules.admin_console.ai_operations.service import (
        get_version_selector,
    )

    result = get_version_selector()
    # At least one dimension must have unknown_count > 0 to surface the
    # "version unknown" badge instead of silently folding into baseline.
    assert any(d.unknown_count > 0 for d in result.dimensions), (
        "version selector must expose unknown_count > 0 for legacy rows"
    )


@pytest.mark.contract
def test_cost_outdated_flag_when_token_table_stale() -> None:
    """EC-3: stale cost reconciliation surfaces stale flag and label."""
    from app.modules.admin_console.ai_operations.service import (
        COST_RECONCILIATION_STALE_DAYS,
    )

    # Threshold is 14 days; the seed defaults to 7 days (fresh).
    # Verify the tunable matches the spec.
    assert COST_RECONCILIATION_STALE_DAYS == 14

    # The CostSummaryResponse schema must permit stale=True.
    from app.modules.admin_console.ai_operations.schemas import (
        CostSummaryResponse,
    )

    r = CostSummaryResponse(
        total_cost_usd=10.0,
        by_feature=[],
        last_reconciled_at="2026-06-01T00:00:00Z",
        is_estimate=True,
        stale=True,
        freshness_at="2026-07-04T00:00:00Z",
    )
    assert r.stale is True


# ---------------------------------------------------------------------------
# Capability tokens (FR-031)
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_ai_operations_capabilities_in_role_map() -> None:
    """AI_OPERATIONS_VIEW must be granted to pm/owner/admin + operations + maintainer."""
    from app.modules.admin_console.auth import (
        AI_OPERATIONS_VIEW,
        _ROLE_GRANTS,
    )

    assert AI_OPERATIONS_VIEW in _ROLE_GRANTS["admin"]
    assert AI_OPERATIONS_VIEW in _ROLE_GRANTS["owner"]
    assert AI_OPERATIONS_VIEW in _ROLE_GRANTS["pm"]
    assert AI_OPERATIONS_VIEW in _ROLE_GRANTS["operations"]
    assert AI_OPERATIONS_VIEW in _ROLE_GRANTS["maintainer"]
    # FR-031 least-privilege: viewer is denied.
    assert AI_OPERATIONS_VIEW not in _ROLE_GRANTS["viewer"]
