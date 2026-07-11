"""REQ-044 US4 — Incidents & Badcases Pydantic v2 schemas (FR-021~FR-023).

Schema surface:

- :class:`IncidentSeverity` — Literal of the 4 FR-021 severity bands
  (P0 / P1 / P2 / P3).
- :class:`IncidentStatus` — Literal of the 4 FR-021 status values
  (open / investigating / resolved / postmortem).
- :class:`IncidentTrend` — Literal of the 3 FR-021 trend directions
  (rising / stable / declining).
- :class:`EvidenceLinkType` — Literal of the 8 FR-022 evidence link types
  (product_metric / user_impact / ai_task / eval_case / log / trace /
  release / comment).
- :class:`EvidenceLink` — single evidence link with type + reference_id
  + label + href + privacy_class.
- :class:`Incident` — single incident row (FR-021 + EC-1/2/3 fields).
- :class:`IncidentListResponse` — list envelope + counts.
- :class:`EvidenceLinkListResponse` — list of evidence links.
- :class:`CommentCreateRequest` — POST body for adding a comment.
- :class:`Comment` — single comment row.
- :class:`CommentListResponse` — list of comments.
- :class:`StatusChangeRequest` — PATCH body for status change.
- :class:`AuditTrailEntry` — single audit row (EC-4: actor / timestamp /
  reason / before_state / after_state).
- :class:`AuditTrail` — list of audit entries.
- :class:`BadcaseStatus` — Literal of the 4 FR-023 status values
  (open / reviewing / closed / escalated).
- :class:`BadcasePrivacyClass` — Literal of the 3 privacy classes
  (public / internal / restricted).
- :class:`Badcase` — single badcase row (FR-023).
- :class:`BadcaseListResponse` — list envelope.
- :class:`BadcaseEscalateResponse` — POST escalate response with new
  incident_id.

Validation invariants locked by AC matrix:

- ``severity`` MUST be one of P0/P1/P2/P3.
- ``status`` MUST be one of open/investigating/resolved/postmortem.
- ``trend`` MUST be one of rising/stable/declining.
- ``evidence_link_type`` MUST be one of 8 FR-022 types.
- ``badcase_status`` MUST be one of open/reviewing/closed/escalated.
- ``badcase_privacy_class`` MUST be one of public/internal/restricted.
- AuditTrail entry MUST carry actor + timestamp + reason + before_state +
  after_state (EC-4).
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# FR-021: Incident enums
# ---------------------------------------------------------------------------


IncidentSeverity = Literal[
    "P0",  # critical, business-blocking
    "P1",  # high, significant impact
    "P2",  # medium, partial impact
    "P3",  # low, minor / cosmetic
]

IncidentStatus = Literal[
    "open",  # newly raised, not yet investigated
    "investigating",  # owner assigned, work in progress
    "resolved",  # fix shipped, awaiting postmortem
    "postmortem",  # retrospective complete
]

IncidentTrend = Literal[
    "rising",  # worsening — frequency or impact increasing
    "stable",  # unchanged
    "declining",  # improving
]


# ---------------------------------------------------------------------------
# FR-022: Evidence link enum
# ---------------------------------------------------------------------------


EvidenceLinkType = Literal[
    "product_metric",  # dashboard / funnel / cohort / feature adoption metric
    "user_impact",    # privacy-safe user lookup (US2)
    "ai_task",        # AI invocation record (US3 quality issue link)
    "eval_case",      # eval run / rubric verdict (US3 eval + badcase)
    "log",            # log event (US5)
    "trace",          # trace / span (US5)
    "release",        # release / version / experiment (US6 + US3)
    "comment",        # inline comment / note
]


# ---------------------------------------------------------------------------
# FR-022: EvidenceLink
# ---------------------------------------------------------------------------


class EvidenceLink(BaseModel):
    """A single evidence link attached to an incident or badcase (FR-022).

    The 8-type ``type`` Literal mirrors the 8 FR-022 evidence surfaces
    (product metrics / user impact / AI tasks / eval cases / logs /
    traces / releases / comments). ``reference_id`` is the canonical
    cross-workspace id (e.g. ``"metric:funnel.registered_to_first_interview"``
    or ``"task:019ec1be-..."``).
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    type: EvidenceLinkType
    reference_id: str = Field(..., min_length=1, max_length=128)
    label: str = Field(..., min_length=1, max_length=160)
    href: str = Field(..., min_length=1, max_length=512)
    privacy_class: Literal["public", "internal", "restricted"] = "internal"
    summary: Optional[str] = Field(default=None, max_length=512)


# ---------------------------------------------------------------------------
# FR-021 + EC-1/2/3: Incident
# ---------------------------------------------------------------------------


class Incident(BaseModel):
    """A single incident row (FR-021 + Edge Cases EC-1/2/3).

    FR-021 mandated fields (10):
    - ``id``
    - ``title``
    - ``severity`` (P0/P1/P2/P3)
    - ``status`` (open/investigating/resolved/postmortem)
    - ``owner``
    - ``affected_feature_area``
    - ``affected_journey_step``
    - ``first_seen_at``
    - ``last_seen_at``
    - ``trend`` (rising/stable/declining)

    Edge case fields:

    - ``candidate`` (EC-1) — True iff this is a low-confidence anomaly
      that has NOT been merged into the confirmed incident list. The
      frontend MUST display a "candidate" label and not surface it
      alongside confirmed incidents.
    - ``common_root_cause`` (EC-2) — non-empty when this incident
      shares a technical root cause with one or more other incidents
      (different journey steps but same root cause).
    - ``linked_incident_ids`` (EC-2) — cross-link to sibling incidents
      sharing ``common_root_cause``.
    - ``ingestion_delayed`` (EC-3) — True when data ingestion lag
      caused the incident (vs. real product behavior). Frontend MUST
      surface an "ingestion delayed" label.
    - ``freshness_at`` — ISO 8601 timestamp OR literal "unknown".
    - ``affected_count`` — number of users / tasks / events affected.
    - ``audit_trail`` — list of audit entries (EC-4).
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: str = Field(..., min_length=1, max_length=64)
    title: str = Field(..., min_length=1, max_length=200)
    severity: IncidentSeverity
    status: IncidentStatus
    owner: str = Field(..., min_length=1, max_length=128)
    affected_feature_area: str = Field(..., min_length=1, max_length=64)
    affected_journey_step: str = Field(..., min_length=1, max_length=64)
    first_seen_at: str = Field(..., min_length=1, max_length=64)
    last_seen_at: str = Field(..., min_length=1, max_length=64)
    trend: IncidentTrend
    candidate: bool = Field(
        default=False,
        description="EC-1: True if this is a low-confidence anomaly not yet merged into confirmed incidents.",
    )
    common_root_cause: Optional[str] = Field(
        default=None, max_length=160,
        description="EC-2: human-readable root-cause label when this incident shares a root cause with siblings.",
    )
    linked_incident_ids: list[str] = Field(
        default_factory=list,
        description="EC-2: cross-link to sibling incidents sharing common_root_cause.",
    )
    ingestion_delayed: bool = Field(
        default=False,
        description="EC-3: True when data ingestion lag caused the incident.",
    )
    freshness_at: str = Field(default="unknown", max_length=64)
    affected_count: int = Field(default=0, ge=0)
    description: str = Field(default="", max_length=1024)
    audit_trail: list["AuditTrailEntry"] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# FR-021: Incident list envelope
# ---------------------------------------------------------------------------


class IncidentListResponse(BaseModel):
    """Top-level envelope for GET /incidents."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    incidents: list[Incident] = Field(default_factory=list)
    total: int = Field(ge=0)
    confirmed_count: int = Field(
        default=0,
        ge=0,
        description="Count of candidate=False incidents; drives the FR-021 + EC-1 separation.",
    )
    candidate_count: int = Field(
        default=0,
        ge=0,
        description="Count of candidate=True incidents; the EC-1 separation count.",
    )
    freshness_at: str = Field(default="unknown", max_length=64)


# ---------------------------------------------------------------------------
# FR-022: Evidence list envelope
# ---------------------------------------------------------------------------


class EvidenceLinkListResponse(BaseModel):
    """Top-level envelope for GET /incidents/{id}/evidence."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    incident_id: str = Field(..., min_length=1, max_length=64)
    evidence_links: list[EvidenceLink] = Field(default_factory=list)
    total: int = Field(ge=0)
    # 8-type coverage map (AC-22.1): type → count. Lets the frontend
    # render 8 sections with empty-state badges.
    coverage: dict[str, int] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# FR-022: Comments
# ---------------------------------------------------------------------------


class CommentCreateRequest(BaseModel):
    """POST body for adding a comment to an incident."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    body: str = Field(..., min_length=1, max_length=2048)
    reason: Optional[str] = Field(default=None, max_length=256)


class Comment(BaseModel):
    """A single comment on an incident."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: str = Field(..., min_length=1, max_length=64)
    incident_id: str = Field(..., min_length=1, max_length=64)
    actor: str = Field(..., min_length=1, max_length=128)
    body: str = Field(..., min_length=1, max_length=2048)
    reason: Optional[str] = Field(default=None, max_length=256)
    created_at: str = Field(..., min_length=1, max_length=64)


class CommentListResponse(BaseModel):
    """Top-level envelope for GET /incidents/{id}/comments."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    incident_id: str = Field(..., min_length=1, max_length=64)
    comments: list[Comment] = Field(default_factory=list)
    total: int = Field(ge=0)


# ---------------------------------------------------------------------------
# EC-4: Status change + audit trail
# ---------------------------------------------------------------------------


class StatusChangeRequest(BaseModel):
    """PATCH body for /incidents/{id}/status (EC-4)."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    new_status: IncidentStatus
    new_owner: Optional[str] = Field(default=None, max_length=128)
    reason: str = Field(..., min_length=1, max_length=512)


class AuditTrailEntry(BaseModel):
    """A single audit-trail row (EC-4).

    The 5 EC-4 fields are all mandatory:

    - ``actor`` — who performed the change (user id or role handle).
    - ``timestamp`` — ISO 8601 timestamp.
    - ``reason`` — human-readable rationale.
    - ``before_state`` — snapshot before the change.
    - ``after_state`` — snapshot after the change.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    actor: str = Field(..., min_length=1, max_length=128)
    timestamp: str = Field(..., min_length=1, max_length=64)
    reason: str = Field(..., min_length=1, max_length=512)
    before_state: dict = Field(default_factory=dict)
    after_state: dict = Field(default_factory=dict)
    action: str = Field(default="status_change", min_length=1, max_length=64)


class AuditTrail(BaseModel):
    """Top-level envelope for GET /incidents/{id}/audit-trail."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    incident_id: str = Field(..., min_length=1, max_length=64)
    entries: list[AuditTrailEntry] = Field(default_factory=list)
    total: int = Field(ge=0)


# ---------------------------------------------------------------------------
# FR-023: Badcase enums
# ---------------------------------------------------------------------------


BadcaseStatus = Literal[
    "open",  # newly raised, not yet reviewed
    "reviewing",  # reviewer assigned, work in progress
    "closed",  # resolved without escalation
    "escalated",  # promoted to incident via /escalate
]

BadcasePrivacyClass = Literal[
    "public",  # no sensitive content — safe for PM
    "internal",  # internal-only fields
    "restricted",  # maintainer-only — requires redaction / reason
]


# ---------------------------------------------------------------------------
# FR-023: Badcase
# ---------------------------------------------------------------------------


class Badcase(BaseModel):
    """A single badcase row (FR-023).

    FR-023 mandated fields (10):

    - ``id``
    - ``eval_verdict``
    - ``affected_feature_area``
    - ``affected_user_id``
    - ``privacy_class``
    - ``classification``
    - ``owner``
    - ``status`` (open/reviewing/closed/escalated)
    - ``resolution``
    - ``first_seen_at``

    Plus auxiliary fields:

    - ``incident_id`` — set when this badcase has been escalated.
    - ``freshness_at`` — ISO 8601 OR "unknown".
    - ``audit_trail`` — list of audit entries (EC-4 mirror).
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: str = Field(..., min_length=1, max_length=64)
    eval_verdict: str = Field(..., min_length=1, max_length=64)
    affected_feature_area: str = Field(..., min_length=1, max_length=64)
    affected_user_id: str = Field(..., min_length=1, max_length=64)
    privacy_class: BadcasePrivacyClass
    classification: str = Field(..., min_length=1, max_length=64)
    owner: str = Field(..., min_length=1, max_length=128)
    status: BadcaseStatus
    resolution: str = Field(default="", max_length=1024)
    first_seen_at: str = Field(..., min_length=1, max_length=64)
    incident_id: Optional[str] = Field(default=None, max_length=64)
    freshness_at: str = Field(default="unknown", max_length=64)
    description: str = Field(default="", max_length=1024)
    audit_trail: list[AuditTrailEntry] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# FR-023: Badcase list envelope
# ---------------------------------------------------------------------------


class BadcaseListResponse(BaseModel):
    """Top-level envelope for GET /badcases."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    badcases: list[Badcase] = Field(default_factory=list)
    total: int = Field(ge=0)
    open_count: int = Field(default=0, ge=0)
    escalated_count: int = Field(default=0, ge=0)
    freshness_at: str = Field(default="unknown", max_length=64)


# ---------------------------------------------------------------------------
# FR-023: Badcase escalate response
# ---------------------------------------------------------------------------


class BadcaseEscalateResponse(BaseModel):
    """POST /badcases/{id}/escalate response with the new incident_id."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    badcase_id: str = Field(..., min_length=1, max_length=64)
    incident_id: str = Field(..., min_length=1, max_length=64)
    escalated_at: str = Field(..., min_length=1, max_length=64)
    escalated_by: str = Field(..., min_length=1, max_length=128)


# ---------------------------------------------------------------------------
# REQ-061 US10 — canonical operational Bad Case facade schemas (T134)
# ---------------------------------------------------------------------------


class OperationalDataQuality(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fresh_at: str
    coverage_percent: float = Field(ge=0, le=100)
    unknown_count: int = Field(ge=0)
    seed_or_mock_count: int = Field(ge=0, le=0)


class OperationalBadcaseSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    badcase_id: str
    status: str
    severity: str
    category: str
    capabilities: list[str] = Field(default_factory=list)
    owner: str | None = None
    privacy_class: str
    first_seen_at: str | None = None
    last_seen_at: str | None = None
    task_count: int = 0
    user_count: int | None = None
    user_count_status: str = "unknown"
    point_treatment_status: str = "unknown"
    sla_status: str = "within_sla"
    version: int = 1
    data_completeness: str = "partial"


class OperationalBadcasePage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[OperationalBadcaseSummary] = Field(default_factory=list)
    next_cursor: str | None = None
    data_quality: OperationalDataQuality
    compatibility: dict[str, str] = Field(default_factory=dict)


class OperationalCompatibilityLinks(BaseModel):
    model_config = ConfigDict(extra="forbid")

    legacy_admin_badcases: str = "/api/v1/admin-console/badcases"
    legacy_domain_badcases: str = "/api/v1/badcases"
    canonical: str = "/api/v1/admin-console/ai/badcases"


# Resolve forward references (AuditTrailEntry referenced by Incident / Badcase).
Incident.model_rebuild()
Badcase.model_rebuild()


__all__ = [
    "AuditTrail",
    "AuditTrailEntry",
    "Badcase",
    "BadcaseEscalateResponse",
    "BadcaseListResponse",
    "BadcasePrivacyClass",
    "BadcaseStatus",
    "Comment",
    "CommentCreateRequest",
    "CommentListResponse",
    "EvidenceLink",
    "EvidenceLinkListResponse",
    "EvidenceLinkType",
    "Incident",
    "IncidentListResponse",
    "IncidentSeverity",
    "IncidentStatus",
    "IncidentTrend",
    "OperationalBadcasePage",
    "OperationalBadcaseSummary",
    "OperationalCompatibilityLinks",
    "OperationalDataQuality",
    "StatusChangeRequest",
]
