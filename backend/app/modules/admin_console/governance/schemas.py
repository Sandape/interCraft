"""REQ-044 US6 — Governance / Audit / Export / Retention Pydantic v2 schemas.

Schema surface (FR-031~FR-036 + SC-008/009/010/011 + Edge Cases):

- WorkspaceId — 8 stable top-level workspace names (matches
  :data:`admin-console.schemas` and frontend WorkspaceId union).
- CapabilityToken — 6 capability tokens used by the access
  matrix (read / write / change / export / reveal / audit).
- ConsoleRole — 5 internal roles + reserved 'unknown'.
- AccessMatrixEntry — single (role, workspace, capability)
  tuple (FR-031).
- AccessMatrixResponse — full 5x8x6 grid envelope.
- VisibilityMode — hidden / masked / full field-level (FR-031).
- DataStatus — valid_zero / missing / partial / stale / failed
  (FR-028 + SC-011).
- UserPrivacySafe — privacy-safe user detail; does NOT include
  raw_* fields (FR-032 + SC-010).
- SensitiveTargetType — 5 sensitive target categories.
- RevealRequestCreate — POST reveal-requests body (FR-033).
- RevealRequest — single reveal-request audit row.
- RevealRequestListResponse — list envelope.
- AuditAction — 11-action Literal covering US1+US4+US6
  (FR-034 + SC-009).
- AuditEvent — single audit row (7 fields: actor / timestamp /
  target / action / reason / result / visibility_mode).
- AuditEventListResponse — list envelope.
- ExportFormat — json / csv / markdown (FR-035).
- ExportRequestCreate — POST exports body.
- ExportResponse — POST exports response (6 fields).
- RetentionAction — block / warn / redact (FR-036).
- RetentionPolicy — single retention policy row.
- RetentionPolicyResponse — GET envelope (workspaces list).
- RetentionPolicyUpdate — PUT body.
"""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# FR-031: Workspace + Role + Capability enums
# ---------------------------------------------------------------------------

WorkspaceId = Literal[
    "command-center",
    "product-analytics",
    "ai-operations",
    "incidents-badcases",
    "logs-and-traces",
    "users-accounts",
    "reports",
    "governance",
]

ConsoleRole = Literal[
    "pm",
    "operations",
    "maintainer",
    "reviewer",
    "owner",
    "unknown",
    "admin",
]

CapabilityToken = Literal[
    "READ",
    "WRITE",
    "CHANGE",
    "EXPORT",
    "REVEAL",
    "AUDIT",
]


# ---------------------------------------------------------------------------
# FR-031: Access matrix
# ---------------------------------------------------------------------------


class AccessMatrixEntry(BaseModel):
    """Single (role, workspace, capability) tuple (FR-031 AC-31.1)."""

    model_config = ConfigDict(frozen=False)

    role: ConsoleRole
    workspace: WorkspaceId
    capability: CapabilityToken
    allowed: bool


class AccessMatrixResponse(BaseModel):
    """Full access matrix envelope (FR-031 AC-31.1)."""

    model_config = ConfigDict(frozen=False)

    entries: list[AccessMatrixEntry]
    total: int
    role_count: int
    workspace_count: int
    capability_count: int
    freshness_at: str
    data_status: "DataStatus"
    updated_at: str


# ---------------------------------------------------------------------------
# FR-031 (field-level) + FR-028 + SC-011: Visibility + DataStatus
# ---------------------------------------------------------------------------

VisibilityMode = Literal[
    "hidden",
    "masked",
    "full",
]

DataStatus = Literal[
    "valid_zero",
    "missing",
    "partial",
    "stale",
    "failed",
]


class UserPrivacySafe(BaseModel):
    """Privacy-safe user detail (FR-032 + SC-010)."""

    model_config = ConfigDict(frozen=False)

    user_id: str
    display_name: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None
    journey_summary: Optional[str] = None
    support_incident_count: int = 0
    quality_issue_count: int = 0
    data_status: DataStatus = "valid_zero"
    visibility_mode: VisibilityMode = "masked"
    fetched_at: str


_RAW_FIELD_NAMES: frozenset[str] = frozenset(
    {"raw_resume", "raw_interview_answer", "raw_prompt", "raw_model_output"}
)


def _assert_user_privacy_safe_no_raw() -> None:
    fields = set(UserPrivacySafe.model_fields.keys())
    leaked = fields & set(_RAW_FIELD_NAMES)
    assert not leaked, (
        f"UserPrivacySafe schema leaked raw_* fields: {leaked}. "
        "Remove the field - FR-032 + SC-010 violation."
    )


_assert_user_privacy_safe_no_raw()


SensitiveTargetType = Literal[
    "user_resume",
    "user_interview",
    "ai_prompt",
    "ai_model_output",
    "incident_payload",
]


class RevealRequestCreate(BaseModel):
    """POST /reveal-requests body - FR-033 + AC-33.1."""

    model_config = ConfigDict(frozen=False)

    target_type: SensitiveTargetType
    target_id: str = Field(min_length=1, max_length=200)
    reason: str = Field(
        min_length=20,
        max_length=2000,
        description="Justification for the reveal - must be 20+ chars (FR-033 AC-33.4)",
    )


class RevealRequest(BaseModel):
    """Single reveal-request audit row (FR-033 AC-33.2)."""

    model_config = ConfigDict(frozen=False)

    request_id: str
    actor: str
    target_type: SensitiveTargetType
    target_id: str
    reason: str
    visibility_mode: VisibilityMode
    result: Literal["approved", "denied"]
    audit_event_id: str
    requested_at: str


class RevealRequestListResponse(BaseModel):
    model_config = ConfigDict(frozen=False)

    requests: list[RevealRequest]
    total: int
    data_status: DataStatus


AuditAction = Literal[
    "replay_triggered",
    "diff_computed",
    "tag_added",
    "tag_removed",
    "incident_status_changed",
    "incident_comment_added",
    "badcase_status_changed",
    "badcase_escalated",
    "sensitive_reveal",
    "export",
    "review_snapshot",
]

AuditResult = Literal[
    "approved",
    "denied",
    "executed",
    "failed",
]

AuditTargetKind = Literal[
    "trace",
    "task",
    "diff",
    "incident",
    "badcase",
    "user_resume",
    "user_interview",
    "ai_prompt",
    "ai_model_output",
    "incident_payload",
    "export",
    "snapshot",
    "governance",
]


class AuditEvent(BaseModel):
    """Single audit event row (FR-034 AC-34.2 - 7 fields)."""

    model_config = ConfigDict(frozen=False)

    event_id: str
    actor: str
    timestamp: str
    target_kind: AuditTargetKind
    target_id: Optional[str]
    action: AuditAction
    reason: Optional[str]
    result: AuditResult
    visibility_mode: VisibilityMode


class AuditEventListResponse(BaseModel):
    model_config = ConfigDict(frozen=False)

    events: list[AuditEvent]
    total: int
    data_status: DataStatus


ExportFormat = Literal["json", "csv", "markdown"]


class ExportRequestCreate(BaseModel):
    """POST /exports body (FR-035 AC-35.1)."""

    model_config = ConfigDict(frozen=False)

    workspace: WorkspaceId
    filters: dict[str, Any] = Field(default_factory=dict)
    format: ExportFormat


class ExportResponse(BaseModel):
    """POST /exports response - 6 fields (FR-035 AC-35.1)."""

    model_config = ConfigDict(frozen=False)

    export_id: str
    download_url: str
    expires_at: str
    fields_included: list[str]
    fields_redacted: list[str]
    freshness_warnings: list[str]
    audit_metadata: dict[str, Any]
    format: ExportFormat
    workspace: WorkspaceId
    created_at: str


RetentionAction = Literal["block", "warn", "redact"]


class RetentionPolicy(BaseModel):
    """Single retention policy row (FR-036 AC-36.1)."""

    model_config = ConfigDict(frozen=False)

    workspace_field: WorkspaceId
    retention_days: int = Field(ge=1, le=3650)
    action: RetentionAction
    last_reconciled_at: str
    updated_at: str
    updated_by: str


class RetentionPolicyResponse(BaseModel):
    model_config = ConfigDict(frozen=False)

    policies: list[RetentionPolicy]
    total: int
    data_status: DataStatus


class RetentionPolicyUpdate(BaseModel):
    """PUT /retention-policy body (FR-036 AC-36.2)."""

    model_config = ConfigDict(frozen=False)

    workspace_field: WorkspaceId
    retention_days: int = Field(ge=1, le=3650)
    action: RetentionAction


__all__ = [
    "AUDIT_ACTIONS",
    "AccessMatrixEntry",
    "AccessMatrixResponse",
    "AuditAction",
    "AuditEvent",
    "AuditEventListResponse",
    "AuditResult",
    "AuditTargetKind",
    "CapabilityToken",
    "ConsoleRole",
    "DataStatus",
    "ExportFormat",
    "ExportRequestCreate",
    "ExportResponse",
    "RevealRequest",
    "RevealRequestCreate",
    "RevealRequestListResponse",
    "RetentionAction",
    "RetentionPolicy",
    "RetentionPolicyResponse",
    "RetentionPolicyUpdate",
    "SensitiveTargetType",
    "UserPrivacySafe",
    "VisibilityMode",
    "WorkspaceId",
]


AUDIT_ACTIONS: frozenset[str] = frozenset(
    {
        "replay_triggered",
        "diff_computed",
        "tag_added",
        "tag_removed",
        "incident_status_changed",
        "incident_comment_added",
        "badcase_status_changed",
        "badcase_escalated",
        "sensitive_reveal",
        "export",
        "review_snapshot",
    }
)
