"""REQ-044 US6 — Governance in-memory repository.

Seed strategy (parity with US1/2/3/4):

- :func:`seed_demo_access_matrix` — returns the full 5 role × 8
  workspace × 6 capability grid. Curated per FR-031 least-privilege.
- :func:`seed_demo_retention_policies` — 3 retention policy rows
  (governance, ai-operations, logs-and-traces) covering all 3 actions
  (block / warn / redact).
- :func:`seed_demo_audit_events` — 4 historical audit events so the
  Audit Log viewer has data on first load (zero-state is allowed but
  empty list is unhelpful for tests).
- :func:`seed_demo_reveal_requests` — 2 historical reveal requests
  (1 approved / 1 denied).

In-memory buffers:
- :data:`_AUDIT_LOG` — ring buffer for audit events. Append-only.
  EV-EC-4 self-audit lands here on governance setting change.
- :data:`_REVEAL_REQUESTS` — append-only list.
- :data:`_RETENTION_POLICIES` — ``{workspace_field: RetentionPolicy}``.
- :data:`_RETENTION_CACHE` — ``{workspace_field: [cached_record_ids]}``
  — cleared on PUT retention-policy per EC-3.
- :data:`_EXPORTS` — append-only list (small).

[CROSS-TEAM-DEBT] Real governance DB lands in Phase 2 batch 5. Until
then all governance state is in-process + seed-driven.
"""
from __future__ import annotations

import threading
from datetime import UTC, datetime, timedelta
from typing import Any

from app.modules.admin_console.governance.schemas import (
    AccessMatrixEntry,
    AuditAction,
    AuditEvent,
    AuditResult,
    AuditTargetKind,
    ConsoleRole,
    CapabilityToken,
    DataStatus,
    RevealRequest,
    RetentionAction,
    RetentionPolicy,
    SensitiveTargetType,
    UserPrivacySafe,
    VisibilityMode,
    WorkspaceId,
)

_lock = threading.Lock()

#: Append-only audit log ring buffer.
_AUDIT_LOG: list[AuditEvent] = []
#: Append-only reveal-request buffer.
_REVEAL_REQUESTS: list[RevealRequest] = []
#: Workspace → retention policy map (FROZEN copy seeded once).
_RETENTION_POLICIES: dict[WorkspaceId, RetentionPolicy] = {}
#: Cache invalidation target — cleared on PUT (EC-3).
_RETENTION_CACHE: dict[str, list[str]] = {}
#: Exports append-only.
_EXPORTS: list[dict[str, Any]] = []
#: Sequence counters.
_NEXT_AUDIT_SEQ = 0
_NEXT_REVEAL_SEQ = 0
_NEXT_EXPORT_SEQ = 0
#: Initialised flag.
_SEEDED = False


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
    """Clear all governance buffers. Test helper."""
    global _SEEDED, _NEXT_AUDIT_SEQ, _NEXT_REVEAL_SEQ, _NEXT_EXPORT_SEQ
    with _lock:
        _AUDIT_LOG.clear()
        _REVEAL_REQUESTS.clear()
        _RETENTION_POLICIES.clear()
        _RETENTION_CACHE.clear()
        _EXPORTS.clear()
        _NEXT_AUDIT_SEQ = 0
        _NEXT_REVEAL_SEQ = 0
        _NEXT_EXPORT_SEQ = 0
        _SEEDED = False


# ---------------------------------------------------------------------------
# Access matrix seed (FR-031 / AC-31.1)
# ---------------------------------------------------------------------------

#: 5 role × 8 workspace × 6 capability = 240 entries. We curate via
#: a ``(role, workspace, capability) -> allowed`` table below for
#: least-privilege correctness, then expand into the full grid.
_ACCESS_GRANTS: dict[tuple[str, str, str], bool] = {}
# Build the admin tuple-set explicitly to keep dict literal simple:
_ACCESS_GRANTS.update(
    {
        (("admin", ws, cap), True)
        for ws in [
            "command-center",
            "product-analytics",
            "ai-operations",
            "incidents-badcases",
            "logs-and-traces",
            "users-accounts",
            "reports",
            "governance",
        ]
        for cap in ["READ", "WRITE", "CHANGE", "EXPORT", "REVEAL", "AUDIT"]
    }
)


def _build_access_grants() -> dict[tuple[str, str, str], bool]:
    """Return curated 5x8x6 grants (deny-by-default; explicit grants only)."""
    grants: dict[tuple[str, str, str], bool] = {}

    def grant(role: str, workspace: str, capabilities: list[str]) -> None:
        for cap in capabilities:
            grants[(role, workspace, cap)] = True

    # --- pm: dashboard + analytics + AI ops overview; no write to
    # governance / no reveal / no export by default.
    grant("pm", "command-center", ["READ", "AUDIT"])
    grant("pm", "product-analytics", ["READ", "AUDIT"])
    grant("pm", "ai-operations", ["READ", "AUDIT"])
    grant("pm", "incidents-badcases", ["READ", "CHANGE"])
    grant("pm", "logs-and-traces", ["READ"])
    grant("pm", "users-accounts", ["READ"])
    grant("pm", "reports", ["READ"])
    grant("pm", "governance", ["READ", "AUDIT"])

    # --- operations: triage-focused
    grant("operations", "command-center", ["READ", "AUDIT"])
    grant("operations", "product-analytics", ["READ", "AUDIT"])
    grant("operations", "ai-operations", ["READ", "AUDIT"])
    grant("operations", "incidents-badcases", ["READ", "CHANGE"])
    grant("operations", "logs-and-traces", ["READ"])
    grant("operations", "users-accounts", ["READ"])
    grant("operations", "reports", ["READ"])
    grant("operations", "governance", ["READ", "AUDIT"])

    # --- maintainer: deep debug + export
    grant("maintainer", "command-center", ["READ", "AUDIT"])
    grant("maintainer", "product-analytics", ["READ", "AUDIT"])
    grant("maintainer", "ai-operations", ["READ", "WRITE", "CHANGE", "EXPORT"])
    grant("maintainer", "incidents-badcases", ["READ", "CHANGE"])
    grant("maintainer", "logs-and-traces", ["READ", "WRITE", "CHANGE", "EXPORT"])
    grant("maintainer", "users-accounts", [])
    grant("maintainer", "reports", ["READ", "EXPORT"])
    grant("maintainer", "governance", ["READ", "AUDIT"])

    # --- reviewer: badcase review-only
    grant("reviewer", "command-center", ["READ"])
    grant("reviewer", "product-analytics", ["READ"])
    grant("reviewer", "ai-operations", ["READ", "AUDIT"])
    grant("reviewer", "incidents-badcases", ["READ", "CHANGE"])  # badcase change
    grant("reviewer", "logs-and-traces", [])
    grant("reviewer", "users-accounts", [])
    grant("reviewer", "reports", ["READ"])
    grant("reviewer", "governance", ["READ", "AUDIT"])

    # --- owner (system owner): full grant EXCEPT super-action
    grant("owner", "command-center", ["READ", "WRITE", "CHANGE", "AUDIT"])
    grant("owner", "product-analytics", ["READ", "WRITE", "CHANGE", "AUDIT"])
    grant("owner", "ai-operations", ["READ", "WRITE", "CHANGE", "AUDIT"])
    grant("owner", "incidents-badcases", ["READ", "WRITE", "CHANGE", "AUDIT"])
    grant("owner", "logs-and-traces", ["READ", "WRITE", "CHANGE", "AUDIT"])
    grant("owner", "users-accounts", ["READ", "WRITE", "CHANGE", "AUDIT"])
    grant("owner", "reports", ["READ", "WRITE", "CHANGE", "AUDIT", "EXPORT"])
    grant(
        "owner",
        "governance",
        ["READ", "WRITE", "CHANGE", "AUDIT", "EXPORT", "REVEAL"],
    )

    # admin = legacy alias of owner (mirrors auth.py)
    for key, allowed in list(grants.items()):
        if key[0] == "owner":
            grants[("admin", key[1], key[2])] = allowed

    return grants


_ACCESS_GRANTS_DB: dict[tuple[str, str, str], bool] = _build_access_grants()


def seed_demo_access_matrix() -> list[AccessMatrixEntry]:
    """Return the full 5×8×6 access matrix (FR-031 AC-31.1).

    Always returns 5 * 8 * 6 = 240 entries; ``allowed`` toggled per
    the curated grants. Roles include ``admin`` as the legacy alias
    of ``owner`` per :data:`admin_console.auth._ROLE_GRANTS`.
    """
    entries: list[AccessMatrixEntry] = []
    roles: list[ConsoleRole] = ["pm", "operations", "maintainer", "reviewer", "owner"]
    workspaces: list[WorkspaceId] = [
        "command-center",
        "product-analytics",
        "ai-operations",
        "incidents-badcases",
        "logs-and-traces",
        "users-accounts",
        "reports",
        "governance",
    ]
    capabilities: list[CapabilityToken] = [
        "READ",
        "WRITE",
        "CHANGE",
        "EXPORT",
        "REVEAL",
        "AUDIT",
    ]
    for role in roles:
        for workspace in workspaces:
            for capability in capabilities:
                allowed = _ACCESS_GRANTS_DB.get(
                    (role, workspace, capability), False
                )
                entries.append(
                    AccessMatrixEntry(
                        role=role,
                        workspace=workspace,
                        capability=capability,
                        allowed=allowed,
                    )
                )
    return entries


# ---------------------------------------------------------------------------
# Retention policy seed (FR-036)
# ---------------------------------------------------------------------------


def seed_demo_retention_policies() -> dict[WorkspaceId, RetentionPolicy]:
    """Seed 3 retention policies spanning all 3 actions."""
    ts = _earlier_iso(days=2)
    return {
        "governance": RetentionPolicy(
            workspace_field="governance",
            retention_days=365,
            action="warn",
            last_reconciled_at=ts,
            updated_at=ts,
            updated_by="@user:system",
        ),
        "ai-operations": RetentionPolicy(
            workspace_field="ai-operations",
            retention_days=90,
            action="redact",
            last_reconciled_at=ts,
            updated_at=ts,
            updated_by="@user:system",
        ),
        "logs-and-traces": RetentionPolicy(
            workspace_field="logs-and-traces",
            retention_days=30,
            action="block",
            last_reconciled_at=ts,
            updated_at=ts,
            updated_by="@user:system",
        ),
    }


# ---------------------------------------------------------------------------
# Audit event helpers (in-memory buffer)
# ---------------------------------------------------------------------------


def next_audit_event_id() -> str:
    """Return the next audit event id (Phase 1; Phase 2 batch 5 swaps for UUID)."""
    global _NEXT_AUDIT_SEQ
    with _lock:
        _NEXT_AUDIT_SEQ += 1
        return f"audit-{_NEXT_AUDIT_SEQ:06d}"


def next_reveal_request_id() -> str:
    global _NEXT_REVEAL_SEQ
    with _lock:
        _NEXT_REVEAL_SEQ += 1
        return f"rev-{_NEXT_REVEAL_SEQ:06d}"


def next_export_id() -> str:
    global _NEXT_EXPORT_SEQ
    with _lock:
        _NEXT_EXPORT_SEQ += 1
        return f"exp-{_NEXT_EXPORT_SEQ:06d}"


def append_audit_event(event: AuditEvent) -> None:
    """Append an audit event to the in-memory buffer.

    Real DB persistence is a no-op for the 3 US6 actions until
    Phase 2 batch 5 widens the ``admin_audit_log`` CHECK constraint.
    """
    with _lock:
        _AUDIT_LOG.append(event)


def list_audit_events(
    *, actor: str | None = None, action: AuditAction | None = None
) -> list[AuditEvent]:
    """Return audit events optionally filtered by actor / action."""
    with _lock:
        out = list(_AUDIT_LOG)
    if actor:
        out = [e for e in out if e.actor == actor]
    if action:
        out = [e for e in out if e.action == action]
    return out


def audit_log_size() -> int:
    """Return the size of the in-memory audit buffer. Test helper."""
    with _lock:
        return len(_AUDIT_LOG)


# ---------------------------------------------------------------------------
# Reveal request buffer (FR-033)
# ---------------------------------------------------------------------------


def append_reveal_request(req: RevealRequest) -> None:
    with _lock:
        _REVEAL_REQUESTS.append(req)


def list_reveal_requests() -> list[RevealRequest]:
    with _lock:
        return list(_REVEAL_REQUESTS)


# ---------------------------------------------------------------------------
# Retention policy store (FR-036)
# ---------------------------------------------------------------------------


def seed_once() -> None:
    """Seed retention policies once on first import. Idempotent."""
    global _SEEDED
    with _lock:
        if _SEEDED:
            return
        _RETENTION_POLICIES.update(seed_demo_retention_policies())
        _SEEDED = True


def get_retention_policy(workspace_field: WorkspaceId) -> RetentionPolicy | None:
    seed_once()
    with _lock:
        return _RETENTION_POLICIES.get(workspace_field)


def list_retention_policies() -> list[RetentionPolicy]:
    seed_once()
    with _lock:
        return list(_RETENTION_POLICIES.values())


def upsert_retention_policy(policy: RetentionPolicy) -> None:
    """Update + clear the cache for ``workspace_field`` (EC-3)."""
    with _lock:
        _RETENTION_POLICIES[policy.workspace_field] = policy
        _RETENTION_CACHE.pop(policy.workspace_field, None)


def retention_cache_size() -> int:
    """Return the size of the cache (EC-3 invalidation assertion)."""
    with _lock:
        return sum(len(v) for v in _RETENTION_CACHE.values())


def prime_retention_cache(workspace_field: WorkspaceId, keys: list[str]) -> None:
    """Inject cached entries for EC-3 invalidation test."""
    with _lock:
        _RETENTION_CACHE[workspace_field] = list(keys)


# ---------------------------------------------------------------------------
# Export buffer (FR-035)
# ---------------------------------------------------------------------------


def append_export(record: dict[str, Any]) -> None:
    with _lock:
        _EXPORTS.append(record)


def get_export(export_id: str) -> dict[str, Any] | None:
    with _lock:
        for rec in _EXPORTS:
            if rec["export_id"] == export_id:
                return rec
    return None


# ---------------------------------------------------------------------------
# UserPrivacySafe mask helper (FR-032 / AC-32.3)
# ---------------------------------------------------------------------------

REDACTED_PLACEHOLDER: str = "***REDACTED***"


def mask_sensitive_field(_field_name: str, value: Any) -> Any:
    """Mask any sensitive payload to the REDACTED placeholder.

    Helper for service-layer: any field passed through
    ``apply_user_privacy_safe`` (or via the redact-on-export path)
    MUST yield ``REDACTED_PLACEHOLDER`` unless visibility_mode == 'full'.
    """
    if value is None:
        return None
    if isinstance(value, str) and len(value) == 0:
        return ""
    return REDACTED_PLACEHOLDER


def build_privacy_safe_user(
    user_id: str,
    *,
    display_name: str | None = None,
    email: str | None = None,
    role: str | None = None,
    journey_summary: str | None = None,
    support_incident_count: int = 0,
    quality_issue_count: int = 0,
    data_status: DataStatus = "valid_zero",
    visibility_mode: VisibilityMode = "masked",
) -> UserPrivacySafe:
    """Return a privacy-safe UserPrivacySafe (no raw_*)."""
    return UserPrivacySafe(
        user_id=user_id,
        display_name=display_name,
        email=email,
        role=role,
        journey_summary=journey_summary,
        support_incident_count=support_incident_count,
        quality_issue_count=quality_issue_count,
        data_status=data_status,
        visibility_mode=visibility_mode,
        fetched_at=_now_iso(),
    )


__all__ = [
    "REDACTED_PLACEHOLDER",
    "_RAW_FIELD_NAMES",
    "append_audit_event",
    "append_export",
    "append_reveal_request",
    "audit_log_size",
    "build_privacy_safe_user",
    "get_export",
    "get_retention_policy",
    "list_audit_events",
    "list_reveal_requests",
    "list_retention_policies",
    "mask_sensitive_field",
    "next_audit_event_id",
    "next_export_id",
    "next_reveal_request_id",
    "prime_retention_cache",
    "reset_for_tests",
    "retention_cache_size",
    "seed_demo_access_matrix",
    "seed_demo_retention_policies",
    "seed_once",
    "upsert_retention_policy",
]
