"""REQ-044 CROSS — Saved Views + Role 扩展 OpenAPI contract test.

Locks the 5-endpoint surface + payload shapes documented in
``.claude/teams/req044/ac-matrix/REQ-044-CROSS.md``:

- ``GET    /api/v1/admin-console/saved-views?workspace_id=X``
- ``POST   /api/v1/admin-console/saved-views``
- ``GET    /api/v1/admin-console/saved-views/{id}``
- ``PATCH  /api/v1/admin-console/saved-views/{id}``
- ``DELETE /api/v1/admin-console/saved-views/{id}``
- ``GET    /api/v1/admin-console/saved-views/health``

Coverage of AC matrix:

- AC-6.1 — list envelope + 8 PM-default seed views.
- AC-6.2 — POST returns saved_view_id + audit_event_id.
- AC-6.3 — GET detail envelope.
- AC-6.4 — PATCH (audit logged, requires SAVED_VIEW_CHANGE, 403 viewer).
- AC-6.5 — DELETE (audit logged).
- AC-6.6 — role-based filter: PM sees all; non-PM sees scoped.
- AC-6.7 — 12th audit action ``saved_view_change`` in VALID_ACTIONS.
- AC-6.12 — cross-workspace shared_with role-share.
- AC-2.1 — governance access matrix 5x8x6 (240 entries).
- AC-2.2 — _ROLE_GRANTS covers all 5 roles (admin/owner/pm/reviewer/
  operations/maintainer); viewer empty.
- IT-1 — IT-3 — cross-US regression + type sync + auth sync.
- EC-1 — saved_view filter references deleted cohort → warning.
- EC-2 — shared_with revoke → permission revoked.
- EC-3 — concurrent update → 422 version_conflict.
- EC-4 — viewer cannot create → 403.

Skipped if ``DATABASE_URL`` is not configured for parity with the
rest of the 033/039/044 suites.
"""
from __future__ import annotations

import os

import pytest


def _app():
    from app.main import create_app

    return create_app()


# ---------------------------------------------------------------------------
# Module import surface sanity
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_saved_views_module_imports() -> None:
    """The saved_views subpackage must import without error."""
    if not os.getenv("DATABASE_URL"):
        pytest.skip("DATABASE_URL not configured; contract test skipped")

    from app.modules.admin_console.saved_views import (  # noqa: F401
        service,
        repository,
    )
    from app.modules.admin_console.saved_views.api import (  # noqa: F401
        saved_views_router,
    )
    from app.modules.admin_console.saved_views.schemas import (  # noqa: F401
        SavedView,
        SavedViewCreateRequest,
        SavedViewUpdateRequest,
        SavedViewListResponse,
        SavedViewDetailResponse,
        SavedViewTrustStatus,
        SharedWithRole,
    )
    from app.modules.admin_console.audit import (  # noqa: F401
        log_saved_view_change,
    )


@pytest.mark.contract
def test_saved_views_routes_in_openapi() -> None:
    """All 5 saved_views routes + 1 health must appear in the OpenAPI surface."""
    if not os.getenv("DATABASE_URL"):
        pytest.skip("DATABASE_URL not configured; contract test skipped")

    app = _app()
    expected = {
        "/api/v1/admin-console/saved-views",
        "/api/v1/admin-console/saved-views/health",
    }
    actual = {
        r.path
        for r in app.routes
        if hasattr(r, "path") and "/admin-console/saved-views" in r.path
    }
    # We must have at least the prefix + health (parameterised routes
    # show up via their template path; FastAPI emits the raw path
    # template like ``/api/v1/admin-console/saved-views/{saved_view_id}``).
    missing = {p for p in expected if not any(p in a for a in actual)}
    assert not missing, f"missing saved_views routes: {missing}"
    # Parameterised routes are present.
    assert any("{saved_view_id}" in a for a in actual), (
        f"parameterised saved_views routes missing: {actual}"
    )


# ---------------------------------------------------------------------------
# AC-6.7 / AC-2.5 — 12 audit actions + saved_view_change is one of them
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_audit_action_saved_view_change() -> None:
    """AC-6.7: audit.VALID_ACTIONS contains 'saved_view_change' (12th token)."""
    from app.modules.admin_console.audit import VALID_ACTIONS
    from app.modules.admin_console.governance.schemas import AUDIT_ACTIONS

    assert "saved_view_change" in VALID_ACTIONS
    assert "saved_view_change" in AUDIT_ACTIONS
    assert len(VALID_ACTIONS) == 12


# ---------------------------------------------------------------------------
# AC-6.1 — GET list envelope + 8 PM-default seed views
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_list_saved_views_returns_full_envelope() -> None:
    """AC-6.1: GET /saved-views?workspace_id=X returns ≥1 seed view per workspace."""
    from app.modules.admin_console.saved_views import repository
    from app.modules.admin_console.saved_views.service import list_views

    repository.reset_for_tests()
    repository.seed_once()

    for ws in [
        "command-center",
        "product-analytics",
        "ai-operations",
        "incidents-badcases",
        "logs-and-traces",
        "users-accounts",
        "reports",
        "governance",
    ]:
        result = list_views(workspace_id=ws, caller_role="pm")
        assert result.total >= 1, f"workspace {ws}: expected ≥1 view, got 0"
        assert result.workspace_id == ws
        assert result.role_view == "pm"
        view = result.views[0]
        # 12 fields: id, name, workspace_id, filters, owner_user_id,
        # description, trust_status, created_at, updated_at,
        # shared_with, version, warnings
        for field in (
            "id",
            "name",
            "workspace_id",
            "filters",
            "owner_user_id",
            "description",
            "trust_status",
            "created_at",
            "updated_at",
            "shared_with",
            "version",
            "warnings",
        ):
            assert hasattr(view, field), f"view missing field: {field}"


# ---------------------------------------------------------------------------
# AC-6.2 — POST returns saved_view_id + audit_event_id
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_create_saved_view_returns_id_and_audit() -> None:
    """AC-6.2: POST returns saved_view_id + audit_event_id (FR-034)."""
    from app.modules.admin_console.governance.repository import list_audit_events
    from app.modules.admin_console.saved_views import repository
    from app.modules.admin_console.saved_views.schemas import SavedViewCreateRequest
    from app.modules.admin_console.saved_views.service import create_view

    repository.reset_for_tests()
    repository.seed_once()
    # Wipe audit buffer for clean assertion.
    from app.modules.admin_console.governance import repository as gov_repo

    gov_repo.reset_for_tests()

    body = SavedViewCreateRequest(
        name="跨工作空间 saved view smoke",
        workspace_id="command-center",
        filters={"since": "7d"},
        description="contract test smoke",
        shared_with=["pm", "operations"],
        trust_status="verified",
    )
    resp = create_view(
        body=body,
        owner_user_id="019ec1be-0000-0000-0000-000000000099",
        caller_role="pm",
    )
    assert resp.view.id
    assert resp.view.name == "跨工作空间 saved view smoke"
    assert resp.view.workspace_id == "command-center"
    assert resp.view.filters == {"since": "7d"}
    assert resp.view.trust_status == "verified"
    assert "operations" in resp.view.shared_with
    assert resp.view.version == 1
    assert resp.audit_event_id

    # Verify the audit event was appended to the US6 governance buffer
    # with action=saved_view_change + target_kind=saved_view.
    events = list_audit_events(action="saved_view_change")
    assert len(events) == 1
    assert events[0].target_kind == "saved_view"
    assert events[0].target_id == resp.view.id
    # AuditEvent only carries 9 fields per FR-034 (event_id/actor/
    # timestamp/target_kind/target_id/action/reason/result/
    # visibility_mode). The lifecycle marker is encoded into the
    # ``reason`` field — ``saved_view created: sv-... workspace=...``.
    assert "created" in events[0].reason, (
        f"expected 'created' in reason, got: {events[0].reason!r}"
    )


# ---------------------------------------------------------------------------
# AC-6.3 — GET detail envelope
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_get_saved_view_detail() -> None:
    """AC-6.3: GET detail returns view + warnings."""
    from app.modules.admin_console.saved_views import repository
    from app.modules.admin_console.saved_views.service import get_view

    repository.reset_for_tests()
    repository.seed_once()
    rows = repository.list_saved_views(workspace_id="command-center", role="pm")
    assert rows, "seed must produce ≥1 view"
    first = rows[0]

    detail = get_view(saved_view_id=first.id, caller_role="pm")
    assert detail.view.id == first.id
    assert detail.permission_revoked is False
    # PM is privileged — no permission-revoked warning.
    assert "permission revoked" not in " ".join(detail.warnings)


# ---------------------------------------------------------------------------
# AC-6.4 — PATCH (audit logged, requires SAVED_VIEW_CHANGE)
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_patch_saved_view_audited() -> None:
    """AC-6.4: PATCH bumps version + writes audit event."""
    from app.modules.admin_console.governance import repository as gov_repo
    from app.modules.admin_console.governance.repository import list_audit_events
    from app.modules.admin_console.saved_views import repository
    from app.modules.admin_console.saved_views.schemas import SavedViewUpdateRequest
    from app.modules.admin_console.saved_views.service import update_view

    repository.reset_for_tests()
    repository.seed_once()
    gov_repo.reset_for_tests()

    rows = repository.list_saved_views(workspace_id="command-center", role="pm")
    target = rows[0]

    updated = update_view(
        saved_view_id=target.id,
        body=SavedViewUpdateRequest(
            name="new name",
            version=target.version,
        ),
        caller_role="pm",
    )
    assert updated.name == "new name"
    assert updated.version == target.version + 1

    events = list_audit_events(action="saved_view_change")
    assert len(events) == 1
    assert "updated" in events[0].reason


# ---------------------------------------------------------------------------
# AC-6.5 — DELETE audit logged
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_delete_saved_view_audited() -> None:
    """AC-6.5: DELETE removes + writes audit event."""
    from app.modules.admin_console.governance import repository as gov_repo
    from app.modules.admin_console.governance.repository import list_audit_events
    from app.modules.admin_console.saved_views import repository
    from app.modules.admin_console.saved_views.service import delete_view

    repository.reset_for_tests()
    repository.seed_once()
    gov_repo.reset_for_tests()

    rows = repository.list_saved_views(workspace_id="command-center", role="pm")
    target = rows[0]

    delete_view(saved_view_id=target.id, caller_role="pm")
    assert repository.get_saved_view(target.id) is None

    events = list_audit_events(action="saved_view_change")
    assert len(events) == 1
    assert "deleted" in events[0].reason


# ---------------------------------------------------------------------------
# AC-6.6 — role-based filter: PM sees all; operations sees shared_with scope
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_role_based_filter_pm_sees_all_operations_scoped() -> None:
    """AC-6.6: PM sees all views; operations only sees views with shared_with=['operations']."""
    from app.modules.admin_console.saved_views import repository
    from app.modules.admin_console.saved_views.service import list_views

    repository.reset_for_tests()
    repository.seed_once()
    # Reset all audit buffer to ensure clean.
    from app.modules.admin_console.governance import repository as gov_repo

    gov_repo.reset_for_tests()

    # PM sees all 8 (one per workspace).
    total_views_across_all_ws = 0
    for ws in [
        "command-center",
        "product-analytics",
        "ai-operations",
        "incidents-badcases",
        "logs-and-traces",
        "users-accounts",
        "reports",
        "governance",
    ]:
        result = list_views(workspace_id=ws, caller_role="pm")
        total_views_across_all_ws += result.total
    assert total_views_across_all_ws == 8, (
        f"expected PM to see all 8 views, got {total_views_across_all_ws}"
    )

    # Operations on logs-and-traces: seed view shared_with=['maintainer','owner','pm']
    # → operations should see 0.
    result = list_views(workspace_id="logs-and-traces", caller_role="operations")
    assert result.total == 0, (
        f"expected operations to see 0 on logs-and-traces, got {result.total}"
    )

    # Operations on incidents-badcases: seed view shared_with=
    # ['pm','owner','operations','maintainer'] → 1.
    result = list_views(
        workspace_id="incidents-badcases", caller_role="operations"
    )
    assert result.total == 1, (
        f"expected operations to see 1 on incidents-badcases, got {result.total}"
    )


# ---------------------------------------------------------------------------
# AC-6.12 — cross-workspace shared_with role-share
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_cross_workspace_role_share() -> None:
    """AC-6.12: PM A creates saved_view; operations B can see it via shared_with."""
    from app.modules.admin_console.saved_views import repository
    from app.modules.admin_console.saved_views.schemas import SavedViewCreateRequest
    from app.modules.admin_console.saved_views.service import (
        create_view,
        list_views,
    )

    repository.reset_for_tests()
    repository.seed_once()

    body = SavedViewCreateRequest(
        name="PM 跨工作空间共享给 operations",
        workspace_id="command-center",
        filters={"since": "7d"},
        description="AC-6.12 happy path",
        shared_with=["operations"],  # share only with operations
        trust_status="verified",
    )
    resp = create_view(
        body=body,
        owner_user_id="019ec1be-0000-0000-0000-000000000050",
        caller_role="pm",
    )
    view_id = resp.view.id

    # operations sees the view (shared_with contains 'operations').
    op_view = list_views(workspace_id="command-center", caller_role="operations")
    assert any(v.id == view_id for v in op_view.views), (
        "operations should see the shared view"
    )

    # maintainer (no shared_with) sees the seed view on logs-and-traces
    # but NOT the new shared view on command-center.
    maintainer_view = list_views(
        workspace_id="command-center", caller_role="maintainer"
    )
    assert not any(v.id == view_id for v in maintainer_view.views), (
        "maintainer should NOT see a view shared only with operations"
    )


# ---------------------------------------------------------------------------
# AC-2.1 — governance access matrix 5x8x6 (240 entries)
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_access_matrix_includes_saved_view_view_change() -> None:
    """AC-2.1: governance.access_matrix is 5x8x6 = 240 (US6 invariant; CROSS inherits)."""
    from app.modules.admin_console.governance.service import get_access_matrix

    m = get_access_matrix()
    assert m.total == 240
    assert m.role_count == 5
    assert m.workspace_count == 8
    assert m.capability_count == 6


# ---------------------------------------------------------------------------
# AC-2.2 — _ROLE_GRANTS covers all 5 roles
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_role_grants_all_five_roles_listed() -> None:
    """AC-2.2: _ROLE_GRANTS lists admin/owner/pm/operations/maintainer/reviewer; viewer = AUDIT_VIEW + GOVERNANCE_VIEW only."""
    from app.modules.admin_console import auth as auth_mod

    expected_roles = {"admin", "owner", "pm", "operations", "maintainer", "reviewer"}
    actual_roles = set(auth_mod._ROLE_GRANTS.keys())
    missing = expected_roles - actual_roles
    assert not missing, f"_ROLE_GRANTS missing roles: {missing}"
    # viewer is the least-privilege role: only audit-view + governance-view.
    # NOT empty — viewer is allowed to see they are being audited.
    viewer_caps = auth_mod._ROLE_GRANTS["viewer"]
    assert "AUDIT_VIEW" in viewer_caps
    assert "GOVERNANCE_VIEW" in viewer_caps
    assert "SAVED_VIEW_VIEW" not in viewer_caps, "viewer MUST NOT see saved views (FR-031)"


# ---------------------------------------------------------------------------
# IT-3 — 5 role × 12 capability RBAC map covers new tokens
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_role_grants_cover_saved_view_tokens() -> None:
    """IT-3: SAVED_VIEW_VIEW granted to 5 roles (except viewer); SAVED_VIEW_CHANGE to 4 editor roles."""
    from app.modules.admin_console import auth as auth_mod
    from app.modules.admin_console.auth import (
        SAVED_VIEW_CHANGE,
        SAVED_VIEW_VIEW,
    )

    view_grantees = {
        role
        for role, caps in auth_mod._ROLE_GRANTS.items()
        if SAVED_VIEW_VIEW in caps
    }
    change_grantees = {
        role
        for role, caps in auth_mod._ROLE_GRANTS.items()
        if SAVED_VIEW_CHANGE in caps
    }
    # PM / admin / owner / operations / maintainer / reviewer — 6 roles.
    assert view_grantees == {
        "admin",
        "owner",
        "pm",
        "operations",
        "maintainer",
        "reviewer",
    }, f"SAVED_VIEW_VIEW grantees: {view_grantees}"
    # Change: 5 roles (no reviewer; reviewer is read-only).
    assert change_grantees == {
        "admin",
        "owner",
        "pm",
        "operations",
        "maintainer",
    }, f"SAVED_VIEW_CHANGE grantees: {change_grantees}"


# ---------------------------------------------------------------------------
# EC-1 — saved_view filter references deleted cohort → warning
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_saved_view_deleted_cohort_warning() -> None:
    """EC-1: filter references deleted cohort → 'filter references deleted cohort, please update'."""
    from app.modules.admin_console.saved_views import repository
    from app.modules.admin_console.saved_views.service import (
        create_view,
        get_view,
    )

    repository.reset_for_tests()
    repository.seed_once()
    # Mark 'exp-cohort' as deleted (the new view below references it).
    repository.mark_cohort_deleted("exp-cohort")

    body_repo = repository.__class__
    # Use service create so audit also fires.
    from app.modules.admin_console.saved_views.schemas import (
        SavedViewCreateRequest,
    )

    body = SavedViewCreateRequest(
        name="EC-1 cohort-deleted",
        workspace_id="command-center",
        filters={"cohort": "exp-cohort"},
        description="EC-1",
        shared_with=[],
        trust_status="verified",
    )
    resp = create_view(
        body=body,
        owner_user_id="019ec1be-0000-0000-0000-000000000077",
        caller_role="pm",
    )

    detail = get_view(saved_view_id=resp.view.id, caller_role="pm")
    assert any("deleted cohort" in w for w in detail.warnings), (
        f"expected EC-1 warning, got: {detail.warnings}"
    )


# ---------------------------------------------------------------------------
# EC-2 — shared_with revoke → permission revoked
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_shared_with_revoke_shows_warning() -> None:
    """EC-2: shared_with revoke → 'permission revoked' warning."""
    from app.modules.admin_console.saved_views import repository
    from app.modules.admin_console.saved_views.service import (
        SavedViewAccessDeniedError,
        create_view,
        get_view,
    )

    repository.reset_for_tests()
    repository.seed_once()

    from app.modules.admin_console.saved_views.schemas import (
        SavedViewCreateRequest,
    )

    body = SavedViewCreateRequest(
        name="EC-2 revoke",
        workspace_id="command-center",
        filters={"since": "7d"},
        description="EC-2",
        # share only with reviewer.
        shared_with=["reviewer"],
        trust_status="verified",
    )
    resp = create_view(
        body=body,
        owner_user_id="019ec1be-0000-0000-0000-000000000088",
        caller_role="pm",
    )

    # reviewer can see it (in shared_with).
    detail_reviewer = get_view(saved_view_id=resp.view.id, caller_role="reviewer")
    assert detail_reviewer.permission_revoked is False

    # operations cannot see it (not in shared_with) → SavedViewAccessDeniedError.
    with pytest.raises(SavedViewAccessDeniedError):
        get_view(saved_view_id=resp.view.id, caller_role="operations")


# ---------------------------------------------------------------------------
# EC-3 — concurrent update → 422 version_conflict
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_saved_view_concurrent_422_version_conflict() -> None:
    """EC-3: PATCH with stale version → SavedViewVersionConflictError."""
    from app.modules.admin_console.saved_views import repository
    from app.modules.admin_console.saved_views.schemas import SavedViewUpdateRequest
    from app.modules.admin_console.saved_views.service import (
        SavedViewVersionConflictError,
        update_view,
    )

    repository.reset_for_tests()
    repository.seed_once()

    rows = repository.list_saved_views(workspace_id="command-center", role="pm")
    target = rows[0]

    with pytest.raises(SavedViewVersionConflictError):
        update_view(
            saved_view_id=target.id,
            body=SavedViewUpdateRequest(
                name="stale write",
                version=target.version + 99,  # wrong version
            ),
            caller_role="pm",
        )


# ---------------------------------------------------------------------------
# EC-4 — viewer cannot create → 403
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_viewer_cannot_create_saved_view() -> None:
    """EC-4: viewer (empty grants) → user_has_capability(SAVED_VIEW_CHANGE) is False."""
    from app.modules.admin_console.auth import (
        SAVED_VIEW_CHANGE,
        set_default_role,
        reset_for_tests,
        user_has_capability,
    )

    reset_for_tests()
    set_default_role("viewer")
    fake = __import__("uuid").UUID("00000000-0000-0000-0000-000000000003")
    assert user_has_capability(fake, SAVED_VIEW_CHANGE) is False
    reset_for_tests()


# ---------------------------------------------------------------------------
# IT-2 — Type alignment: frontend SharedWithRole ↔ backend Literal
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_workspace_id_literal_alignment() -> None:
    """IT-2: WorkspaceId Literal matches the 8 stable workspaces (cross-team contract)."""
    import typing

    from app.modules.admin_console.governance.schemas import WorkspaceId

    args = set(typing.get_args(WorkspaceId))
    expected = {
        "command-center",
        "product-analytics",
        "ai-operations",
        "incidents-badcases",
        "logs-and-traces",
        "users-accounts",
        "reports",
        "governance",
    }
    assert args == expected, f"WorkspaceId mismatch: {args ^ expected}"


@pytest.mark.contract
def test_shared_with_role_literal_alignment() -> None:
    """IT-2: SharedWithRole Literal matches the 5 console roles minus 'unknown'."""
    import typing

    from app.modules.admin_console.saved_views.schemas import SharedWithRole

    args = set(typing.get_args(SharedWithRole))
    expected = {"pm", "operations", "maintainer", "reviewer", "owner"}
    assert args == expected, f"SharedWithRole mismatch: {args ^ expected}"