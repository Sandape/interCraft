"""REQ-044 CROSS — Saved Views workspace (FR-006).

This sub-module lands the real persistence layer for saved views that
US1 (IA shell) stubbed with ``throw NotImplementedError``. The full
cross-cutting scope is FR-006 + FR-002:

- :mod:`schemas` — Pydantic v2 models for ``SavedView`` (single row)
  + ``SavedViewCreateRequest`` (POST body) + ``SavedViewUpdateRequest``
  (PATCH body) + ``SavedViewListResponse`` (GET list envelope) +
  ``SavedViewDetailResponse`` (GET single envelope). Also re-exports
  the cross-cutting :data:`SavedViewTrustStatus` Literal
  (verified / pending / deprecated) so the frontend mirrors
  exactly.
- :mod:`repository` — in-memory buffer + role-aware filter. ``pm``
  sees all; non-pm roles see only views whose ``shared_with`` list
  contains their role (FR-031 + AC-6.6). 8 seed views across 8
  workspaces (1 PM-default per workspace) for E2E happy-path.
- :mod:`service` — orchestration: list / get / create / update /
  delete + role-based filtering + optimistic locking (EC-3
  422 version_conflict) + warning surfaces (EC-1 deleted cohort,
  EC-2 permission revoked).
- :mod:`api` — FastAPI router mounted at
  ``/api/v1/admin-console/saved-views`` with 5 endpoints (list /
  create / get / patch / delete) + 1 health.

Auth: capability check via
:func:`app.modules.admin_console.auth.require_capability` with the
2 CROSS capability tokens (:data:`SAVED_VIEW_VIEW` +
:data:`SAVED_VIEW_CHANGE`). Audit: 12th audit action
``saved_view_change`` (target_kind='saved_view') is emitted on
create / update / delete lifecycle events (FR-034 AC-6.7).

[CROSS-TEAM-DEBT] Real saved_views DB + cross-org share scope
+ webhook notification land in Phase 2 batch 5. Until then all
state is in-process + seed-driven (mirrors US1/2/3/4/6/7
in-memory pattern). Real RBAC DB also lands in batch 5; Phase 2
batch 5 will widen the migration 0022 CHECK constraint to allow
the 12th audit action ``saved_view_change`` to persist via
``admin_audit_log``.
"""
from app.modules.admin_console.saved_views import repository, service
from app.modules.admin_console.saved_views.api import saved_views_router

__all__ = [
    "repository",
    "saved_views_router",
    "service",
]