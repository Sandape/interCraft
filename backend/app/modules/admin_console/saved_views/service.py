"""REQ-044 CROSS — Saved Views service layer (FR-006 + FR-031 + Edge Cases).

Pure orchestration: list / get / create / update / delete + role-based
filtering + optimistic locking (EC-3) + warning surfaces (EC-1
deleted-cohort, EC-2 permission-revoked).

Functions:

- :func:`list_views` — GET /saved-views with role-aware filter
  (FR-006 AC-6.1 + AC-6.6).
- :func:`get_view` — GET /saved-views/{id} with role-aware warnings
  (FR-006 AC-6.3 + EC-1 + EC-2).
- :func:`create_view` — POST /saved-views + audit event
  (FR-006 AC-6.2 + SC-009).
- :func:`update_view` — PATCH /saved-views/{id} + audit + optimistic
  lock (FR-006 AC-6.4 + SC-009 + EC-3).
- :func:`delete_view` — DELETE /saved-views/{id} + audit
  (FR-006 AC-6.5 + SC-009).
- :func:`_emit_saved_view_audit` — helper writing the 12th audit
  action ``saved_view_change`` to the US6 governance audit buffer.
- :func:`_coerce_role` — resolve admin→owner, unknown→pm; ensures
  the role we filter by is always one of the 5 canonical ConsoleRole
  names (defence-in-depth against the frontend sending weird strings).

Error semantics:

- 422 ``version_conflict`` (EC-3) when the client-supplied
  ``version`` does not match the current row.
- 404 ``saved_view_not_found`` when the row is missing.
- 403 ``saved_view_role_denied`` when the role can't see the row
  (so we don't leak existence).

[CROSS-TEAM-DEBT] Real DB + cross-org share scope land in Phase 2
batch 5. Until then all state is in-process + seed-driven.
"""
from __future__ import annotations

import threading
from datetime import UTC, datetime
from typing import Any

from app.modules.admin_console.governance.repository import (
    append_audit_event,
    next_audit_event_id,
)
from app.modules.admin_console.governance.schemas import (
    AuditEvent,
    AuditResult,
)
from app.modules.admin_console.saved_views import repository
from app.modules.admin_console.saved_views.schemas import (
    SavedView,
    SavedViewCreateRequest,
    SavedViewCreateResponse,
    SavedViewDetailResponse,
    SavedViewListResponse,
    SavedViewUpdateRequest,
    SharedWithRole,
    WorkspaceId,
)

_lock = threading.Lock()


def _now_iso() -> str:
    return (
        datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    )


def _coerce_role(role: str | None) -> SharedWithRole:
    """Resolve admin→owner / unknown→pm / None→pm.

    Defence-in-depth so the repository role-filter never sees the
    reserved ``unknown`` sentinel or the legacy ``admin`` alias.
    """
    if role in (None, "unknown", ""):
        return "pm"
    if role == "admin":
        return "owner"
    valid = {"pm", "operations", "maintainer", "reviewer", "owner"}
    if role in valid:
        return role  # type: ignore[return-value]
    return "pm"


def _emit_saved_view_audit(
    *,
    saved_view_id: str,
    workspace_id: WorkspaceId,
    lifecycle: str,  # 'created' | 'updated' | 'deleted'
    actor: str,
    name: str | None = None,
    shared_with: list[SharedWithRole] | None = None,
) -> str:
    """Append the 12th audit action ``saved_view_change`` to the US6 buffer.

    Returns the audit event id so the API layer can surface it to the
    caller (FR-006 AC-6.2 / SC-009).
    """
    audit_id = next_audit_event_id()
    audit = AuditEvent(
        event_id=audit_id,
        actor=actor,
        timestamp=_now_iso(),
        target_kind="saved_view",
        target_id=saved_view_id,
        action="saved_view_change",
        reason=f"saved_view {lifecycle}: {saved_view_id} workspace={workspace_id}",
        result="executed",
        visibility_mode="full",
    )
    append_audit_event(audit)
    return audit_id


# ---------------------------------------------------------------------------
# FR-006 — List
# ---------------------------------------------------------------------------


def list_views(
    *,
    workspace_id: WorkspaceId,
    caller_role: str | None,
) -> SavedViewListResponse:
    """Return saved views filtered by workspace + role visibility."""
    role = _coerce_role(caller_role)
    rows = repository.list_saved_views(workspace_id=workspace_id, role=role)
    # EC-1: warnings per row (deleted cohort).
    decorated: list[SavedView] = []
    for v in rows:
        warnings = repository.compute_view_warnings(v)
        decorated.append(v.model_copy(update={"warnings": warnings}))
    return SavedViewListResponse(
        views=decorated,
        total=len(decorated),
        workspace_id=workspace_id,
        role_view=role,
        warnings=[],
    )


# ---------------------------------------------------------------------------
# FR-006 — Get (detail)
# ---------------------------------------------------------------------------


class SavedViewNotFoundError(Exception):
    """Raised when the requested saved_view does not exist (AC-6.3)."""

    def __init__(self, saved_view_id: str):
        self.saved_view_id = saved_view_id
        super().__init__(f"saved_view {saved_view_id} not found")


class SavedViewAccessDeniedError(Exception):
    """Raised when the caller's role cannot see this row (AC-6.6).

    We deliberately do NOT distinguish "not found" from "access
    denied" for saved views (less info leakage than 404); the API
    layer maps both to 403 / 404 per the spec — but the service
    layer emits the two distinct error types so tests can pin them.
    """

    def __init__(self, saved_view_id: str, caller_role: str):
        self.saved_view_id = saved_view_id
        self.caller_role = caller_role
        super().__init__(
            f"saved_view {saved_view_id} access denied for role={caller_role}"
        )


def get_view(
    *,
    saved_view_id: str,
    caller_role: str | None,
) -> SavedViewDetailResponse:
    """Return a saved view with EC-1/EC-2 warnings."""
    role = _coerce_role(caller_role)
    view = repository.get_saved_view(saved_view_id)
    if view is None:
        raise SavedViewNotFoundError(saved_view_id)

    # Role-based visibility (EC-2 surface).
    visible = (role == "pm") or (role in view.shared_with)
    permission_revoked = not visible

    warnings = repository.compute_view_warnings(view)
    if permission_revoked:
        warnings.append("permission revoked — shared_with no longer includes your role")

    if permission_revoked:
        # Match the spec AC-6.6: don't serve detail. The API layer
        # surfaces 403; tests pin via SavedViewAccessDeniedError.
        raise SavedViewAccessDeniedError(saved_view_id, role)

    decorated = view.model_copy(update={"warnings": warnings})
    return SavedViewDetailResponse(
        view=decorated,
        permission_revoked=False,
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# FR-006 — Create
# ---------------------------------------------------------------------------


def create_view(
    body: SavedViewCreateRequest,
    *,
    owner_user_id: str,
    caller_role: str | None,
) -> SavedViewCreateResponse:
    """Create a saved view + audit event (AC-6.2 + SC-009)."""
    view_id = repository.next_saved_view_id()
    now = _now_iso()
    # Persist with ``admin`` alias collapsed to ``owner`` in shared_with.
    shared_with: list[SharedWithRole] = []
    for r in body.shared_with:
        if r == "admin":
            shared_with.append("owner")
        else:
            shared_with.append(r)
    view = SavedView(
        id=view_id,
        name=body.name,
        workspace_id=body.workspace_id,
        filters=dict(body.filters or {}),
        owner_user_id=owner_user_id,
        description=body.description,
        trust_status=body.trust_status,
        created_at=now,
        updated_at=now,
        shared_with=shared_with,
        version=1,
        warnings=[],
    )
    repository.append_saved_view(view)
    role = _coerce_role(caller_role)
    audit_event_id = _emit_saved_view_audit(
        saved_view_id=view_id,
        workspace_id=body.workspace_id,
        lifecycle="created",
        actor=f"@user:{owner_user_id[:8]}",
        name=body.name,
        shared_with=shared_with,
    )
    return SavedViewCreateResponse(
        view=view,
        audit_event_id=audit_event_id,
    )


# ---------------------------------------------------------------------------
# FR-006 — Update (PATCH + EC-3 optimistic locking)
# ---------------------------------------------------------------------------


class SavedViewVersionConflictError(Exception):
    """Raised when the client-supplied version doesn't match (EC-3)."""

    def __init__(self, saved_view_id: str, expected: int, actual: int):
        self.saved_view_id = saved_view_id
        self.expected = expected
        self.actual = actual
        super().__init__(
            f"saved_view {saved_view_id} version conflict: "
            f"expected={expected} actual={actual}"
        )


def update_view(
    *,
    saved_view_id: str,
    body: SavedViewUpdateRequest,
    caller_role: str | None,
) -> SavedView:
    """Update a saved view + audit + optimistic lock (AC-6.4 + EC-3)."""
    role = _coerce_role(caller_role)
    existing = repository.get_saved_view(saved_view_id)
    if existing is None:
        raise SavedViewNotFoundError(saved_view_id)

    # PM can edit anything; non-PM must be in shared_with OR be owner.
    is_owner = (caller_role is None) or (role == "pm") or (
        existing.owner_user_id == caller_role
    ) or (role in existing.shared_with)
    if not is_owner:
        raise SavedViewAccessDeniedError(saved_view_id, role)

    # EC-3 optimistic lock.
    if body.version is not None and body.version != existing.version:
        raise SavedViewVersionConflictError(
            saved_view_id, body.version, existing.version
        )

    update_kwargs: dict[str, Any] = {"updated_at": _now_iso(), "version": existing.version + 1}
    if body.name is not None:
        update_kwargs["name"] = body.name
    if body.filters is not None:
        update_kwargs["filters"] = dict(body.filters)
    if body.description is not None:
        update_kwargs["description"] = body.description
    if body.shared_with is not None:
        # Collapse admin alias.
        collapsed: list[SharedWithRole] = []
        for r in body.shared_with:
            if r == "admin":
                collapsed.append("owner")
            else:
                collapsed.append(r)
        update_kwargs["shared_with"] = collapsed
    if body.trust_status is not None:
        update_kwargs["trust_status"] = body.trust_status

    updated = existing.model_copy(update=update_kwargs)
    repository.update_saved_view(saved_view_id, updated)
    _emit_saved_view_audit(
        saved_view_id=saved_view_id,
        workspace_id=existing.workspace_id,
        lifecycle="updated",
        actor=f"@user:{(caller_role or 'pm')[:8]}",
        name=updated.name,
        shared_with=updated.shared_with,
    )
    return updated


# ---------------------------------------------------------------------------
# FR-006 — Delete
# ---------------------------------------------------------------------------


def delete_view(
    *,
    saved_view_id: str,
    caller_role: str | None,
) -> None:
    """Delete a saved view + audit (AC-6.5 + SC-009)."""
    role = _coerce_role(caller_role)
    existing = repository.get_saved_view(saved_view_id)
    if existing is None:
        raise SavedViewNotFoundError(saved_view_id)

    is_owner = (role == "pm") or (existing.owner_user_id == caller_role) or (
        role in existing.shared_with
    )
    if not is_owner:
        raise SavedViewAccessDeniedError(saved_view_id, role)

    repository.delete_saved_view(saved_view_id)
    _emit_saved_view_audit(
        saved_view_id=saved_view_id,
        workspace_id=existing.workspace_id,
        lifecycle="deleted",
        actor=f"@user:{(caller_role or 'pm')[:8]}",
        name=existing.name,
        shared_with=existing.shared_with,
    )


__all__ = [
    "SavedViewAccessDeniedError",
    "SavedViewNotFoundError",
    "SavedViewVersionConflictError",
    "create_view",
    "delete_view",
    "get_view",
    "list_views",
    "update_view",
]