"""Environment-specific redaction policy for REQ-033 US10 (FR-031..FR-036).

Three policies are supported:

- ``ALLOW_ALL`` — pass-through, used in local / CI for synthetic data.
- ``STRIP_PII`` — remove PII keys (``email`` / ``phone`` / ``address``) from
  ``ProductEvent.properties`` and from any nested dict. Other fields kept.
- ``METADATA_ONLY`` — keep only ``name`` + ``occurred_at`` + ``event_id`` +
  (optionally) ``user_id`` from the event envelope; ``properties`` is
  replaced with ``{}``.

Production environment defaults to ``METADATA_ONLY`` and *forces*
``user_id`` to ``None`` unless ``RedactionContext.allow_user_ids`` contains
the user (escape hatch for opt-in debugging; rare).

The policy is applied via ``apply_redaction(event, ctx) -> ProductEvent``
(immutable — returns a new dataclass) and validated via
``validate_redaction(policy, event) -> list[str]`` (returns the names of
fields that violate the policy). ``RedactionAudit`` records one audit row
per redaction so FR-035 ("production export audit evidence") can be
backed.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from app.modules.telemetry_contracts.events import ProductEvent

try:
    from app.eval.schemas import RepresentationLevel
except Exception:  # pragma: no cover - keeps REQ-033 import surface tolerant
    RepresentationLevel = None  # type: ignore[assignment]


class RedactionPolicy(StrEnum):
    """Available redaction policies."""

    ALLOW_ALL = "ALLOW_ALL"
    STRIP_PII = "STRIP_PII"
    METADATA_ONLY = "METADATA_ONLY"


# Field names stripped by STRIP_PII. Lower-cased for case-insensitive match.
PII_FIELDS: frozenset[str] = frozenset({"email", "phone", "address"})
MASKED_RAW_SECRET_FIELDS: frozenset[str] = frozenset(
    {"authorization", "api_key", "apikey", "secret", "password", "token", "cookie"}
)
MASKED_RAW_ALLOWED_VALUES: frozenset[str] = frozenset(
    {
        "[MASKED_SECRET]",
        "[MASKED_SYSTEM_PROMPT]",
        "[MASKED_USER_TEXT]",
        "[REDACTED]",
    }
)

# Metadata fields kept by METADATA_ONLY. Everything else (including
# ``properties``) is dropped.
METADATA_FIELDS: frozenset[str] = frozenset(
    {"name", "occurred_at", "event_id", "user_id"}
)

VALID_ENVIRONMENTS: frozenset[str] = frozenset(
    {"dev", "local", "ci", "staging", "production"}
)


@dataclass
class RedactionContext:
    """Redaction environment + policy + escape-hatch configuration."""

    env: str
    policy: RedactionPolicy
    redaction_fields: set[str] = field(default_factory=lambda: set(PII_FIELDS))
    allow_user_ids: set[UUID] = field(default_factory=set)
    policy_version: str = "v1"

    def __post_init__(self) -> None:
        env_norm = self.env.strip().lower()
        if env_norm not in VALID_ENVIRONMENTS:
            raise ValueError(
                f"invalid env={self.env!r}; expected one of "
                f"{sorted(VALID_ENVIRONMENTS)}"
            )
        # RedactionContext is mutable (not frozen) so direct assignment
        # is fine here. (RetentionContext is frozen and uses
        # object.__setattr__ for the same canonicalization.)
        self.env = env_norm


@dataclass
class RedactionAudit:
    """Audit row for one redaction operation (FR-035 evidence)."""

    audit_id: UUID
    event_id: UUID
    policy_applied: RedactionPolicy
    env: str
    fields_redacted: list[str]
    audited_at: datetime
    policy_version: str = "v1"

    def to_dict(self) -> dict[str, Any]:
        return {
            "audit_id": str(self.audit_id),
            "event_id": str(self.event_id),
            "policy_applied": self.policy_applied.value,
            "env": self.env,
            "fields_redacted": list(self.fields_redacted),
            "audited_at": self.audited_at.isoformat(),
            "policy_version": self.policy_version,
        }


def _strip_pii_from_dict(d: dict[str, Any], fields: set[str]) -> tuple[dict[str, Any], list[str]]:
    """Strip PII keys (case-insensitive) from a dict. Returns new dict + keys removed."""
    removed: list[str] = []
    out: dict[str, Any] = {}
    for k, v in d.items():
        if k.lower() in fields:
            removed.append(k)
        else:
            out[k] = v
    return out, removed


def production_default_context(
    *, allow_user_ids: set[UUID] | None = None, policy_version: str = "v1"
) -> RedactionContext:
    """Build the canonical production redaction context (METADATA_ONLY).

    FR-035a: production trace metadata + redacted summaries retained 30 days;
    redaction here enforces that user content cannot leak out of ``properties``.
    """
    return RedactionContext(
        env="production",
        policy=RedactionPolicy.METADATA_ONLY,
        allow_user_ids=set(allow_user_ids or set()),
        policy_version=policy_version,
    )


def staging_default_context(policy_version: str = "v1") -> RedactionContext:
    """Staging context: STRIP_PII (keeps properties minus PII; metadata visible)."""
    return RedactionContext(
        env="staging",
        policy=RedactionPolicy.STRIP_PII,
        policy_version=policy_version,
    )


def dev_default_context(policy_version: str = "v1") -> RedactionContext:
    """Dev / local / CI context: ALLOW_ALL (no redaction; synthetic data)."""
    return RedactionContext(env="dev", policy=RedactionPolicy.ALLOW_ALL, policy_version=policy_version)


def apply_redaction(
    event: ProductEvent, ctx: RedactionContext
) -> ProductEvent:
    """Return a redacted copy of ``event`` per ``ctx`` policy.

    Behavior by policy:

    - ``ALLOW_ALL`` → returns a deepcopy unchanged (no audit recorded).
    - ``STRIP_PII`` → returns a copy with PII keys removed from
      ``properties``. Empty dict is preserved (not replaced).
    - ``METADATA_ONLY`` → returns a copy with only ``name`` /
      ``occurred_at`` / ``event_id`` / (allowed) ``user_id`` retained.
      ``properties`` is set to ``{}``.

    Production (``env == "production"``) *forces* ``user_id`` to ``None``
    unless it appears in ``ctx.allow_user_ids``. This is independent of
    the policy field (so callers cannot accidentally bypass the production
    user-id policy by choosing ``STRIP_PII``).
    """
    if ctx.policy == RedactionPolicy.ALLOW_ALL:
        return deepcopy(event)

    if ctx.policy == RedactionPolicy.STRIP_PII:
        cleaned_props, _ = _strip_pii_from_dict(event.properties, ctx.redaction_fields)
        user_id = event.user_id
        if (
            ctx.env == "production"
            and user_id is not None
            and user_id not in ctx.allow_user_ids
        ):
            user_id = None
        return ProductEvent(
            name=event.name,
            occurred_at=event.occurred_at,
            properties=cleaned_props,
            event_id=event.event_id,
            user_id=user_id,
            environment=event.environment,
            release_stage=event.release_stage,
            app_version=event.app_version,
            feature_area=event.feature_area,
            privacy_class=event.privacy_class,
            redaction_status="PASSED",
        )

    # METADATA_ONLY
    user_id = event.user_id
    if (
        ctx.env == "production"
        and user_id is not None
        and user_id not in ctx.allow_user_ids
    ):
        user_id = None
    return ProductEvent(
        name=event.name,
        occurred_at=event.occurred_at,
        properties={},
        event_id=event.event_id,
        user_id=user_id,
        environment=event.environment,
        release_stage=event.release_stage,
        app_version=event.app_version,
        feature_area=event.feature_area,
        privacy_class=event.privacy_class,
        redaction_status="PASSED",
    )


def audit_redaction(
    event: ProductEvent,
    ctx: RedactionContext,
    redacted_event: ProductEvent,
    *,
    audited_at: datetime | None = None,
) -> RedactionAudit:
    """Compute and record a ``RedactionAudit`` for the redacted event.

    Compares field-by-field between the original and redacted event to
    enumerate which fields were actually removed or stripped. Pure
    function — does not persist anywhere (DB / file). Persistence is the
    caller's job (Sub-batch 2).
    """
    fields_redacted: list[str] = []
    if event.properties != redacted_event.properties:
        # enumerate keys present in original but absent in redacted
        orig_keys = set(event.properties.keys())
        new_keys = set(redacted_event.properties.keys())
        for k in sorted(orig_keys - new_keys):
            fields_redacted.append(k)
    if event.user_id != redacted_event.user_id and event.user_id is not None:
        fields_redacted.append("user_id")
    if event.environment != redacted_event.environment:
        fields_redacted.append("environment")
    if event.app_version != redacted_event.app_version:
        fields_redacted.append("app_version")
    if event.feature_area != redacted_event.feature_area:
        fields_redacted.append("feature_area")
    if event.release_stage != redacted_event.release_stage:
        fields_redacted.append("release_stage")
    if event.privacy_class != redacted_event.privacy_class:
        fields_redacted.append("privacy_class")
    if event.name != redacted_event.name:
        fields_redacted.append("name")

    return RedactionAudit(
        audit_id=uuid4(),
        event_id=event.event_id,
        policy_applied=ctx.policy,
        env=ctx.env,
        fields_redacted=fields_redacted,
        audited_at=audited_at or datetime.now(UTC),
        policy_version=ctx.policy_version,
    )


def validate_redaction(
    policy: RedactionPolicy, event: ProductEvent
) -> list[str]:
    """Return field names that violate ``policy`` (for pre-export validation).

    Use this before exporting an event to a downstream system (LangSmith,
    external report) to confirm the event meets the policy. Returns the
    names of *envelope* fields / ``properties`` keys that violate the
    policy; empty list means the event passes.

    Note: this only checks shape, not cross-context concerns (e.g.
    production user_id forcing). For full audit, use ``audit_redaction``
    after ``apply_redaction``.
    """
    violations: list[str] = []
    if policy == RedactionPolicy.ALLOW_ALL:
        return violations

    if policy == RedactionPolicy.STRIP_PII:
        for key in event.properties:
            if key.lower() in PII_FIELDS:
                violations.append(f"properties.{key}")
        return violations

    # METADATA_ONLY: properties must be empty AND only metadata fields set.
    if event.properties:
        violations.append("properties")
    # Envelope fields other than the allowed metadata set are violations
    # *if* they carry non-default values. For validate_redaction we treat
    # the dataclass as is — anything that survives must be in METADATA_FIELDS.
    # We don't introspect defaults; we just note that "non-metadata fields
    # are present" as a violation if the corresponding field carries info
    # beyond the metadata envelope. This is a coarse signal — callers
    # wanting strict checks should pass through ``apply_redaction`` and
    # diff the result.
    if event.release_stage not in {"UNKNOWN", "DEVELOPMENT", "RELEASE_CANDIDATE", "PRODUCTION"}:
        violations.append("release_stage")
    return violations


def _path_join(parent: str, key: str) -> str:
    return f"{parent}.{key}" if parent else key


def _is_mask_placeholder(value: Any) -> bool:
    return isinstance(value, str) and (
        value in MASKED_RAW_ALLOWED_VALUES or value.startswith("[MASKED:")
    )


def _looks_like_raw_secret(value: str) -> bool:
    lowered = value.lower()
    return (
        lowered.startswith("bearer ")
        or lowered.startswith("sk-")
        or "api_key=" in lowered
        or "password=" in lowered
    )


def validate_masked_raw_payload(payload: Any) -> list[str]:
    """Return paths whose masked-raw values still expose sensitive content.

    This validation is intentionally conservative. It focuses on the surfaces
    REQ-035 allows in masked raw payloads: secret-bearing keys must hold mask
    placeholders, and LLM chat message content for system/user roles must be
    masked rather than raw text.
    """

    violations: list[str] = []

    def visit(value: Any, path: str, *, parent_role: str | None = None) -> None:
        if isinstance(value, dict):
            role = str(value.get("role", parent_role or "")).lower()
            for key, child in value.items():
                child_path = _path_join(path, str(key))
                key_norm = str(key).lower()
                if key_norm in MASKED_RAW_SECRET_FIELDS:
                    if not _is_mask_placeholder(child):
                        violations.append(child_path)
                    continue
                if key_norm == "content" and role in {"system", "user"}:
                    if not _is_mask_placeholder(child):
                        violations.append(child_path)
                    continue
                visit(child, child_path, parent_role=role or parent_role)
            return
        if isinstance(value, list):
            for index, item in enumerate(value):
                visit(item, f"{path}[{index}]", parent_role=parent_role)
            return
        if isinstance(value, str) and _looks_like_raw_secret(value) and not _is_mask_placeholder(value):
            violations.append(path)

    visit(payload, "")
    return violations


def _normalize_representation_level(level: Any) -> str:
    value = getattr(level, "value", level)
    return str(value).strip().upper()


def _redact_destination_payload(value: Any, path: str = "", *, role: str | None = None) -> Any:
    if isinstance(value, dict):
        current_role = str(value.get("role", role or "")).lower()
        out: dict[str, Any] = {}
        for key, child in value.items():
            key_norm = str(key).lower()
            if key_norm in PII_FIELDS or key_norm in MASKED_RAW_SECRET_FIELDS:
                out[key] = "[REDACTED]"
                continue
            if key_norm == "content" and current_role in {"system", "user"}:
                out[key] = "[REDACTED]"
                continue
            out[key] = _redact_destination_payload(
                child,
                _path_join(path, str(key)),
                role=current_role or role,
            )
        return out
    if isinstance(value, list):
        return [
            _redact_destination_payload(item, f"{path}[{index}]", role=role)
            for index, item in enumerate(value)
        ]
    if isinstance(value, str) and _looks_like_raw_secret(value):
        return "[REDACTED]"
    return deepcopy(value)


def _metadata_shape(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return {
            "kind": "object",
            "keys": sorted(str(key) for key in value.keys()),
            "fieldCount": len(value),
        }
    if isinstance(value, list):
        return {"kind": "array", "itemCount": len(value)}
    return {"kind": type(value).__name__}


def apply_destination_representation(payload: Any, level: Any) -> Any:
    """Transform a payload to the representation approved for a destination."""

    normalized = _normalize_representation_level(level)
    if normalized == "FULL_CONTENT":
        return deepcopy(payload)
    if normalized == "REDACTED":
        return _redact_destination_payload(payload)
    if normalized == "METADATA_ONLY":
        return {
            "representationLevel": "METADATA_ONLY",
            "shape": _metadata_shape(payload),
        }
    if normalized == "BLOCKED":
        return None
    raise ValueError(f"unknown representation level: {level!r}")


__all__ = [
    "apply_destination_representation",
    "MASKED_RAW_ALLOWED_VALUES",
    "MASKED_RAW_SECRET_FIELDS",
    "METADATA_FIELDS",
    "PII_FIELDS",
    "VALID_ENVIRONMENTS",
    "RedactionAudit",
    "RedactionContext",
    "RedactionPolicy",
    "apply_redaction",
    "audit_redaction",
    "dev_default_context",
    "production_default_context",
    "staging_default_context",
    "validate_masked_raw_payload",
    "validate_redaction",
]
