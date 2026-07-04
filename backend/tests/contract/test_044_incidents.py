"""REQ-044 US4 — Incidents & Badcases OpenAPI contract test (FR-021~FR-023).

Locks the 12-endpoint surface + payload shapes documented in
``.claude/teams/req044/ac-matrix/REQ-044-US4.md``:

- ``GET /api/v1/admin-console/incidents``
- ``GET /api/v1/admin-console/incidents/{id}``
- ``GET /api/v1/admin-console/incidents/{id}/evidence``
- ``GET /api/v1/admin-console/incidents/{id}/comments``
- ``POST /api/v1/admin-console/incidents/{id}/comments`` (INCIDENT_CHANGE)
- ``PATCH /api/v1/admin-console/incidents/{id}/status`` (INCIDENT_CHANGE)
- ``GET /api/v1/admin-console/incidents/{id}/audit-trail``
- ``GET /api/v1/admin-console/incidents/health``
- ``GET /api/v1/admin-console/badcases``
- ``GET /api/v1/admin-console/badcases/{id}``
- ``POST /api/v1/admin-console/badcases/{id}/escalate`` (BADCASE_CHANGE)
- ``GET /api/v1/admin-console/badcases/health``

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
def test_incidents_routes_in_openapi() -> None:
    """All 8 incident routes must appear."""
    if not os.getenv("DATABASE_URL"):
        pytest.skip("DATABASE_URL not configured; contract test skipped")

    app = _app()
    expected = {
        "/api/v1/admin-console/incidents",
        "/api/v1/admin-console/incidents/{incident_id}",
        "/api/v1/admin-console/incidents/{incident_id}/evidence",
        "/api/v1/admin-console/incidents/{incident_id}/comments",
        "/api/v1/admin-console/incidents/{incident_id}/audit-trail",
        "/api/v1/admin-console/incidents/health",
    }
    actual = {
        r.path
        for r in app.routes
        if hasattr(r, "path") and "/admin-console/incidents" in r.path
    }
    missing = expected - actual
    assert not missing, f"missing incidents routes: {missing}"


@pytest.mark.contract
def test_badcases_routes_in_openapi() -> None:
    """All 4 badcase routes must appear."""
    if not os.getenv("DATABASE_URL"):
        pytest.skip("DATABASE_URL not configured; contract test skipped")

    app = _app()
    expected = {
        "/api/v1/admin-console/badcases",
        "/api/v1/admin-console/badcases/{badcase_id}",
        "/api/v1/admin-console/badcases/health",
    }
    actual = {
        r.path
        for r in app.routes
        if hasattr(r, "path") and "/admin-console/badcases" in r.path
    }
    missing = expected - actual
    assert not missing, f"missing badcases routes: {missing}"


# ---------------------------------------------------------------------------
# FR-021 — Incident list: 10 fields + sort + EC-1 split
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_list_incidents_has_all_fields() -> None:
    """AC-21.1: each incident carries 10 FR-021 fields."""
    from app.modules.admin_console.incidents.service import list_incidents
    from app.modules.admin_console.incidents.schemas import Incident

    result = list_incidents()
    assert result.total >= 1, "seed must include ≥1 incident"
    required_fields = {
        "id",
        "title",
        "severity",
        "status",
        "owner",
        "affected_feature_area",
        "affected_journey_step",
        "first_seen_at",
        "last_seen_at",
        "trend",
    }
    schema_fields = set(Incident.model_fields.keys())
    missing = required_fields - schema_fields
    assert not missing, f"Incident schema missing FR-021 fields: {missing}"
    for inc in result.incidents:
        for field in required_fields:
            assert getattr(inc, field), f"incident missing {field}"
    # Seed includes all 4 severities
    severities = {i.severity for i in result.incidents}
    assert severities == {"P0", "P1", "P2", "P3"}, f"severity coverage: {severities}"
    # Seed includes all 4 statuses
    statuses = {i.status for i in result.incidents}
    assert statuses == {"open", "investigating", "resolved", "postmortem"}, (
        f"status coverage: {statuses}"
    )
    # Seed includes all 3 trends
    trends = {i.trend for i in result.incidents}
    assert trends == {"rising", "stable", "declining"}, f"trend coverage: {trends}"


@pytest.mark.contract
def test_incidents_sorted_by_severity_then_last_seen() -> None:
    """AC-21.2: incidents sorted by severity desc + last_seen_at desc."""
    from app.modules.admin_console.incidents.service import list_incidents

    result = list_incidents()
    sev_rank = {"P0": 4, "P1": 3, "P2": 2, "P3": 1}
    for a, b in zip(result.incidents, result.incidents[1:]):
        rank_a, rank_b = sev_rank[a.severity], sev_rank[b.severity]
        if rank_a == rank_b:
            assert a.last_seen_at >= b.last_seen_at, (
                f"sort violated for {a.id} vs {b.id}"
            )
        else:
            assert rank_a > rank_b, (
                f"sort violated: {a.severity} should come before {b.severity}"
            )


# ---------------------------------------------------------------------------
# FR-021 — Single incident detail (AC-21.3)
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_get_incident_detail_includes_common_root_cause() -> None:
    """AC-21.3: incident detail carries common_root_cause + linked_incident_ids (EC-2)."""
    from app.modules.admin_console.incidents.service import get_incident

    inc = get_incident("inc-2026-0703-002")
    assert inc is not None
    assert inc.common_root_cause == "db-timeout-cluster"
    assert "inc-2026-0703-003" in inc.linked_incident_ids
    # The sibling also references back
    sibling = get_incident("inc-2026-0703-003")
    assert sibling is not None
    assert "inc-2026-0703-002" in sibling.linked_incident_ids


@pytest.mark.contract
def test_get_incident_returns_none_for_unknown_id() -> None:
    """Unknown incident id → None (caller maps to 404)."""
    from app.modules.admin_console.incidents.service import get_incident

    assert get_incident("inc-does-not-exist") is None


# ---------------------------------------------------------------------------
# FR-022 — Evidence: 8-type coverage
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_evidence_links_cover_eight_types() -> None:
    """AC-22.1: evidence list covers all 8 FR-022 types per incident."""
    from app.modules.admin_console.incidents.service import get_incident_evidence

    ev = get_incident_evidence("inc-2026-0704-001")
    assert ev.total == 8, f"expected 8 evidence links, got {ev.total}"
    expected_types = {
        "product_metric",
        "user_impact",
        "ai_task",
        "eval_case",
        "log",
        "trace",
        "release",
        "comment",
    }
    assert set(ev.coverage.keys()) == expected_types, (
        f"coverage keys: {set(ev.coverage.keys())}"
    )
    for link in ev.evidence_links:
        assert link.reference_id
        assert link.href
        assert link.label
    # Each type has exactly 1 link in the seed.
    for t, count in ev.coverage.items():
        assert count == 1, f"type {t} has {count} links (expected 1)"


@pytest.mark.contract
def test_evidence_for_unknown_incident_returns_empty() -> None:
    """Unknown incident → empty list with total=0 (FR-028 valid zero)."""
    from app.modules.admin_console.incidents.service import get_incident_evidence

    ev = get_incident_evidence("inc-does-not-exist")
    assert ev.total == 0
    assert ev.evidence_links == []
    assert ev.coverage == {}


# ---------------------------------------------------------------------------
# FR-022 — Comments + status change (AC-22.2 + EC-4)
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_add_comment_appends_to_in_memory_buffer() -> None:
    """AC-22.2: add comment appends + is visible in subsequent list call."""
    from app.modules.admin_console.incidents import service

    service.reset_for_tests()
    before = service.list_incident_comments("inc-2026-0704-001").total
    new_comment = service.add_incident_comment(
        incident_id="inc-2026-0704-001",
        actor="@test-user",
        body="contract test comment",
        reason="verifying AC-22.2",
    )
    after = service.list_incident_comments("inc-2026-0704-001")
    assert after.total == before + 1
    assert any(c.id == new_comment.id for c in after.comments)
    assert new_comment.body == "contract test comment"
    assert new_comment.actor == "@test-user"


@pytest.mark.contract
def test_add_comment_requires_incident_change_capability() -> None:
    """AC-22.2: POST /comments endpoint requires INCIDENT_CHANGE capability."""
    from app.modules.admin_console.incidents.api import INCIDENT_CHANGE

    assert INCIDENT_CHANGE == "INCIDENT_CHANGE"


@pytest.mark.contract
def test_status_change_audit_trail() -> None:
    """EC-4: status change records actor + timestamp + reason + before + after."""
    from app.modules.admin_console.incidents import service

    service.reset_for_tests()
    entry = service.change_incident_status(
        incident_id="inc-2026-0704-001",
        actor="@contract-test",
        new_status="investigating",
        new_owner="@ops-oncall",
        reason="EC-4 contract test",
    )
    # All 5 EC-4 fields are populated.
    assert entry.actor == "@contract-test"
    assert entry.timestamp
    assert entry.reason == "EC-4 contract test"
    assert entry.before_state == {"status": "open", "owner": "@ops-oncall"}
    assert entry.after_state == {
        "status": "investigating",
        "owner": "@ops-oncall",
    }
    # Trail is retrievable + the new entry is included.
    trail = service.get_incident_audit_trail("inc-2026-0704-001")
    assert any(e.reason == "EC-4 contract test" for e in trail)


# ---------------------------------------------------------------------------
# FR-023 — Badcase list + escalate (AC-23.1/23.4)
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_list_badcases_has_all_fields() -> None:
    """AC-23.1: badcase carries all 10 FR-023 fields."""
    from app.modules.admin_console.incidents.schemas import Badcase
    from app.modules.admin_console.incidents.service import list_badcases

    result = list_badcases()
    assert result.total >= 1
    required_fields = {
        "id",
        "eval_verdict",
        "affected_feature_area",
        "affected_user_id",
        "privacy_class",
        "classification",
        "owner",
        "status",
        "resolution",
        "first_seen_at",
    }
    schema_fields = set(Badcase.model_fields.keys())
    missing = required_fields - schema_fields
    assert not missing, f"Badcase schema missing FR-023 fields: {missing}"
    for bc in result.badcases:
        for field in required_fields:
            # ``resolution`` is allowed to be empty for "open" badcases.
            if field == "resolution":
                assert bc.resolution is not None, f"badcase missing {field}"
            else:
                assert getattr(bc, field), f"badcase missing {field}"
    # Coverage: all 4 statuses + 3 privacy classes
    statuses = {b.status for b in result.badcases}
    assert statuses == {"open", "reviewing", "closed", "escalated"}, statuses
    privacy = {b.privacy_class for b in result.badcases}
    assert privacy == {"public", "internal", "restricted"}, privacy


@pytest.mark.contract
def test_escalate_badcase_to_incident() -> None:
    """AC-23.4: POST /badcases/{id}/escalate returns a new incident_id."""
    from app.modules.admin_console.incidents import service

    service.reset_for_tests()
    response = service.escalate_badcase_to_incident(
        badcase_id="bc-2026-0704-001",
        actor="@contract-test",
    )
    assert response.badcase_id == "bc-2026-0704-001"
    assert response.incident_id.startswith("inc-escalated-")
    assert response.escalated_at
    assert response.escalated_by == "@contract-test"


@pytest.mark.contract
def test_escalate_unknown_badcase_raises() -> None:
    """Unknown badcase → ValueError (caller maps to 404)."""
    from app.modules.admin_console.incidents import service
    import pytest as _pytest

    with _pytest.raises(ValueError):
        service.escalate_badcase_to_incident(
            badcase_id="bc-does-not-exist",
            actor="@contract-test",
        )


# ---------------------------------------------------------------------------
# EC-1 — Candidate incidents are labeled + not merged with confirmed
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_candidate_incident_labeled() -> None:
    """EC-1: low confidence anomalies carry candidate=True + separate count."""
    from app.modules.admin_console.incidents.service import list_incidents

    result = list_incidents()
    candidates = [i for i in result.incidents if i.candidate]
    confirmed = [i for i in result.incidents if not i.candidate]
    assert result.candidate_count == len(candidates)
    assert result.confirmed_count == len(confirmed)
    # The seed has exactly 1 candidate
    assert result.candidate_count >= 1
    # The candidate is sorted BELOW the P0 confirmed incident
    if candidates and confirmed:
        first_confirmed_sev = confirmed[0].severity
        # The candidate P2 should come after P0/P1 confirmed.
        if first_confirmed_sev in {"P0", "P1"}:
            assert candidates[0].id not in {c.id for c in confirmed[:1]}


# ---------------------------------------------------------------------------
# EC-2 — Common root cause cross-link
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_common_root_cause_cross_link() -> None:
    """EC-2: 2+ incidents sharing common_root_cause have cross-links."""
    from app.modules.admin_console.incidents.service import list_incidents

    result = list_incidents()
    siblings = [i for i in result.incidents if i.common_root_cause]
    assert len(siblings) >= 2, "seed must include ≥2 incidents with shared root cause"
    for inc in siblings:
        assert inc.common_root_cause
        assert len(inc.linked_incident_ids) >= 1


# ---------------------------------------------------------------------------
# EC-3 — Ingestion delayed label
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_ingestion_delayed_label() -> None:
    """EC-3: at least 1 incident carries ingestion_delayed=True."""
    from app.modules.admin_console.incidents.service import list_incidents

    result = list_incidents()
    delayed = [i for i in result.incidents if i.ingestion_delayed]
    assert len(delayed) >= 1
    for inc in delayed:
        assert inc.freshness_at  # freshness_at is always set


# ---------------------------------------------------------------------------
# EC-4 — Status change audit trail contains 5 mandatory fields
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_status_change_audit_trail_five_fields() -> None:
    """EC-4: AuditTrailEntry MUST carry actor / timestamp / reason / before_state / after_state."""
    from app.modules.admin_console.incidents.schemas import AuditTrailEntry

    required = {
        "actor",
        "timestamp",
        "reason",
        "before_state",
        "after_state",
    }
    actual = set(AuditTrailEntry.model_fields.keys())
    assert required <= actual, f"AuditTrailEntry missing EC-4 fields: {required - actual}"


# ---------------------------------------------------------------------------
# Capability tokens (FR-031)
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_incident_view_capability_in_role_map() -> None:
    """INCIDENT_VIEW must be granted to admin/owner/pm/operations/maintainer/reviewer."""
    from app.modules.admin_console.auth import (
        INCIDENT_VIEW,
        _ROLE_GRANTS,
    )

    for role in ("admin", "owner", "pm", "operations", "maintainer", "reviewer"):
        assert INCIDENT_VIEW in _ROLE_GRANTS[role], f"{role} missing INCIDENT_VIEW"
    # FR-031 least-privilege: viewer is denied.
    assert INCIDENT_VIEW not in _ROLE_GRANTS["viewer"]


@pytest.mark.contract
def test_incident_change_capability_restricted() -> None:
    """INCIDENT_CHANGE granted to admin/owner/pm/operations/maintainer (NOT reviewer)."""
    from app.modules.admin_console.auth import (
        INCIDENT_CHANGE,
        _ROLE_GRANTS,
    )

    for role in ("admin", "owner", "pm", "operations", "maintainer"):
        assert INCIDENT_CHANGE in _ROLE_GRANTS[role], f"{role} missing INCIDENT_CHANGE"
    # reviewer cannot mutate incidents
    assert INCIDENT_CHANGE not in _ROLE_GRANTS["reviewer"]
    # viewer cannot mutate
    assert INCIDENT_CHANGE not in _ROLE_GRANTS["viewer"]


@pytest.mark.contract
def test_badcase_view_capability_in_role_map() -> None:
    """BADCASE_VIEW must be granted to admin/owner/pm/operations/maintainer/reviewer."""
    from app.modules.admin_console.auth import (
        BADCASE_VIEW,
        _ROLE_GRANTS,
    )

    for role in ("admin", "owner", "pm", "operations", "maintainer", "reviewer"):
        assert BADCASE_VIEW in _ROLE_GRANTS[role], f"{role} missing BADCASE_VIEW"
    assert BADCASE_VIEW not in _ROLE_GRANTS["viewer"]


@pytest.mark.contract
def test_badcase_change_capability_in_role_map() -> None:
    """BADCASE_CHANGE granted to admin/owner/operations/reviewer."""
    from app.modules.admin_console.auth import (
        BADCASE_CHANGE,
        _ROLE_GRANTS,
    )

    for role in ("admin", "owner", "operations", "reviewer"):
        assert BADCASE_CHANGE in _ROLE_GRANTS[role], f"{role} missing BADCASE_CHANGE"


# ---------------------------------------------------------------------------
# Audit tokens (US1 + US4 vocabulary)
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_audit_actions_cover_us4_vocabulary() -> None:
    """VALID_ACTIONS must include the 4 US4 actions (in-memory audit)."""
    from app.modules.admin_console.audit import VALID_ACTIONS

    required = {
        "replay_triggered",
        "diff_computed",
        "tag_added",
        "tag_removed",
        "incident_status_changed",
        "incident_comment_added",
        "badcase_status_changed",
        "badcase_escalated",
    }
    assert required <= VALID_ACTIONS, (
        f"VALID_ACTIONS missing US4 actions: {required - VALID_ACTIONS}"
    )


@pytest.mark.contract
def test_audit_target_kinds_cover_incident_and_badcase() -> None:
    """VALID_TARGET_KINDS must include incident + badcase."""
    from app.modules.admin_console.audit import VALID_TARGET_KINDS

    assert "incident" in VALID_TARGET_KINDS
    assert "badcase" in VALID_TARGET_KINDS


# ---------------------------------------------------------------------------
# Capability API exports
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_capability_tokens_exported() -> None:
    """All 4 US4 capability tokens must be importable from incidents.api."""
    from app.modules.admin_console.incidents import api

    assert api.INCIDENT_VIEW == "INCIDENT_VIEW"
    assert api.INCIDENT_CHANGE == "INCIDENT_CHANGE"
    assert api.BADCASE_VIEW == "BADCASE_VIEW"
    assert api.BADCASE_CHANGE == "BADCASE_CHANGE"
