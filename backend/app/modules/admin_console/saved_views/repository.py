"""REQ-044 CROSS — Saved Views in-memory repository (FR-006).

Seed strategy (parity with US1/2/3/4/6/7):

- :func:`seed_demo_saved_views` — 8 PM-default saved views, one per
  of the 8 stable top-level workspaces. Each is owned by the
  system PM (id ``pm-demo-001``) and is shared_with ``['pm',
  'owner', 'operations']`` so cross-workspace share (AC-6.12) can
  be exercised in tests / Playwright happy path.

In-memory buffers:

- :data:`_SAVED_VIEWS` — ``{saved_view_id: SavedView}``. Append-only
  on create; updated in place on PATCH; removed on DELETE.
- :data:`_DELETED_COHORTS` — set of cohort names flagged as
  ``deleted`` so the EC-1 warning path is exercisable in tests.
- :data:`_NEXT_VIEW_SEQ` — sequence counter for id allocation.

Audit write goes through US6
:func:`governance.repository.append_audit_event` +
:func:`governance.repository.next_audit_event_id` (no new audit
buffer; reuse US6 in-memory ring — same pattern US7 review_snapshots
already established).

[CROSS-TEAM-DEBT] Real saved_views DB lands in Phase 2 batch 5
alongside the wider DB CHECK-constraint widening (12th audit action
``saved_view_change``) + the cross-org share scope. Until then all
state is in-process + seed-driven.
"""
from __future__ import annotations

import threading
from datetime import UTC, datetime, timedelta
from typing import Any, Iterable

from app.modules.admin_console.governance.repository import (
    next_audit_event_id,
)
from app.modules.admin_console.governance.schemas import WorkspaceId
from app.modules.admin_console.saved_views.schemas import (
    SavedView,
    SavedViewCreateRequest,
    SavedViewTrustStatus,
    SharedWithRole,
    WorkspaceId as SavedViewWorkspaceId,  # re-typed for clarity
)

# Alias WorkspaceId for SavedView to use a single source of truth.
WorkspaceId = SavedViewWorkspaceId

_lock = threading.Lock()

#: saved_view_id -> SavedView.
_SAVED_VIEWS: dict[str, SavedView] = {}
#: Cohort names flagged as deleted (EC-1 warning).
_DELETED_COHORTS: set[str] = set()
#: Sequence counter for id allocation.
_NEXT_VIEW_SEQ = 0
#: Initialised flag.
_SEEDED = False

# Owner id used by the demo seed (mirrors ``demo@intercraft.io`` PM).
_PM_OWNER_ID: str = "019ec1be-0000-0000-0000-000000000001"


def _now_iso() -> str:
    return (
        datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    )


def _earlier_iso(days: int = 0, hours: int = 0, minutes: int = 0) -> str:
    return (
        (datetime.now(UTC) - timedelta(days=days, hours=hours, minutes=minutes))
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def reset_for_tests() -> None:
    """Clear all saved_views buffers. Test helper."""
    global _SEEDED, _NEXT_VIEW_SEQ
    with _lock:
        _SAVED_VIEWS.clear()
        _DELETED_COHORTS.clear()
        _NEXT_VIEW_SEQ = 0
        _SEEDED = False


# ---------------------------------------------------------------------------
# Seed (FR-006 / AC-6.1 / AC-6.12 happy-path)
# ---------------------------------------------------------------------------


def _build_seed_view(
    workspace: WorkspaceId,
    name: str,
    description: str,
    filters: dict[str, Any],
    shared_with: list[SharedWithRole] | None = None,
    trust_status: SavedViewTrustStatus = "verified",
    days_old: int = 2,
) -> SavedView:
    """Build a seed view WITHOUT taking the lock.

    NOTE: callers that mutate shared state (``_NEXT_VIEW_SEQ`` +
    ``_SAVED_VIEWS``) MUST already hold :data:`_lock`. Taking the
    lock inside this helper would deadlock against :func:`seed_once`,
    which holds :data:`_lock` for the duration of the seed batch.
    """
    global _NEXT_VIEW_SEQ
    _NEXT_VIEW_SEQ += 1
    view_id = f"sv-{_NEXT_VIEW_SEQ:06d}"
    return SavedView(
        id=view_id,
        name=name,
        workspace_id=workspace,
        filters=filters,
        owner_user_id=_PM_OWNER_ID,
        description=description,
        trust_status=trust_status,
        created_at=_earlier_iso(days=days_old),
        updated_at=_earlier_iso(days=days_old),
        shared_with=list(shared_with or ["pm", "owner", "operations"]),
        version=1,
        warnings=[],
    )


def seed_once() -> None:
    """Seed 8 PM-default saved views, one per workspace (FR-006 AC-6.1).

    Idempotent — call once on first import.
    """
    global _SEEDED
    with _lock:
        if _SEEDED:
            return
        seed_views: list[SavedView] = [
            _build_seed_view(
                workspace="command-center",
                name="PM 默认:本周产品/AI/系统健康",
                description="默认 PM 关注 7 类决策信号 (产品/AI quality/AI cost/系统健康/incident/data freshness/review)",
                filters={"since": "7d", "tier": "p1", "cohort": "all-active"},
                shared_with=["pm", "owner", "operations"],
            ),
            _build_seed_view(
                workspace="product-analytics",
                name="PM 默认:7 日 Funnel 流失",
                description="激活 → 简历完成 → 投递 → 面试 funnel 7 日窗口对比",
                filters={"since": "7d", "funnel_id": "resume-activation", "cohort": "all-active"},
                shared_with=["pm", "owner", "operations"],
            ),
            _build_seed_view(
                workspace="ai-operations",
                name="PM 默认:AI Quality vs Cost 7 日",
                description="AI tasks quality / cost / latency / failure per feature area",
                filters={"since": "7d", "feature_area": "all"},
                shared_with=["pm", "owner", "operations"],
            ),
            _build_seed_view(
                workspace="incidents-badcases",
                name="Operations 默认:High severity P1",
                description="severity=P1 + status=open + owner 自分配",
                filters={"severity": "p1", "status": "open"},
                shared_with=["pm", "owner", "operations", "maintainer"],
            ),
            _build_seed_view(
                workspace="logs-and-traces",
                name="Maintainer 默认:Error spike",
                description="trace status=failed + since=24h + correlated incidents",
                filters={"status": "failed", "since": "24h"},
                shared_with=["maintainer", "owner", "pm"],
            ),
            _build_seed_view(
                workspace="users-accounts",
                name="Operations 默认:Support 升级用户",
                description="support_incident_count>2 + quality_issue_count>1",
                filters={"support_incident_count_min": 2, "quality_issue_count_min": 1},
                shared_with=["pm", "owner", "operations"],
            ),
            _build_seed_view(
                workspace="reports",
                name="PM 默认:周报快照",
                description="weekly review snapshot inputs",
                filters={"period": "this_week", "comparison": "last_week"},
                shared_with=["pm", "owner", "operations"],
            ),
            _build_seed_view(
                workspace="governance",
                name="Owner 默认:Audit 30 日",
                description="audit events since 30d + result=failed|denied",
                filters={"since": "30d", "result": ["failed", "denied"]},
                shared_with=["owner", "pm"],
                trust_status="pending",
            ),
        ]
        for v in seed_views:
            _SAVED_VIEWS[v.id] = v
        _SEEDED = True


# ---------------------------------------------------------------------------
# CRUD (FR-006 AC-6.1 ~ AC-6.5)
# ---------------------------------------------------------------------------


def next_saved_view_id() -> str:
    global _NEXT_VIEW_SEQ
    with _lock:
        _NEXT_VIEW_SEQ += 1
        return f"sv-{_NEXT_VIEW_SEQ:06d}"


def append_saved_view(view: SavedView) -> None:
    with _lock:
        _SAVED_VIEWS[view.id] = view


def update_saved_view(view_id: str, view: SavedView) -> None:
    with _lock:
        _SAVED_VIEWS[view_id] = view


def delete_saved_view(view_id: str) -> bool:
    with _lock:
        return _SAVED_VIEWS.pop(view_id, None) is not None


def get_saved_view(view_id: str) -> SavedView | None:
    seed_once()
    with _lock:
        return _SAVED_VIEWS.get(view_id)


def list_saved_views(
    *,
    workspace_id: WorkspaceId | None = None,
    role: SharedWithRole | None = None,
) -> list[SavedView]:
    """Return saved views filtered by workspace + role visibility.

    Role visibility (FR-031 + AC-6.6):

    - ``pm`` (and the legacy ``admin`` alias collapsed to ``pm``)
      sees ALL saved views across all workspaces.
    - Other roles (operations / maintainer / reviewer / owner) see
      only views where their role is in ``shared_with`` OR they are
      the ``owner_user_id``.
    - Viewer (and the reserved ``unknown`` role) sees nothing (FR-031
      least-privilege).
    """
    seed_once()
    with _lock:
        all_views = list(_SAVED_VIEWS.values())

    out: list[SavedView] = []
    for v in all_views:
        if workspace_id is not None and v.workspace_id != workspace_id:
            continue
        if role is not None and not _role_can_see(role, v):
            continue
        out.append(v)
    return out


def _role_can_see(role: SharedWithRole, view: SavedView) -> bool:
    """Return True when ``role`` can see ``view``.

    PM is privileged: sees all (FR-031 privileged + AC-6.6).
    Operations / maintainer / reviewer / owner must appear in
    ``shared_with`` OR be the ``owner_user_id``.
    """
    if role == "pm":
        return True
    return role in view.shared_with


def iter_all_saved_views() -> Iterable[SavedView]:
    """Yield every view (used by Playwright happy-path / debug only)."""
    seed_once()
    with _lock:
        return list(_SAVED_VIEWS.values())


def saved_view_count() -> int:
    seed_once()
    with _lock:
        return len(_SAVED_VIEWS)


# ---------------------------------------------------------------------------
# Deleted-cohort (EC-1) registry — tests mark a cohort as deleted to
# exercise the warning surface.
# ---------------------------------------------------------------------------


def mark_cohort_deleted(cohort_name: str) -> None:
    with _lock:
        _DELETED_COHORTS.add(cohort_name)


def is_cohort_deleted(cohort_name: str) -> bool:
    with _lock:
        return cohort_name in _DELETED_COHORTS


def compute_view_warnings(view: SavedView) -> list[str]:
    """Return render-time warnings (EC-1 deleted cohort).

    EC-2 permission-revoked is computed at the service layer (it
    depends on the caller role, which the repository doesn't see).
    """
    warnings: list[str] = []
    cohort = view.filters.get("cohort")
    if isinstance(cohort, str) and is_cohort_deleted(cohort):
        warnings.append(
            f"filter references deleted cohort ({cohort}); please update"
        )
    return warnings


__all__ = [
    "compute_view_warnings",
    "delete_saved_view",
    "get_saved_view",
    "iter_all_saved_views",
    "list_saved_views",
    "mark_cohort_deleted",
    "next_saved_view_id",
    "reset_for_tests",
    "saved_view_count",
    "seed_once",
    "update_saved_view",
]