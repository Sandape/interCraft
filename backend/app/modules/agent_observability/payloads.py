from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID


SECRET_KEYS = {
    "authorization",
    "api_key",
    "apikey",
    "access_token",
    "refresh_token",
    "token",
    "cookie",
    "password",
    "secret",
    "private_key",
}


class PayloadRevealDenied(PermissionError):
    pass


class PayloadRevealExpired(PermissionError):
    pass


@dataclass
class PayloadRevealRequest:
    payload_id: UUID
    actor_id: UUID
    role_labels: set[str]
    capabilities: set[str]
    reason: str
    now: datetime
    retention_expires_at: datetime
    visibility_mode: str = "masked_raw"


@dataclass(frozen=True)
class PayloadRevealDecision:
    allowed: bool
    visibility_mode: str


def _value_shape(value: Any) -> str:
    if isinstance(value, list):
        return f"array[{len(value)}]"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return "number"
    if value is None:
        return "null"
    return "string"


def summarize_shape(payload: Any) -> dict[str, str] | str:
    if isinstance(payload, dict):
        return {str(key): _value_shape(value) for key, value in payload.items()}
    return _value_shape(payload)


def mask_sensitive_payload(payload: Any) -> Any:
    if isinstance(payload, list):
        return [mask_sensitive_payload(item) for item in payload]
    if not isinstance(payload, dict):
        return payload

    out: dict[str, Any] = {}
    role = str(payload.get("role", "")).lower()
    for key, value in payload.items():
        key_norm = str(key).lower()
        if key_norm in SECRET_KEYS or any(secret in key_norm for secret in SECRET_KEYS):
            out[key] = "[MASKED_SECRET]"
        elif key_norm == "content" and role == "system":
            out[key] = "[MASKED_SYSTEM_PROMPT]"
        elif key_norm == "content" and role == "user":
            out[key] = "[MASKED_USER_TEXT]"
        elif key_norm == "content" and role == "assistant":
            out[key] = "[MASKED_MODEL_OUTPUT]"
        else:
            out[key] = mask_sensitive_payload(value)
    return out


def can_reveal_masked_raw(request: PayloadRevealRequest) -> PayloadRevealDecision:
    roles = {role.lower() for role in request.role_labels}
    capabilities = {cap.upper() for cap in request.capabilities}
    if "MASKED_RAW_VIEW" not in capabilities:
        raise PayloadRevealDenied("missing MASKED_RAW_VIEW capability")
    if not roles.intersection({"developer", "reviewer"}):
        raise PayloadRevealDenied("masked raw requires developer or reviewer role")
    if not request.reason.strip():
        raise PayloadRevealDenied("masked raw reveal requires a reason")
    if request.retention_expires_at <= request.now:
        raise PayloadRevealExpired("masked raw payload has expired")
    return PayloadRevealDecision(allowed=True, visibility_mode="masked_raw")


__all__ = [
    "PayloadRevealDecision",
    "PayloadRevealDenied",
    "PayloadRevealExpired",
    "PayloadRevealRequest",
    "can_reveal_masked_raw",
    "mask_sensitive_payload",
    "summarize_shape",
]
