"""Export-policy guard for REQ-033 US10 (FR-031..FR-036, FR-024).

The guard sits between the eval / LangSmith reporter and any external
export sink (LangSmith Cloud, external report artifact, etc.). It
enforces three rules before any payload leaves the process:

1. **Environment-specific forbidden content** — production MUST NOT
   contain raw resume text, interview answers, JD text, free-form chat,
   access / refresh tokens, API keys, passwords, or other secrets.
   Staging may carry these only for synthetic / golden / approved
   staging test data; otherwise metadata + redacted summaries only.
2. **Dual approval for emergency override** (FR-024) — any override of
   an eval gate requires BOTH the PM business owner and the technical
   owner. A single-signature record hard-fails.
3. **Fail-open runtime** (FR-017) — if export preparation itself raises
   an unexpected exception, callers MUST still be able to continue
   product execution. ``safe_prepare_export_payload`` wraps the strict
   ``prepare_export_payload`` to swallow operational errors and return
   a ``None``-marked payload so product flow can resume.

This module is intentionally LangSmith-free: it imports nothing from
``langsmith`` and depends only on the
``telemetry_contracts.redaction`` library (which is also
LangSmith-free). Future US6 work that introduces ``langsmith_reporter``
should call :func:`prepare_export_payload` from this module before
pushing to the LangSmith SDK so the same policy guard applies to both
report-file output and LangSmith experiment sync.

Contract (called by US6 ``langsmith_reporter``):

- ``prepare_export_payload(report_data, environment)`` returns the
  payload dict with forbidden-content keys stripped and a
  ``"redaction_status"`` field set to ``"PASSED"`` or ``"FAILED"``.
- ``enforce_export_policy(payload, environment)`` raises
  :class:`PolicyViolation` if forbidden content remains.
- ``is_override_approved(override_record)`` returns ``True`` only if
  BOTH the PM business owner and the technical owner signed.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import structlog

from app.modules.telemetry_contracts.redaction import (
    RedactionContext,
    RedactionPolicy,
    dev_default_context,
    production_default_context,
    staging_default_context,
)

logger = structlog.get_logger("eval.export_policy")

# Forbidden production export keys (FR-032, SC-008).
# Lower-case for case-insensitive comparison.
FORBIDDEN_PRODUCTION_KEYS: frozenset[str] = frozenset(
    {
        "resume_text",
        "interview_answer",
        "job_description",
        "free_form_text",
        "api_key",
        "access_token",
        "refresh_token",
        "password",
        "secret",
    }
)

# Override dual-approval roles (FR-024).
REQUIRED_OVERRIDE_ROLES: frozenset[str] = frozenset(
    {"PM_BUSINESS_OWNER", "TECHNICAL_OWNER"}
)

# Environments where the strict production forbidden-content check applies.
PROD_LIKE_ENVIRONMENTS: frozenset[str] = frozenset({"production", "prod"})


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class PolicyViolation(Exception):
    """Raised when a payload violates the export policy.

    Attributes:
        environment: env under which the violation was detected.
        violations: list of forbidden key names that triggered the failure.
        sample_id: optional sample id (audit_id / case_id) for traceability.
    """

    def __init__(
        self,
        message: str,
        *,
        environment: str,
        violations: list[str],
        sample_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.environment = environment
        self.violations = list(violations)
        self.sample_id = sample_id


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RedactionResult:
    """Outcome of one ``prepare_export_payload`` call.

    Fields:
        payload: the (possibly redacted) dict to forward to the export
            sink. ``None`` if the entire payload was rejected.
        redacted: True if at least one forbidden key was stripped.
        redaction_status: ``"PASSED"`` / ``"FAILED"`` / ``"NOT_REQUIRED"``.
        violations: list of forbidden key names still present after
            processing. Empty list means the payload is safe to export.
    """

    payload: dict[str, Any] | None
    redacted: bool
    redaction_status: str
    violations: list[str]


# ---------------------------------------------------------------------------
# Environment → redaction context
# ---------------------------------------------------------------------------


def _is_prod_like(environment: str) -> bool:
    return environment.strip().lower() in PROD_LIKE_ENVIRONMENTS


def context_for_environment(environment: str) -> RedactionContext:
    """Build the redaction context for an environment string.

    Recognized environments (case-insensitive):

    - ``production`` / ``prod`` → :func:`production_default_context`.
    - ``staging`` → :func:`staging_default_context`.
    - everything else (local / dev / ci) → :func:`dev_default_context`.

    Unknown environments fall back to the dev (ALLOW_ALL) context — but
    :func:`enforce_export_policy` still applies the strict
    forbidden-content check on top of whatever policy the dev context
    advertises.
    """
    norm = environment.strip().lower()
    if _is_prod_like(norm):
        return production_default_context()
    if norm == "staging":
        return staging_default_context()
    return dev_default_context()


# ---------------------------------------------------------------------------
# Forbidden-content detection
# ---------------------------------------------------------------------------


def find_forbidden_keys(payload: Mapping[str, Any]) -> list[str]:
    """Walk ``payload`` and return the list of forbidden key names.

    Scans both ``payload["properties"]`` and ``payload["metadata"]`` (if
    either is a dict) plus top-level string values that match the
    forbidden key set. Comparison is case-insensitive.
    """
    found: set[str] = set()
    for container_key in ("properties", "metadata"):
        sub = payload.get(container_key)
        if isinstance(sub, Mapping):
            for k in sub:
                if k.lower() in FORBIDDEN_PRODUCTION_KEYS:
                    found.add(k)
    # Top-level keys (e.g. when caller flattens).
    for k in payload:
        if isinstance(k, str) and k.lower() in FORBIDDEN_PRODUCTION_KEYS:
            found.add(k)
    return sorted(found)


# ---------------------------------------------------------------------------
# Payload preparation
# ---------------------------------------------------------------------------


def prepare_export_payload(
    report_data: Mapping[str, Any],
    environment: str,
) -> RedactionResult:
    """Strip forbidden keys from ``report_data`` and stamp a status.

    The result is always deterministic: same input + environment →
    same output. Production payload with non-empty forbidden content
    returns ``payload=None`` and ``redaction_status="FAILED"``.

    Non-production environments with forbidden content get those keys
    *stripped* (caller still gets a usable payload) but
    ``redaction_status="FAILED"`` so callers can decide to skip upload.
    """
    norm_env = environment.strip().lower()
    ctx = context_for_environment(norm_env)
    payload: dict[str, Any] = dict(report_data)
    forbidden = find_forbidden_keys(payload)

    redacted = False
    for container_key in ("properties", "metadata"):
        sub = payload.get(container_key)
        if isinstance(sub, Mapping):
            cleaned = {
                k: v
                for k, v in sub.items()
                if (not isinstance(k, str)) or k.lower() not in FORBIDDEN_PRODUCTION_KEYS
            }
            if len(cleaned) != len(sub):
                redacted = True
                payload[container_key] = cleaned

    # Also strip top-level forbidden keys.
    for k in list(payload.keys()):
        if isinstance(k, str) and k.lower() in FORBIDDEN_PRODUCTION_KEYS:
            payload.pop(k, None)
            redacted = True

    is_prod = _is_prod_like(norm_env)

    if forbidden and is_prod:
        # Production: hard-reject (return None).
        logger.warning(
            "export_policy.production_forbidden",
            environment=norm_env,
            violations=forbidden,
            policy_version=ctx.policy_version,
        )
        return RedactionResult(
            payload=None,
            redacted=True,
            redaction_status="FAILED",
            violations=forbidden,
        )

    if forbidden:
        # Non-prod: stripped but flagged.
        logger.warning(
            "export_policy.non_prod_forbidden_stripped",
            environment=norm_env,
            violations=forbidden,
            policy_version=ctx.policy_version,
        )
        status = "FAILED"
    else:
        status = "NOT_REQUIRED" if ctx.policy == RedactionPolicy.ALLOW_ALL else "PASSED"

    payload.setdefault("environment", norm_env)
    payload["redaction_status"] = status
    payload["redaction_policy"] = ctx.policy.value
    payload["policy_version"] = ctx.policy_version

    return RedactionResult(
        payload=payload,
        redacted=redacted,
        redaction_status=status,
        violations=forbidden,
    )


def enforce_export_policy(
    payload: Mapping[str, Any],
    environment: str,
    *,
    sample_id: str | None = None,
) -> dict[str, Any]:
    """Raise :class:`PolicyViolation` if ``payload`` is not safe to export.

    On success returns the (possibly normalized) payload as a fresh dict.
    """
    norm_env = environment.strip().lower()
    violations = find_forbidden_keys(payload)
    if _is_prod_like(norm_env) and violations:
        raise PolicyViolation(
            f"forbidden production content detected: {violations}",
            environment=norm_env,
            violations=violations,
            sample_id=sample_id,
        )
    out = dict(payload)
    out["environment"] = norm_env
    out["redaction_status"] = "FAILED" if violations else "PASSED"
    return out


def safe_prepare_export_payload(
    report_data: Mapping[str, Any],
    environment: str,
) -> RedactionResult:
    """Fail-open wrapper around :func:`prepare_export_payload`.

    Per FR-017 (``LangSmith integration MUST fail open for product
    runtime``): if the strict preparation itself raises an unexpected
    exception, return a ``RedactionResult`` with ``payload=None`` and
    status ``"FAILED"`` so the calling product path can continue without
    raising.
    """
    try:
        return prepare_export_payload(report_data, environment)
    except Exception as exc:  # pragma: no cover — defensive
        logger.error(
            "export_policy.safe_prepare_unexpected_error",
            environment=environment,
            error_type=type(exc).__name__,
            error=str(exc),
        )
        return RedactionResult(
            payload=None,
            redacted=False,
            redaction_status="FAILED",
            violations=[],
        )


# ---------------------------------------------------------------------------
# Dual-approval gate (FR-024)
# ---------------------------------------------------------------------------


def is_override_approved(override_record: Mapping[str, Any]) -> bool:
    """Return True iff BOTH PM business owner AND technical owner signed.

    Per FR-024: ``Baseline refresh and emergency override MUST require
    dual approval from the PM business owner and technical owner, with
    reason, evidence, timestamp, and affected baseline or gate
    recorded.``

    The check is hard: a single missing approver returns False. ``None``
    / empty override records return False.
    """
    if not override_record:
        return False
    approvals = override_record.get("approvals")
    if not isinstance(approvals, list) or not approvals:
        return False
    seen_roles: set[str] = set()
    for entry in approvals:
        if not isinstance(entry, Mapping):
            continue
        role = entry.get("actor_role")
        if isinstance(role, str):
            seen_roles.add(role)
    return REQUIRED_OVERRIDE_ROLES.issubset(seen_roles)


def assert_override_approved(override_record: Mapping[str, Any]) -> None:
    """Raise :class:`PolicyViolation` if the override is missing dual sign-off."""
    if not is_override_approved(override_record):
        raise PolicyViolation(
            "override requires dual approval from PM business owner "
            "and technical owner",
            environment="n/a",
            violations=["missing_dual_approval"],
            sample_id=str(override_record.get("override_id") or ""),
        )


__all__ = [
    "FORBIDDEN_PRODUCTION_KEYS",
    "PolicyViolation",
    "RedactionResult",
    "REQUIRED_OVERRIDE_ROLES",
    "assert_override_approved",
    "context_for_environment",
    "enforce_export_policy",
    "find_forbidden_keys",
    "is_override_approved",
    "prepare_export_payload",
    "safe_prepare_export_payload",
]