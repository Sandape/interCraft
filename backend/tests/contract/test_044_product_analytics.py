"""REQ-044 US2 — Product Analytics OpenAPI contract test (FR-011~FR-015).

Locks the 6-endpoint surface + payload shapes documented in
``.claude/teams/req044/ac-matrix/REQ-044-US2.md``:

- ``GET /api/v1/admin-console/product-analytics/health``
- ``GET /api/v1/admin-console/product-analytics/question-templates``
- ``GET /api/v1/admin-console/product-analytics/funnel``
- ``GET /api/v1/admin-console/product-analytics/cohorts``
- ``GET /api/v1/admin-console/product-analytics/feature-adoption``
- ``GET /api/v1/admin-console/users/{user_id}``

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
def test_product_analytics_routes_in_openapi() -> None:
    """All 5 product-analytics routes + the user lookup must appear."""
    if not os.getenv("DATABASE_URL"):
        pytest.skip("DATABASE_URL not configured; contract test skipped")

    app = _app()
    expected = {
        "/api/v1/admin-console/product-analytics/question-templates",
        "/api/v1/admin-console/product-analytics/funnel",
        "/api/v1/admin-console/product-analytics/cohorts",
        "/api/v1/admin-console/product-analytics/feature-adoption",
        "/api/v1/admin-console/product-analytics/health",
        "/api/v1/admin-console/users/{user_id}",
    }
    actual = {
        r.path
        for r in app.routes
        if hasattr(r, "path")
        and (
            "/admin-console/product-analytics" in r.path
            or "/admin-console/users" in r.path
        )
    }
    missing = expected - actual
    assert not missing, f"missing product_analytics routes: {missing}"


@pytest.mark.contract
def test_question_templates_endpoint_declares_200_and_403() -> None:
    """GET /question-templates must declare 200 + 403 (FR-031)."""
    if not os.getenv("DATABASE_URL"):
        pytest.skip("DATABASE_URL not configured; contract test skipped")

    app = _app()
    schema = app.openapi()
    path = schema["paths"][
        "/api/v1/admin-console/product-analytics/question-templates"
    ]
    get = path["get"]
    assert "200" in get["responses"]
    assert "403" in get["responses"]


@pytest.mark.contract
def test_user_lookup_endpoint_declares_404() -> None:
    """GET /users/{user_id} must declare 404 for unknown users (FR-015)."""
    if not os.getenv("DATABASE_URL"):
        pytest.skip("DATABASE_URL not configured; contract test skipped")

    app = _app()
    schema = app.openapi()
    path = schema["paths"]["/api/v1/admin-console/users/{user_id}"]
    get = path["get"]
    assert "200" in get["responses"]
    assert "404" in get["responses"]


# ---------------------------------------------------------------------------
# FR-011 — QuestionTemplate: 7 tabs + ≥3 templates per tab
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_seed_has_min_21_templates() -> None:
    """AC-11.2: ≥21 templates (3 per tab × 7 tabs)."""
    from app.modules.admin_console.product_analytics.service import (
        list_question_templates,
    )

    result = list_question_templates()
    assert result.total >= 21, (
        f"need ≥21 templates, got {result.total}"
    )


@pytest.mark.contract
def test_seed_covers_all_seven_question_tabs() -> None:
    """FR-011: templates MUST cover all 7 question tabs."""
    from app.modules.admin_console.product_analytics.service import (
        list_question_templates,
    )

    result = list_question_templates()
    tabs = {t.tab for t in result.templates}
    required = {
        "activation",
        "funnel",
        "retention",
        "adoption",
        "journey",
        "release",
        "experiment",
    }
    missing = required - tabs
    assert not missing, f"question tabs missing: {missing}"


@pytest.mark.contract
def test_seed_has_three_templates_per_tab() -> None:
    """AC-11.2: ≥3 templates per tab (UX density)."""
    from app.modules.admin_console.product_analytics.service import (
        list_question_templates,
    )

    result = list_question_templates()
    by_tab: dict[str, int] = {}
    for t in result.templates:
        by_tab[t.tab] = by_tab.get(t.tab, 0) + 1
    for tab in (
        "activation",
        "funnel",
        "retention",
        "adoption",
        "journey",
        "release",
        "experiment",
    ):
        assert by_tab.get(tab, 0) >= 3, (
            f"tab '{tab}' has {by_tab.get(tab, 0)} templates; need ≥3"
        )


# ---------------------------------------------------------------------------
# FR-012 — Funnel: 5 steps + entry conversion + comparison delta + T2C
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_funnel_has_5_steps_with_all_required_fields() -> None:
    """AC-12.1: 5 steps + each step has count + step_conversion + drop_off."""
    from app.modules.admin_console.product_analytics.service import get_funnel

    result = get_funnel(template_id="q-fun-1")
    assert len(result.steps) == 5, (
        f"funnel must have 5 steps, got {len(result.steps)}"
    )
    for i, step in enumerate(result.steps):
        assert step.count >= 0, f"step {i} count must be ≥0"
        if i == 0:
            # First step: conversion / drop_off from previous are None.
            assert step.step_conversion is None
            assert step.drop_off is None
        else:
            assert step.step_conversion is not None
            assert 0.0 <= step.step_conversion <= 1.0
            assert step.drop_off is not None
            assert 0.0 <= step.drop_off <= 1.0


@pytest.mark.contract
def test_funnel_has_entry_conversion_and_comparison_delta() -> None:
    """AC-12.2: entry_conversion + comparison_period_delta."""
    from app.modules.admin_console.product_analytics.service import get_funnel

    result = get_funnel(template_id="q-fun-1")
    assert 0.0 <= result.entry_conversion <= 1.0, (
        f"entry_conversion out of range: {result.entry_conversion}"
    )
    assert result.comparison_delta is not None
    assert result.comparison_delta.comparison_period_label, (
        "comparison_period_label must be non-empty"
    )
    assert -1.0 <= result.comparison_delta.step_conversion_delta <= 1.0


@pytest.mark.contract
def test_funnel_has_time_to_convert_p50_with_ci() -> None:
    """AC-12.3: time-to-convert P50 + 95% CI + sample_size."""
    from app.modules.admin_console.product_analytics.service import get_funnel

    result = get_funnel(template_id="q-fun-1")
    assert result.time_to_convert is not None
    ttc = result.time_to_convert
    assert ttc.p50_seconds >= 0.0
    assert ttc.ci95_lower_seconds >= 0.0
    assert ttc.ci95_upper_seconds >= ttc.p50_seconds, (
        "CI upper bound must be ≥ P50"
    )
    assert ttc.sample_size >= 0


# ---------------------------------------------------------------------------
# FR-013 — Cohort: id/name/definition/population/owner/last_computed_at
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_cohorts_endpoint_returns_required_fields() -> None:
    """AC-13.1: each cohort carries id/name/definition/population/owner/last_computed_at."""
    from app.modules.admin_console.product_analytics.service import list_cohorts

    result = list_cohorts()
    assert result.total >= 1
    for c in result.cohorts:
        assert c.id, f"empty id in {c}"
        assert c.name, f"empty name in {c.id}"
        assert c.definition, f"empty definition in {c.id}"
        assert c.population >= 0, f"invalid population in {c.id}"
        assert c.owner, f"empty owner in {c.id}"
        assert c.last_computed_at, f"empty last_computed_at in {c.id}"


@pytest.mark.contract
def test_cohort_seed_has_stale_cohort_for_ec2() -> None:
    """EC-2: at least one cohort with stale=True so the warning is observable."""
    from app.modules.admin_console.product_analytics.service import list_cohorts

    result = list_cohorts()
    assert any(c.stale for c in result.cohorts), (
        "seed must include at least one stale cohort for EC-2"
    )


# ---------------------------------------------------------------------------
# FR-014 — Feature adoption: 5 metrics + comparison delta
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_feature_adoption_has_5_metrics() -> None:
    """AC-14.1: each feature carries 5 metrics in the locked order."""
    from app.modules.admin_console.product_analytics.service import (
        get_feature_adoption,
    )

    result = get_feature_adoption()
    expected_metrics = [
        "discovery_users",
        "first_use_users",
        "repeat_users",
        "frequency_avg",
        "downstream_success_rate",
    ]
    for feat in result.features:
        actual = [m.metric_name for m in feat.metrics]
        assert actual == expected_metrics, (
            f"feature {feat.feature_id} has metric order {actual}; "
            f"expected {expected_metrics}"
        )


@pytest.mark.contract
def test_feature_adoption_has_comparison_delta() -> None:
    """AC-14.2: each metric carries a comparison_delta in [-1, 1]."""
    from app.modules.admin_console.product_analytics.service import (
        get_feature_adoption,
    )

    result = get_feature_adoption()
    assert result.features, "seed must include at least one feature"
    for feat in result.features:
        for m in feat.metrics:
            assert -1.0 <= m.comparison_delta <= 1.0, (
                f"comparison_delta out of range: {m.comparison_delta} "
                f"in {feat.feature_id}/{m.metric_name}"
            )


@pytest.mark.contract
def test_feature_adoption_has_insufficient_data_for_ec3() -> None:
    """EC-3: at least one feature with insufficient_data=True."""
    from app.modules.admin_console.product_analytics.service import (
        get_feature_adoption,
    )

    result = get_feature_adoption()
    assert any(
        any(m.insufficient_data for m in feat.metrics) for feat in result.features
    ), "seed must include a feature with insufficient_data=True for EC-3"


# ---------------------------------------------------------------------------
# FR-015 — User privacy-safe lookup: allow-listed fields only
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_user_safe_profile_strips_sensitive_fields() -> None:
    """AC-15.1: UserPrivacySafe carries ONLY the 7 allow-listed fields.

    Forbidden field names (per FR-032 + AC-15.4):
    raw_resume, raw_interview_answer, raw_prompt, raw_model_output,
    resume_content, interview_answers, prompts, model_outputs,
    secrets, tokens, passwords, credentials.
    """
    from app.modules.admin_console.product_analytics.schemas import (
        UserPrivacySafeField,
    )

    allowed = set(UserPrivacySafeField.model_fields["name"].annotation.__args__)
    forbidden = {
        "raw_resume",
        "raw_interview_answer",
        "raw_prompt",
        "raw_model_output",
        "resume_content",
        "interview_answers",
        "prompts",
        "model_outputs",
        "secrets",
        "tokens",
        "passwords",
        "credentials",
    }
    # The forbidden set MUST NOT overlap the allowed set.
    overlap = allowed & forbidden
    assert not overlap, f"forbidden fields leaked into allow-list: {overlap}"

    # And the seed must populate at least one user profile.
    from app.modules.admin_console.product_analytics.service import (
        seed_demo_users,
    )

    profiles = seed_demo_users()
    assert profiles, "seed must include at least one user profile"
    for uid, profile in profiles.items():
        actual_field_names = {f.name for f in profile.fields}
        # Every field name MUST be in the allow-list.
        leaked = actual_field_names - allowed
        assert not leaked, (
            f"user {uid} leaked fields outside allow-list: {leaked}"
        )
        # And no field should be named any forbidden token.
        forbidden_hit = actual_field_names & forbidden
        assert not forbidden_hit, (
            f"user {uid} has forbidden field names: {forbidden_hit}"
        )


@pytest.mark.contract
def test_user_safe_profile_each_field_has_visibility_level() -> None:
    """AC-15.3: each field MUST carry a visibility level (full/masked/hidden)."""
    from app.modules.admin_console.product_analytics.service import (
        seed_demo_users,
    )

    profiles = seed_demo_users()
    for uid, profile in profiles.items():
        assert profile.fields, f"user {uid} has no fields"
        for f in profile.fields:
            assert f.visibility in {"full", "masked", "hidden"}, (
                f"user {uid} field {f.name} has invalid visibility: {f.visibility}"
            )


# ---------------------------------------------------------------------------
# Edge Cases — EC-1 zero funnel data
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_zero_funnel_surfaces_explicit_zero_counts() -> None:
    """EC-1: zero funnel MUST return count=0 explicitly, not 200 + empty list."""
    from app.modules.admin_console.product_analytics.service import get_funnel

    result = get_funnel(template_id="funnel-empty")
    assert len(result.steps) == 5
    for i, step in enumerate(result.steps):
        assert step.count == 0, (
            f"step {i} should be count=0 for zero funnel; got {step.count}"
        )
    assert result.entry_conversion == 0.0


# ---------------------------------------------------------------------------
# SC-005 — 5 analysis views each have ≥1 template
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_seed_covers_five_analysis_views() -> None:
    """SC-005: workspace covers ≥1 template for each of the 5 views.

    The 5 views (per spec.md) = funnel + cohort + retention + adoption
    + release (or experiment comparison).
    """
    from app.modules.admin_console.product_analytics.service import (
        list_question_templates,
    )

    result = list_question_templates()
    by_tab: dict[str, int] = {}
    for t in result.templates:
        by_tab[t.tab] = by_tab.get(t.tab, 0) + 1
    for view in ("funnel", "cohort", "retention", "adoption", "release"):
        # release tab serves the release comparison view;
        # cohort tab (which already has 3 templates per AC-11.2) is
        # not a question tab itself but is covered by the cohort
        # endpoint, so we accept either.
        if view == "cohort":
            # cohort is exposed via /cohorts endpoint, not a question tab.
            from app.modules.admin_console.product_analytics.service import (
                list_cohorts,
            )

            cohorts = list_cohorts()
            assert cohorts.total >= 1, "cohort view must have ≥1 cohort"
        else:
            assert by_tab.get(view, 0) >= 1, (
                f"view '{view}' must have ≥1 template"
            )


# ---------------------------------------------------------------------------
# Capability tokens (FR-031)
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_product_analytics_capabilities_in_role_map() -> None:
    """PRODUCT_ANALYTICS_VIEW + USER_LOOKUP must be granted to pm/owner/admin."""
    from app.modules.admin_console.auth import (
        PRODUCT_ANALYTICS_VIEW,
        USER_LOOKUP,
        _ROLE_GRANTS,
    )

    assert PRODUCT_ANALYTICS_VIEW in _ROLE_GRANTS["admin"]
    assert PRODUCT_ANALYTICS_VIEW in _ROLE_GRANTS["owner"]
    assert PRODUCT_ANALYTICS_VIEW in _ROLE_GRANTS["pm"]
    assert USER_LOOKUP in _ROLE_GRANTS["admin"]
    assert USER_LOOKUP in _ROLE_GRANTS["owner"]
    assert USER_LOOKUP in _ROLE_GRANTS["pm"]
    # FR-031 least-privilege: viewer is denied.
    assert PRODUCT_ANALYTICS_VIEW not in _ROLE_GRANTS["viewer"]
    assert USER_LOOKUP not in _ROLE_GRANTS["viewer"]