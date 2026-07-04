"""REQ-044 CROSS — Saved Views Pydantic v2 schemas (FR-006).

Schema surface (FR-006 + FR-031 + SC-008 + SC-009 + Edge Cases):

- :data:`SavedViewTrustStatus` — Literal of 3 trust states
  (verified / pending / deprecated). Mirrors
  ``src/types/admin-console.ts:SavedViewTrustStatus``.
- :data:`SharedWithRole` — Literal of the 5 console roles that can
  be added to a saved_view's ``shared_with`` array. Mirrors the
  frontend :data:`ConsoleRole` union minus the reserved ``unknown``
  sentinel.
- :data:`WorkspaceId` — Re-export from US6 governance (single
  source of truth for the 8 workspace names).
- :class:`SavedView` — single saved-view row (12 fields: id, name,
  workspace_id, filters jsonb, owner_user_id, description,
  trust_status, created_at, updated_at, shared_with, version
  optimistic-locking, warnings).
- :class:`SavedViewCreateRequest` — POST body (5 fields: name,
  workspace_id, filters, description, shared_with optional).
- :class:`SavedViewUpdateRequest` — PATCH body (4 fields: name,
  filters, description, shared_with; all optional).
- :class:`SavedViewListResponse` — GET list envelope.
- :class:`SavedViewDetailResponse` — GET single envelope (extends
  SavedView with role-aware warnings: deleted-cohort (EC-1) +
  permission-revoked (EC-2)).
- :class:`SavedViewCreateResponse` — POST response (envelope with
  saved_view_id + audit_event_id).

All SavedView-related enumerations are mirrored verbatim in
``src/types/admin-console.ts`` (cross-team contract per
memory ``feedback_cross_team_contract_l031.md``).
"""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

# Reuse US6 governance WorkspaceId — DO NOT redeclare.
from app.modules.admin_console.governance.schemas import WorkspaceId

# ---------------------------------------------------------------------------
# FR-006 — Saved view enumerations
# ---------------------------------------------------------------------------

#: Saved view trust status — 3 states.
#: Frontend mirror: ``src/types/admin-console.ts:SavedViewTrustStatus``.
SavedViewTrustStatus = Literal["verified", "pending", "deprecated"]

#: Shared-with role list (subset of ConsoleRole minus the reserved
#: ``unknown`` sentinel; admin alias collapses to ``owner`` at the
#: repository layer).
#: Frontend mirror: ``src/types/admin-console.ts:SharedWithRole``.
SharedWithRole = Literal[
    "pm",
    "operations",
    "maintainer",
    "reviewer",
    "owner",
]

#: SavedView filter payload — opaque JSON-shaped dictionary. The
#: schema intentionally keeps this as ``dict[str, Any]`` so the
#: frontend can pass workspace-specific filter shapes (e.g. cohort
#: name + funnel_step + since) without backend coupling.
SavedViewFilters = dict[str, Any]


# ---------------------------------------------------------------------------
# FR-006 — SavedView row + envelope
# ---------------------------------------------------------------------------


class SavedView(BaseModel):
    """Single saved-view row (FR-006 AC-6.1).

    The 12 fields match the GET /saved-views response shape:

    - ``id`` (str) — unique id (``sv-{seq:06d}``).
    - ``name`` (str) — human-readable label.
    - ``workspace_id`` (WorkspaceId) — primary workspace.
    - ``filters`` (dict) — opaque JSON filter state.
    - ``owner_user_id`` (str) — UUID-as-string of the owner.
    - ``description`` (str) — free-text description.
    - ``trust_status`` (SavedViewTrustStatus) — 3-state trust.
    - ``created_at`` (str) — ISO timestamp.
    - ``updated_at`` (str) — ISO timestamp.
    - ``shared_with`` (list[SharedWithRole]) — roles with access
      (empty list + owner-only-implicit → private to owner).
    - ``version`` (int) — optimistic-locking counter (EC-3).
    - ``warnings`` (list[str]) — render-time warnings (deleted
      cohort, permission revoked, etc.).
    """

    model_config = ConfigDict(frozen=False)

    id: str
    name: str
    workspace_id: WorkspaceId
    filters: SavedViewFilters
    owner_user_id: str
    description: str
    trust_status: SavedViewTrustStatus
    created_at: str
    updated_at: str
    shared_with: list[SharedWithRole] = Field(default_factory=list)
    version: int = 1
    warnings: list[str] = Field(default_factory=list)


class SavedViewCreateRequest(BaseModel):
    """POST /saved-views body (FR-006 AC-6.2)."""

    model_config = ConfigDict(frozen=False)

    name: str = Field(min_length=1, max_length=200)
    workspace_id: WorkspaceId
    filters: SavedViewFilters = Field(default_factory=dict)
    description: str = Field(default="", max_length=2000)
    shared_with: list[SharedWithRole] = Field(default_factory=list)
    trust_status: SavedViewTrustStatus = "pending"


class SavedViewUpdateRequest(BaseModel):
    """PATCH /saved-views/{id} body (FR-006 AC-6.4).

    All fields optional so a partial update can be sent. ``version``
    is required for optimistic locking (EC-3): if the current row
    version does not match, the API returns 422 ``version_conflict``.
    """

    model_config = ConfigDict(frozen=False)

    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    filters: Optional[SavedViewFilters] = None
    description: Optional[str] = Field(default=None, max_length=2000)
    shared_with: Optional[list[SharedWithRole]] = None
    trust_status: Optional[SavedViewTrustStatus] = None
    version: Optional[int] = Field(default=None, ge=1)


class SavedViewListResponse(BaseModel):
    """GET /saved-views list envelope (FR-006 AC-6.1)."""

    model_config = ConfigDict(frozen=False)

    views: list[SavedView]
    total: int
    workspace_id: WorkspaceId
    role_view: SharedWithRole
    warnings: list[str] = Field(default_factory=list)


class SavedViewDetailResponse(BaseModel):
    """GET /saved-views/{id} detail envelope (FR-006 AC-6.3).

    Extends SavedView with role-aware warnings (EC-1 deleted-cohort,
    EC-2 permission-revoked) so the frontend can render the
    ``filter references deleted cohort, please update`` or
    ``permission revoked`` banner.
    """

    model_config = ConfigDict(frozen=False)

    view: SavedView
    permission_revoked: bool = False
    warnings: list[str] = Field(default_factory=list)


class SavedViewCreateResponse(BaseModel):
    """POST /saved-views response (FR-006 AC-6.2).

    Includes the new view + the audit event id so the frontend can
    show ``audit_event_id`` in the row's tooltip.
    """

    model_config = ConfigDict(frozen=False)

    view: SavedView
    audit_event_id: str


__all__ = [
    "SavedView",
    "SavedViewCreateRequest",
    "SavedViewCreateResponse",
    "SavedViewDetailResponse",
    "SavedViewFilters",
    "SavedViewListResponse",
    "SavedViewTrustStatus",
    "SavedViewUpdateRequest",
    "SharedWithRole",
    "WorkspaceId",
]