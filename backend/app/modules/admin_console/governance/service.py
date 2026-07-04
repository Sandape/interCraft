"""REQ-044 US6 — Governance service layer (FR-031~FR-036 + Edge Cases).

Pure orchestration: returns access matrix, reveal-request, audit event,
export, retention policy data + applies retention filtering.

Functions:

- :func:`get_access_matrix` — full RBAC matrix (FR-031, AC-31.1).
- :func:`create_reveal_request` — POST /reveal-requests (FR-033).
- :func:`list_reveal_requests` — GET /reveal-requests (FR-033).
- :func:`list_audit_events` — GET /audit-events (FR-034).
- :func:`create_export` — POST /exports (FR-035).
- :func:`list_retention_policies` — GET /retention-policy (FR-036).
- :func:`update_retention_policy` — PUT /retention-policy + cache
  invalidation (EC-3) + self-audit (EC-4) (FR-036).
- :func:`apply_retention_filter` — return ``expired`` tag if record
  has aged beyond ``retention_days`` (FR-036 + EC-2).

Audit event write order is locked by AC-33.5: the helper
:func:`_write_audit_event` is invoked BEFORE any
sensitive-payload-returning function returns to the caller. EC-1
("reveal denied after trace open") is handled via the API layer
returning ``audit_event_id`` so the frontend can close the trace
drawer.

[CROSS-TEAM-DEBT] Real governance DB lands in Phase 2 batch 5 with
DB-backed RBAC + audit log + retention scheduler. Until then all
state is in-process + seed-driven (see ``repository.py``).
"""
from __future__ import annotations

import threading
from datetime import UTC, datetime, timedelta
from typing import Any

from app.modules.admin_console.governance import repository
from app.modules.admin_console.governance.schemas import (
    AccessMatrixEntry,
    AccessMatrixResponse,
    AuditAction,
    AuditEvent,
    AuditEventListResponse,
    AuditResult,
    AuditTargetKind,
    ConsoleRole,
    DataStatus,
    ExportFormat,
    ExportRequestCreate,
    ExportResponse,
    RevealRequest,
    RevealRequestCreate,
    RevealRequestListResponse,
    RetentionAction,
    RetentionPolicy,
    RetentionPolicyResponse,
    RetentionPolicyUpdate,
    SensitiveTargetType,
    UserPrivacySafe,
    VisibilityMode,
    WorkspaceId,
)

_lock = threading.Lock()


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


# ---------------------------------------------------------------------------
# Access matrix (FR-031)
# ---------------------------------------------------------------------------


def get_access_matrix() -> AccessMatrixResponse:
    """Return the 5x8x6 access matrix."""
    entries = repository.seed_demo_access_matrix()
    return AccessMatrixResponse(
        entries=entries,
        total=len(entries),
        role_count=5,
        workspace_count=8,
        capability_count=6,
        freshness_at=_now_iso(),
        data_status="valid_zero",
        updated_at=_earlier_iso(days=2),
    )


def role_workspace_allowed(role: ConsoleRole, workspace: WorkspaceId) -> bool:
    """Return True if role has READ on workspace (RBAC sidebar gating)."""
    entries = repository.seed_demo_access_matrix()
    for entry in entries:
        if entry.role == role and entry.workspace == workspace and entry.capability == "READ":
            return entry.allowed
    return False


# ---------------------------------------------------------------------------
# Reveal request (FR-033)
# ---------------------------------------------------------------------------

MIN_REASON_LENGTH = 20


def _audit_event_id_for_request() -> str:
    return repository.next_audit_event_id()


def create_reveal_request(
    body: RevealRequestCreate,
    actor: str,
    *,
    has_reveal_capability: bool = True,
) -> RevealRequest:
    """Create a reveal request + write audit event FIRST (AC-33.5).

    Validates: ``reason`` length ≥ :data:`MIN_REASON_LENGTH`. The
    audit event is written BEFORE the request is returned so the
    caller can prove the audit-trail invariant (FR-033 + EC-1).
    """
    if len(body.reason.strip()) < MIN_REASON_LENGTH:
        raise ValueError(
            f"reveal reason must be ≥ {MIN_REASON_LENGTH} chars (FR-033 AC-33.4)"
        )

    # Approve / deny based on reveal capability grant.
    approved = has_reveal_capability
    visibility: VisibilityMode = "full" if approved else "hidden"

    # Audit event written BEFORE returning request (AC-33.5).
    audit_id = _audit_event_id_for_request()
    audit = AuditEvent(
        event_id=audit_id,
        actor=actor,
        timestamp=_now_iso(),
        target_kind=_sensitive_to_audit_target(body.target_type),
        target_id=body.target_id,
        action="sensitive_reveal",
        reason=body.reason,
        result="approved" if approved else "denied",
        visibility_mode=visibility,
    )
    repository.append_audit_event(audit)

    request_id = repository.next_reveal_request_id()
    req = RevealRequest(
        request_id=request_id,
        actor=actor,
        target_type=body.target_type,
        target_id=body.target_id,
        reason=body.reason,
        visibility_mode=visibility,
        result="approved" if approved else "denied",
        audit_event_id=audit_id,
        requested_at=_now_iso(),
    )
    repository.append_reveal_request(req)
    return req


def _sensitive_to_audit_target(t: SensitiveTargetType) -> AuditTargetKind:
    """Map a SensitiveTargetType to its AuditTargetKind mirror (FR-034)."""
    return {
        "user_resume": "user_resume",
        "user_interview": "user_interview",
        "ai_prompt": "ai_prompt",
        "ai_model_output": "ai_model_output",
        "incident_payload": "incident_payload",
    }[t]


def list_reveal_requests() -> RevealRequestListResponse:
    """Return the reveal-request audit buffer (FR-033 AC-33.2)."""
    items = repository.list_reveal_requests()
    return RevealRequestListResponse(
        requests=items,
        total=len(items),
        data_status="valid_zero" if not items else "valid_zero",
    )


# ---------------------------------------------------------------------------
# Audit log (FR-034)
# ---------------------------------------------------------------------------


def list_audit_events(
    *,
    actor: str | None = None,
    action: AuditAction | None = None,
) -> AuditEventListResponse:
    """Return the audit-event buffer."""
    items = repository.list_audit_events(actor=actor, action=action)
    return AuditEventListResponse(
        events=items,
        total=len(items),
        data_status="valid_zero",
    )


# ---------------------------------------------------------------------------
# Export (FR-035)
# ---------------------------------------------------------------------------

EXPORT_FIELDS_INCLUDED: list[str] = [
    # whitelist — approved fields per FR-035
    "user_id",
    "display_name",
    "incident_id",
    "severity",
    "status",
    "first_seen_at",
    "last_seen_at",
    "trend",
    "ai_task_id",
    "eval_verdict",
    "audit_metadata",
    "filters",
    "freshness",
]

EXPORT_FIELDS_REDACTED: list[str] = [
    # FR-032 raw_* enforcement — must NEVER appear in export payload
    "raw_resume",
    "raw_interview_answer",
    "raw_prompt",
    "raw_model_output",
]


def _export_field_whitelist(workspace: WorkspaceId) -> list[str]:
    """Return the per-workspace approved field list.

    All workspaces share the same base whitelist; workspace-specific
    extensions land in Phase 2 batch 5.
    """
    return list(EXPORT_FIELDS_INCLUDED)


def _expired_record_ids_for_period(filters: dict[str, Any]) -> list[str]:
    """Return synthetic expired record ids for EC-2.

    A real implementation would query the audit / retention tables;
    for US6 we surface a deterministic marker from the filters dict.
    """
    expired = filters.get("expired_record_ids")
    if isinstance(expired, list):
        return [str(x) for x in expired]
    return []


def create_export(
    body: ExportRequestCreate,
    actor: str,
) -> ExportResponse:
    """Create an export + audit event (FR-035 AC-35.1)."""
    # Detect EC-2: expired records in the requested period
    expired_record_ids = _expired_record_ids_for_period(body.filters)
    if expired_record_ids:
        # Per AC-35.5 + EC-2: write audit event for the denied export
        audit_id = repository.next_audit_event_id()
        audit = AuditEvent(
            event_id=audit_id,
            actor=actor,
            timestamp=_now_iso(),
            target_kind="export",
            target_id=None,
            action="export",
            reason="export blocked: period contains expired records (EC-2)",
            result="denied",
            visibility_mode="hidden",
        )
        repository.append_audit_event(audit)
        # Raise so the API layer returns 422 with the expired list.
        raise ExportBlockedError(expired_record_ids)

    fields_included = _export_field_whitelist(body.workspace)
    freshness_warnings: list[str] = []
    if body.filters.get("period") == "stale_window":
        freshness_warnings.append(
            "selected period overlaps stale data window (>30d); recompute recommended"
        )

    export_id = repository.next_export_id()
    created_at = _now_iso()
    expires_at = (datetime.now(UTC) + timedelta(hours=24)).replace(
        microsecond=0
    ).isoformat().replace("+00:00", "Z")

    audit_metadata = {
        "actor": actor,
        "timestamp": created_at,
        "filters": body.filters,
        "fields_included": fields_included,
        "fields_redacted": EXPORT_FIELDS_REDACTED,
        "redaction_state": "applied",
        "audit_event_ids": [repository.next_audit_event_id()],
    }
    # Write the actual export audit event FIRST (AC-35.5).
    audit = AuditEvent(
        event_id=audit_metadata["audit_event_ids"][0],
        actor=actor,
        timestamp=created_at,
        target_kind="export",
        target_id=export_id,
        action="export",
        reason=f"export generated for workspace={body.workspace} format={body.format}",
        result="executed",
        visibility_mode="full",
    )
    repository.append_audit_event(audit)

    repository.append_export(
        {
            "export_id": export_id,
            "workspace": body.workspace,
            "format": body.format,
            "filters": body.filters,
            "fields_included": fields_included,
            "fields_redacted": list(EXPORT_FIELDS_REDACTED),
            "freshness_warnings": freshness_warnings,
            "audit_metadata": audit_metadata,
            "created_at": created_at,
        }
    )
    return ExportResponse(
        export_id=export_id,
        download_url=f"/api/v1/admin-console/governance/exports/{export_id}/download",
        expires_at=expires_at,
        fields_included=fields_included,
        fields_redacted=list(EXPORT_FIELDS_REDACTED),
        freshness_warnings=freshness_warnings,
        audit_metadata=audit_metadata,
        format=body.format,
        workspace=body.workspace,
        created_at=created_at,
    )


class ExportBlockedError(Exception):
    """Raised when an export period contains expired records (EC-2)."""

    def __init__(self, expired_record_ids: list[str]):
        self.expired_record_ids = expired_record_ids
        super().__init__(f"export blocked: {len(expired_record_ids)} expired records")


# ---------------------------------------------------------------------------
# Retention (FR-036)
# ---------------------------------------------------------------------------


def list_retention_policies() -> RetentionPolicyResponse:
    """Return all retention policies."""
    items = repository.list_retention_policies()
    return RetentionPolicyResponse(
        policies=items,
        total=len(items),
        data_status="valid_zero" if not items else "valid_zero",
    )


def get_retention_policy(workspace_field: WorkspaceId) -> RetentionPolicy | None:
    return repository.get_retention_policy(workspace_field)


def update_retention_policy(
    body: RetentionPolicyUpdate,
    actor: str,
) -> RetentionPolicy:
    """Update retention + invalidate cache (EC-3) + self-audit (EC-4 / FR-034).

    Sequence:
    1. Upsert policy (repository layer clears _RETENTION_CACHE for that
       workspace_field — EC-3).
    2. Write a ``review_snapshot`` audit event with target_kind =
       ``governance`` (US6 self-audit per FR-034).
    """
    policy = RetentionPolicy(
        workspace_field=body.workspace_field,
        retention_days=body.retention_days,
        action=body.action,
        last_reconciled_at=_now_iso(),
        updated_at=_now_iso(),
        updated_by=actor,
    )
    repository.upsert_retention_policy(policy)

    # EC-4 self-audit
    audit_id = repository.next_audit_event_id()
    audit = AuditEvent(
        event_id=audit_id,
        actor=actor,
        timestamp=_now_iso(),
        target_kind="governance",
        target_id=body.workspace_field,
        action="review_snapshot",
        reason=(
            f"retention policy update: {body.workspace_field} "
            f"→ {body.retention_days}d / {body.action}"
        ),
        result="executed",
        visibility_mode="full",
    )
    repository.append_audit_event(audit)
    return policy


def apply_retention_filter(
    workspace_field: WorkspaceId,
    record_id: str,
    record_age_days: int,
) -> dict[str, Any]:
    """Return ``{value: None, expired: True/False, action: RetentionAction}``.

    :func:`apply_retention_filter` is invoked by service-layer callers
    that need to gate a record behind the per-workspace retention rule
    (FR-036 + SC-11).
    """
    policy = repository.get_retention_policy(workspace_field)
    if policy is None:
        return {"value": None, "expired": False, "action": None, "policy": None}
    expired = record_age_days > policy.retention_days
    return {
        "value": None if expired else "available",
        "expired": expired,
        "action": policy.action,
        "policy": policy.workspace_field,
    }


# ---------------------------------------------------------------------------
# User privacy safe (FR-032)
# ---------------------------------------------------------------------------

_KNOWN_RAW_FIELDS: frozenset[str] = frozenset(
    {"raw_resume", "raw_interview_answer", "raw_prompt", "raw_model_output"}
)


def assert_user_privacy_safe_no_raw(payload: dict[str, Any]) -> None:
    """Service-layer guard (defence-in-depth; schema also locks).

    Raises ValueError if the payload contains any raw_* key.
    """
    leaked = set(payload.keys()) & _KNOWN_RAW_FIELDS
    if leaked:
        raise ValueError(
            f"UserPrivacySafe payload leaked raw_* fields: {leaked}. "
            "FR-032 + SC-010 violation."
        )


def build_privacy_safe_user_safe(
    user_id: str,
    *,
    display_name: str | None = None,
    email: str | None = None,
    role: str | None = None,
    journey_summary: str | None = None,
    support_incident_count: int = 0,
    quality_issue_count: int = 0,
    visibility_mode: VisibilityMode = "masked",
    data_status: DataStatus = "valid_zero",
) -> UserPrivacySafe:
    """Return a UserPrivacySafe record.

    Companion to :func:`repository.build_privacy_safe_user` with
    explicit field allow-list (defence-in-depth: omitted fields
    cannot leak raw_*).
    """
    return repository.build_privacy_safe_user(
        user_id=user_id,
        display_name=display_name,
        email=email,
        role=role,
        journey_summary=journey_summary,
        support_incident_count=support_incident_count,
        quality_issue_count=quality_issue_count,
        data_status=data_status,
        visibility_mode=visibility_mode,
    )


__all__ = [
    "EXPORT_FIELDS_INCLUDED",
    "EXPORT_FIELDS_REDACTED",
    "ExportBlockedError",
    "MIN_REASON_LENGTH",
    "apply_retention_filter",
    "assert_user_privacy_safe_no_raw",
    "build_privacy_safe_user_safe",
    "create_export",
    "create_reveal_request",
    "get_access_matrix",
    "get_retention_policy",
    "list_audit_events",
    "list_reveal_requests",
    "list_retention_policies",
    "role_workspace_allowed",
    "update_retention_policy",
]
