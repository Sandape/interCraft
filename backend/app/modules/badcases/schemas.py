"""Pydantic v2 schemas for badcase records (T042, US9).

Locks the data-model.md §Badcase / §BadcaseReviewAction contract:

- ``Badcase`` — main record. Carries type, severity, status, source,
  reviewer, privacy class, redaction status, run_id/trace_id, closure
  reason + timestamp, and the full ``VersionContext``.
- ``BadcaseReviewAction`` — append-only audit log row for the
  lifecycle (create, classify, close, promote, override, baseline refresh).
- Missing fields default to explicit ``"unknown"`` per SC-010 / FR-038.
- Enums for type/severity/status/source are validated at construction
  (typos fail-fast instead of poisoning the dashboard).

API routes are NOT in this file (those land in T062, US8). This is the
value-object / DTO layer only.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic.alias_generators import to_camel

from app.modules.telemetry_contracts.schemas import VersionContext


# ---------------------------------------------------------------------------
# Enum tables (data-model.md)
# ---------------------------------------------------------------------------

BADCASE_TYPES: tuple[str, ...] = (
    "RESUME_DIAGNOSIS_QUALITY",
    "MOCK_INTERVIEW_QUALITY",
    "AI_RELIABILITY",
    "AI_COST_LATENCY",
    "PRODUCT_FUNNEL_UX",
    "DATA_QUALITY",
    "PRIVACY_REDACTION",
    "EVAL_REGRESSION",
)

BADCASE_SEVERITIES: tuple[str, ...] = ("LOW", "MEDIUM", "HIGH", "CRITICAL")

BADCASE_STATUSES: tuple[str, ...] = (
    "OPEN",
    "TRIAGED",
    "IN_PROGRESS",
    "AWAITING_VALIDATION",
    "CLOSED",
    "REJECTED",
)

BADCASE_SOURCES: tuple[str, ...] = (
    "EVAL_FAILURE",
    "STAGING_TRACE",
    "USER_FEEDBACK",
    "PM_REVIEW",
    "MANUAL_ENTRY",
)

BADCASE_ACTOR_ROLES: tuple[str, ...] = (
    "PM_BUSINESS_OWNER",
    "TECHNICAL_OWNER",
    "BADCASE_REVIEWER",
    "AUTOMATION",
    "USER",
    "UNKNOWN",
)

BADCASE_ACTION_TYPES: tuple[str, ...] = (
    "CREATE",
    "CLASSIFY",
    "PROMOTE_CANDIDATE",
    "APPROVE_PROMOTION",
    "CLOSE",
    "REJECT",
    "OVERRIDE",
    "BASELINE_REFRESH",
)

PRIVACY_CLASSES: tuple[str, ...] = (
    "PUBLIC_METADATA",
    "INTERNAL_METADATA",
    "SENSITIVE_USER_CONTENT",
    "SECRET",
    "REDACTED_SUMMARY",
    "UNKNOWN",
)

REDACTION_STATUSES: tuple[str, ...] = (
    "NOT_REQUIRED",
    "PENDING",
    "PASSED",
    "FAILED",
    "NOT_EXPORTABLE",
    "UNKNOWN",
)


def _normalize_to_unknown(v: Optional[str]) -> str:
    """Empty / None → ``"unknown"`` (SC-010)."""
    if v is None:
        return "unknown"
    if isinstance(v, str) and not v.strip():
        return "unknown"
    return v


# ---------------------------------------------------------------------------
# Badcase
# ---------------------------------------------------------------------------


class Badcase(BaseModel):
    """Human-reviewable quality issue (data-model.md §Badcase).

    US9 (T042): every record carries a full ``VersionContext`` so PM
    panels and badcase filters can roll up by app version / prompt
    fingerprint / rubric version / environment.

    Closure contract (FR-029): a record with ``status in
    {"CLOSED", "REJECTED"}`` MUST have ``closureReason`` and ``closedAt``
    set. A record with any other status MUST NOT have them set. This is
    validated by the model_validator below.
    """

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        alias_generator=to_camel,
    )

    badcase_id: str = Field(
        default_factory=lambda: f"badcase-{uuid4()}",
        description="Stable unique id; auto-generated as badcase-<uuid4>.",
    )
    type: str = Field(default="DATA_QUALITY")
    severity: str = Field(default="MEDIUM")
    status: str = Field(default="OPEN")
    source: str = Field(default="MANUAL_ENTRY")
    reviewer: Optional[str] = Field(default="unknown")
    privacy_class: str = Field(default="UNKNOWN")
    redaction_status: str = Field(default="NOT_REQUIRED")
    eval_lifecycle: Optional[str] = Field(default=None, alias="evalLifecycle")
    export_policy_decision_id: Optional[str] = Field(default=None, alias="exportPolicyDecisionId")
    dataset_version: Optional[str] = Field(default=None, alias="datasetVersion")
    run_id: Optional[UUID] = Field(default=None)
    trace_id: Optional[str] = Field(default=None)
    closure_reason: Optional[str] = Field(default=None)
    closed_at: Optional[datetime] = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.utcnow())
    updated_at: datetime = Field(default_factory=lambda: datetime.utcnow())
    version_context: VersionContext = Field(
        default_factory=lambda: VersionContext.unknown(environment="LOCAL"),
    )

    @field_validator("type")
    @classmethod
    def _valid_type(cls, v: str) -> str:
        if v not in BADCASE_TYPES:
            raise ValueError(f"type must be one of {BADCASE_TYPES}, got {v!r}")
        return v

    @field_validator("severity")
    @classmethod
    def _valid_severity(cls, v: str) -> str:
        if v not in BADCASE_SEVERITIES:
            raise ValueError(
                f"severity must be one of {BADCASE_SEVERITIES}, got {v!r}"
            )
        return v

    @field_validator("status")
    @classmethod
    def _valid_status(cls, v: str) -> str:
        if v not in BADCASE_STATUSES:
            raise ValueError(
                f"status must be one of {BADCASE_STATUSES}, got {v!r}"
            )
        return v

    @field_validator("source")
    @classmethod
    def _valid_source(cls, v: str) -> str:
        if v not in BADCASE_SOURCES:
            raise ValueError(
                f"source must be one of {BADCASE_SOURCES}, got {v!r}"
            )
        return v

    @field_validator("privacy_class")
    @classmethod
    def _valid_privacy_class(cls, v: str) -> str:
        if v not in PRIVACY_CLASSES:
            raise ValueError(
                f"privacy_class must be one of {PRIVACY_CLASSES}, got {v!r}"
            )
        return v

    @field_validator("redaction_status")
    @classmethod
    def _valid_redaction_status(cls, v: str) -> str:
        if v not in REDACTION_STATUSES:
            raise ValueError(
                f"redaction_status must be one of {REDACTION_STATUSES}, got {v!r}"
            )
        return v

    @field_validator("reviewer", "trace_id")
    @classmethod
    def _normalize_optional_str(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        if isinstance(v, str) and not v.strip():
            return "unknown"
        return v

    @model_validator(mode="after")
    def _closure_consistency(self) -> "Badcase":
        """CLOSED/REJECTED must have closureReason + closedAt; others must not."""
        if self.status in {"CLOSED", "REJECTED"}:
            if not self.closure_reason:
                raise ValueError(
                    f"closure_reason is required when status={self.status} (FR-029)"
                )
            if self.closed_at is None:
                raise ValueError(
                    f"closed_at is required when status={self.status} (FR-029)"
                )
        else:
            # If closure fields are set on a non-closed record, that's a
            # bookkeeping error — surface it here rather than letting it
            # silently confuse the dashboard.
            if self.closed_at is not None:
                raise ValueError(
                    f"closed_at must be None when status={self.status}"
                )
        return self

    # ---- factory ----

    @classmethod
    def unknown(cls) -> "Badcase":
        """Build a Badcase with every version field set to ``"unknown"``."""
        return cls(
            type="DATA_QUALITY",
            severity="MEDIUM",
            status="OPEN",
            source="MANUAL_ENTRY",
            reviewer="unknown",
            privacy_class="UNKNOWN",
            redaction_status="NOT_REQUIRED",
            run_id=None,
            trace_id=None,
            closure_reason=None,
            closed_at=None,
            version_context=VersionContext.unknown(environment="LOCAL"),
        )

    # ---- JSON contract ----

    def to_dict(self) -> dict[str, Any]:
        """Serialize to camelCase dict (camelCase per event schema contract)."""
        return self.model_dump(by_alias=True, mode="json")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Badcase":
        """Re-hydrate from a dict. Tolerates snake_case or camelCase keys."""
        return cls.model_validate(data)


# ---------------------------------------------------------------------------
# BadcaseReviewAction
# ---------------------------------------------------------------------------


class BadcaseReviewAction(BaseModel):
    """Append-only audit log of badcase lifecycle actions (data-model.md §BadcaseReviewAction).

    Each row records one lifecycle event (create, classify, close, etc.)
    with the actor role, reason, and evidence reference. Required
    fields per FR-026/FR-029:

    - ``reason`` is required for ``CLOSE``, ``REJECT``, ``OVERRIDE``,
      ``BASELINE_REFRESH``, ``PROMOTE_CANDIDATE``, ``APPROVE_PROMOTION``.
    - ``evidenceRef`` is required for ``CLOSE``, ``OVERRIDE``,
      ``BASELINE_REFRESH``, ``APPROVE_PROMOTION``.
    """

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        alias_generator=to_camel,
    )

    action_type: str = Field(default="CREATE")
    actor_role: str = Field(default="UNKNOWN")
    reason: Optional[str] = Field(default="unknown")
    evidence_ref: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.utcnow())
    version_context: VersionContext = Field(
        default_factory=lambda: VersionContext.unknown(environment="LOCAL"),
    )

    @field_validator("action_type")
    @classmethod
    def _valid_action_type(cls, v: str) -> str:
        if v not in BADCASE_ACTION_TYPES:
            raise ValueError(
                f"action_type must be one of {BADCASE_ACTION_TYPES}, got {v!r}"
            )
        return v

    @field_validator("actor_role")
    @classmethod
    def _valid_actor_role(cls, v: str) -> str:
        if v not in BADCASE_ACTOR_ROLES:
            raise ValueError(
                f"actor_role must be one of {BADCASE_ACTOR_ROLES}, got {v!r}"
            )
        return v

    @field_validator("reason")
    @classmethod
    def _normalize_reason(cls, v: Optional[str]) -> str:
        if v is None:
            return "unknown"
        if isinstance(v, str) and not v.strip():
            return "unknown"
        return v

    @field_validator("evidence_ref")
    @classmethod
    def _normalize_evidence(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        if isinstance(v, str) and not v.strip():
            return None
        return v

    @model_validator(mode="after")
    def _required_fields_for_actions(self) -> "BadcaseReviewAction":
        """Enforce the data-model.md reason/evidence rules."""
        require_reason = {
            "CLOSE",
            "REJECT",
            "OVERRIDE",
            "BASELINE_REFRESH",
            "PROMOTE_CANDIDATE",
            "APPROVE_PROMOTION",
        }
        require_evidence = {
            "CLOSE",
            "OVERRIDE",
            "BASELINE_REFRESH",
            "APPROVE_PROMOTION",
        }
        if self.action_type in require_reason:
            if not self.reason or self.reason == "unknown":
                raise ValueError(
                    f"reason is required when action_type={self.action_type} (FR-029)"
                )
        if self.action_type in require_evidence:
            if not self.evidence_ref:
                raise ValueError(
                    f"evidence_ref is required when action_type={self.action_type} (FR-029)"
                )
        return self

    # ---- JSON contract ----

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(by_alias=True, mode="json")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BadcaseReviewAction":
        return cls.model_validate(data)


__all__ = [
    "BADCASE_ACTION_TYPES",
    "BADCASE_ACTOR_ROLES",
    "BADCASE_SEVERITIES",
    "BADCASE_SOURCES",
    "BADCASE_STATUSES",
    "BADCASE_TYPES",
    "PRIVACY_CLASSES",
    "REDACTION_STATUSES",
    "Badcase",
    "BadcaseReviewAction",
]
