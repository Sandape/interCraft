"""Shared Pydantic v2 value objects for REQ-033 (T014, T037 US9).

Self-contained Pydantic v2 models representing the canonical shape of
version context, AI invocation summary, and related join fields used
across the eval / PM dashboard / badcase pipelines.

Why Pydantic v2 (not dataclass like the rest of this package)?

- Validation: Pydantic enforces enum ranges (release_stage, environment,
  status) at construction time so missing/garbage values fail-fast.
- JSON round-trip: ``model_dump(by_alias=True)`` / ``model_validate``
  give us camelCase contract out of the box.
- SC-010 normalization: field defaults to ``"unknown"`` (not None) so the
  explicit-unknown contract is enforced by the schema itself, not by
  caller convention.

The dataclass modules (events.py / metrics.py / redaction.py / retention.py)
remain the runtime contract for streaming event types; this module is the
**value-object** contract for things that go into DB columns / report rows
where validation matters.

Public surface (exported via __init__.py):

- ``VersionContext`` — the canonical version join field (data-model.md §VersionContext).
- ``AIInvocationSummary`` — the canonical AI-call summary row.
- ``PromptFingerprint`` helpers in ``prompt_fingerprint.py`` (T039).
"""
from __future__ import annotations

from typing import Any, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, alias_generators, field_validator, model_validator
from pydantic.alias_generators import to_camel


# ---------------------------------------------------------------------------
# VersionContext
# ---------------------------------------------------------------------------

# Canonical release-stage enum (data-model.md §VersionContext).
RELEASE_STAGES: tuple[str, ...] = (
    "DEVELOPMENT",
    "RELEASE_CANDIDATE",
    "PRODUCTION",
    "UNKNOWN",
)

# Canonical environment enum (data-model.md §VersionContext).
ENVIRONMENTS: tuple[str, ...] = ("LOCAL", "CI", "STAGING", "PRODUCTION")


class VersionContext(BaseModel):
    """Shared version attribution fields (data-model.md §VersionContext).

    SC-010 / FR-038: missing fields are represented as the explicit string
    ``"unknown"`` — never None, never empty string, never field omission.
    This contract is enforced at construction time by the ``field_validator``
    below.
    """

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        str_strip_whitespace=True,
        alias_generator=to_camel,
    )

    # --- required ---
    app_version: str = Field(
        ...,
        min_length=1,
        description="Product version or explicit 'unknown'.",
    )
    release_stage: str = Field(
        default="UNKNOWN",
        description="DEVELOPMENT | RELEASE_CANDIDATE | PRODUCTION | UNKNOWN",
    )
    environment: str = Field(
        default="LOCAL",
        description="LOCAL | CI | STAGING | PRODUCTION",
    )
    schema_version: str = Field(
        ...,
        min_length=1,
        description="Event/report schema version (e.g. 'v1').",
    )

    # --- conditional (default to explicit "unknown") ---
    prompt_fingerprint: str = Field(default="unknown")
    rubric_version: str = Field(default="unknown")
    model: str = Field(default="unknown")
    experiment_id: str = Field(default="unknown")
    graph: str = Field(default="unknown")
    node: str = Field(default="unknown")

    @field_validator("app_version", "schema_version")
    @classmethod
    def _required_non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("required field cannot be empty")
        return v

    @field_validator("release_stage")
    @classmethod
    def _valid_release_stage(cls, v: str) -> str:
        if v not in RELEASE_STAGES:
            raise ValueError(
                f"release_stage must be one of {RELEASE_STAGES}, got {v!r}"
            )
        return v

    @field_validator("environment")
    @classmethod
    def _valid_environment(cls, v: str) -> str:
        if v not in ENVIRONMENTS:
            raise ValueError(
                f"environment must be one of {ENVIRONMENTS}, got {v!r}"
            )
        return v

    @field_validator(
        "prompt_fingerprint",
        "rubric_version",
        "model",
        "experiment_id",
        "graph",
        "node",
    )
    @classmethod
    def _normalize_optional(cls, v: Optional[str]) -> str:
        """Empty / None → explicit ``"unknown"`` (SC-010 normalization)."""
        if v is None or (isinstance(v, str) and not v.strip()):
            return "unknown"
        return v

    @model_validator(mode="after")
    def _no_field_is_none(self) -> "VersionContext":
        """Belt-and-suspenders: no field may be None at the end of validation."""
        for fname in self.model_fields:
            val = getattr(self, fname)
            if val is None:
                raise ValueError(f"{fname} must not be None (SC-010)")
        return self

    # ---- factory ----

    @classmethod
    def unknown(cls, *, environment: str = "LOCAL") -> "VersionContext":
        """Build a VersionContext with every field set to ``"unknown"``.

        ``environment`` is the one exception — caller can pass a real env
        even when all other version fields are unknown. Used when a record
        is recorded but the version source has not been wired up yet.
        """
        return cls(
            app_version="unknown",
            release_stage="UNKNOWN",
            environment=environment,
            schema_version="unknown",
            prompt_fingerprint="unknown",
            rubric_version="unknown",
            model="unknown",
            experiment_id="unknown",
            graph="unknown",
            node="unknown",
        )

    # ---- JSON contract (camelCase per contracts/event-metric-schema.md) ----

    def to_dict(self) -> dict[str, Any]:
        """Serialize to camelCase dict matching the canonical event schema."""
        return self.model_dump(by_alias=True, mode="json")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VersionContext":
        """Re-hydrate from a dict that uses either snake_case or camelCase.

        Tolerates both because callers from JSON web payloads typically
        use camelCase, while internal Python call sites use snake_case.
        Missing optional fields are normalized to ``"unknown"`` via the
        field defaults above.
        """
        return cls.model_validate(data)


# ---------------------------------------------------------------------------
# AIInvocationSummary
# ---------------------------------------------------------------------------

# Status enum (data-model.md §AIInvocationRecord).
AI_INVOCATION_STATUSES: tuple[str, ...] = (
    "SUCCESS",
    "FAILURE",
    "TIMEOUT",
    "CANCELLED",
    "UNKNOWN",
)


class AIInvocationSummary(BaseModel):
    """Per-AI-call summary (data-model.md §AIInvocationRecord).

    Field semantics (US9 contract):

    - ``invocationId`` / ``runId`` / ``traceId`` are join ids for the
      eval / trace pipelines. ``runId`` and ``traceId`` may be None when
      the call is not part of an eval run.
    - ``graph`` + ``node`` identify the agent context.
    - ``model`` + ``promptFingerprint`` + ``rubricVersion`` are version
      fields; missing → explicit ``"unknown"`` (SC-010).
    - ``estimatedCost`` is always labeled ``isEstimate=true`` — cost is
      not billed per-call.
    - ``status`` is one of the canonical enums; on failure, ``errorCategory``
      is required.
    """

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        alias_generator=to_camel,
    )

    invocation_id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: Optional[UUID] = Field(default=None)
    run_id: Optional[UUID] = Field(default=None)
    trace_id: Optional[str] = Field(default=None)
    graph: str = Field(default="unknown")
    node: str = Field(default="unknown")
    model: str = Field(default="unknown")
    prompt_fingerprint: str = Field(default="unknown")
    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)
    estimated_cost: float = Field(default=0.0, ge=0.0)
    is_estimate: bool = Field(default=True)
    latency_ms: int = Field(default=0, ge=0)
    retry_count: int = Field(default=0, ge=0)
    status: str = Field(default="SUCCESS")
    error_category: Optional[str] = Field(default=None)

    @field_validator("graph", "node", "model", "prompt_fingerprint")
    @classmethod
    def _normalize_version_field(cls, v: Optional[str]) -> str:
        if v is None or (isinstance(v, str) and not v.strip()):
            return "unknown"
        return v

    @field_validator("status")
    @classmethod
    def _valid_status(cls, v: str) -> str:
        if v not in AI_INVOCATION_STATUSES:
            raise ValueError(
                f"status must be one of {AI_INVOCATION_STATUSES}, got {v!r}"
            )
        return v

    @field_validator("error_category")
    @classmethod
    def _normalize_error_category(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        if isinstance(v, str) and not v.strip():
            return "unknown"
        return v

    # ---- factory ----

    @classmethod
    def unknown(cls) -> "AIInvocationSummary":
        """Build an AIInvocationSummary with every string field set to ``"unknown"``.

        Used for SC-010 normalization — a record always carries explicit
        values for every version / status field, never None / empty.
        """
        return cls(
            invocation_id=str(uuid4()),
            user_id=None,
            run_id=None,
            trace_id=None,
            graph="unknown",
            node="unknown",
            model="unknown",
            prompt_fingerprint="unknown",
            prompt_tokens=0,
            completion_tokens=0,
            estimated_cost=0.0,
            is_estimate=True,
            latency_ms=0,
            retry_count=0,
            status="UNKNOWN",
            error_category="unknown",
        )

    # ---- JSON contract ----

    def to_dict(self) -> dict[str, Any]:
        """Serialize to camelCase dict matching the canonical event schema."""
        return self.model_dump(by_alias=True, mode="json")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AIInvocationSummary":
        """Re-hydrate from dict. Tolerates snake_case or camelCase keys."""
        return cls.model_validate(data)


__all__ = [
    "AI_INVOCATION_STATUSES",
    "AIInvocationSummary",
    "ENVIRONMENTS",
    "RELEASE_STAGES",
    "VersionContext",
]
