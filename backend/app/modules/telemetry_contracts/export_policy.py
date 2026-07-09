"""Destination-aware export policy for REQ-045."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.eval.schemas import (
    Environment,
    ExportDestination,
    ExportPolicyDecisionRecord,
    RepresentationLevel,
)

SECRET_KEY_HINTS = frozenset(
    {
        "authorization",
        "api_key",
        "apikey",
        "secret",
        "password",
        "token",
        "cookie",
        "credential",
    }
)


@dataclass(frozen=True)
class SecretScanResult:
    paths: tuple[str, ...] = ()

    @property
    def has_secret(self) -> bool:
        return bool(self.paths)


@dataclass(frozen=True)
class DestinationPolicyInput:
    destination: ExportDestination
    environment: Environment
    requested_level: RepresentationLevel
    policy_version: str = "req045.v1"
    owner: str | None = None
    access_scope: str | None = None
    retention_days: int | None = None
    allowed_content_classes: tuple[str, ...] = ()
    sample_rate: float = 1.0
    payload: Any | None = None


@dataclass(frozen=True)
class DestinationPolicyResult:
    decision: ExportPolicyDecisionRecord
    secret_scan: SecretScanResult = field(default_factory=SecretScanResult)

    @property
    def allowed(self) -> bool:
        return self.decision.representation_level != RepresentationLevel.BLOCKED

    def to_payload(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "decision": _decision_to_payload(self.decision),
            "secretPaths": list(self.secret_scan.paths),
        }


def scan_for_operational_secrets(payload: Any) -> SecretScanResult:
    paths: list[str] = []

    def visit(value: Any, path: str) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                key_norm = str(key).lower()
                child_path = f"{path}.{key}" if path else str(key)
                if any(hint in key_norm for hint in SECRET_KEY_HINTS):
                    paths.append(child_path)
                    continue
                visit(child, child_path)
            return
        if isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, f"{path}[{index}]")
            return
        if isinstance(value, str):
            lowered = value.lower()
            if lowered.startswith("bearer ") or lowered.startswith("sk-"):
                paths.append(path or "$")

    visit(payload, "")
    return SecretScanResult(tuple(sorted(set(paths))))


def _missing_full_content_metadata(input_: DestinationPolicyInput) -> list[str]:
    missing = [
        name
        for name, value in (
            ("owner", input_.owner),
            ("access_scope", input_.access_scope),
            ("retention_days", input_.retention_days),
            ("policy_version", input_.policy_version),
        )
        if value in (None, "")
    ]
    if not input_.allowed_content_classes:
        missing.append("allowed_content_classes")
    return missing


def _blocked_decision(
    input_: DestinationPolicyInput,
    *,
    reason: str,
) -> ExportPolicyDecisionRecord:
    return ExportPolicyDecisionRecord(
        destination=input_.destination,
        environment=input_.environment,
        representation_level=RepresentationLevel.BLOCKED,
        policy_version=input_.policy_version,
        owner=input_.owner,
        access_scope=input_.access_scope,
        retention_days=input_.retention_days,
        allowed_content_classes=list(input_.allowed_content_classes),
        blocked_reason=reason,
        sample_rate=input_.sample_rate,
    )


def _decision_to_payload(decision: ExportPolicyDecisionRecord) -> dict[str, Any]:
    payload = decision.model_dump(mode="json")
    return {
        "decisionId": payload["decision_id"],
        "destination": payload["destination"],
        "environment": payload["environment"],
        "representationLevel": payload["representation_level"],
        "policyVersion": payload["policy_version"],
        "owner": payload.get("owner"),
        "accessScope": payload.get("access_scope"),
        "retentionDays": payload.get("retention_days"),
        "allowedContentClasses": payload.get("allowed_content_classes", []),
        "blockedReason": payload.get("blocked_reason"),
        "sampleRate": payload.get("sample_rate"),
        "createdAt": payload.get("created_at"),
        "secretClassesBlocked": payload.get("secret_classes_blocked"),
    }


def decide_export_policy(input_: DestinationPolicyInput) -> DestinationPolicyResult:
    secret_scan = scan_for_operational_secrets(input_.payload)
    if secret_scan.has_secret:
        decision = _blocked_decision(input_, reason="operational_secret_detected")
        return DestinationPolicyResult(decision=decision, secret_scan=secret_scan)

    level = input_.requested_level
    full_prod_langsmith = (
        input_.destination == ExportDestination.LANGSMITH
        and input_.environment == Environment.PRODUCTION
        and level == RepresentationLevel.FULL_CONTENT
    )
    if full_prod_langsmith:
        missing = _missing_full_content_metadata(input_)
        if missing:
            return DestinationPolicyResult(
                decision=_blocked_decision(
                    input_,
                    reason="missing_full_content_policy_metadata:" + ",".join(missing),
                ),
                secret_scan=secret_scan,
            )
    if input_.destination == ExportDestination.OTLP_GENERIC and level == RepresentationLevel.FULL_CONTENT:
        level = RepresentationLevel.REDACTED
    if input_.destination == ExportDestination.LOCAL_ARTIFACT:
        level = input_.requested_level

    decision = ExportPolicyDecisionRecord(
        destination=input_.destination,
        environment=input_.environment,
        representation_level=level,
        policy_version=input_.policy_version,
        owner=input_.owner,
        access_scope=input_.access_scope,
        retention_days=input_.retention_days,
        allowed_content_classes=list(input_.allowed_content_classes),
        sample_rate=input_.sample_rate,
    )
    return DestinationPolicyResult(decision=decision, secret_scan=secret_scan)


__all__ = [
    "DestinationPolicyInput",
    "DestinationPolicyResult",
    "SECRET_KEY_HINTS",
    "SecretScanResult",
    "decide_export_policy",
    "scan_for_operational_secrets",
]
