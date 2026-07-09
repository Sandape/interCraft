from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from app.modules.agent_observability.payloads import SECRET_KEYS


@dataclass(frozen=True)
class SafeCurl:
    curl: str
    redacted_headers: list[str]


def _contains_secret_key(key: str) -> bool:
    lowered = key.lower()
    return lowered in SECRET_KEYS or any(secret in lowered for secret in SECRET_KEYS)


def _redact_body(value: Any) -> Any:
    if isinstance(value, list):
        return [_redact_body(item) for item in value]
    if isinstance(value, dict):
        return {
            key: ("[REDACTED_SECRET]" if _contains_secret_key(str(key)) else _redact_body(item))
            for key, item in value.items()
        }
    return value


def _single_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


def build_safe_curl(
    *,
    method: str,
    base_url: str,
    endpoint: str,
    headers: dict[str, str],
    body: Any,
    provider: str,
    model: str,
    trace_id: str,
    attempt: int,
) -> SafeCurl:
    redacted_headers: list[str] = []
    header_parts: list[str] = []
    for key, value in headers.items():
        del value
        key_norm = key.lower()
        if key_norm == "authorization":
            redacted_headers.append(key)
            header_parts.append("-H " + _single_quote("Authorization: Bearer $PROVIDER_API_KEY"))
        elif key_norm == "cookie":
            redacted_headers.append(key)
            continue
        elif _contains_secret_key(key):
            redacted_headers.append(key)
            header_parts.append("-H " + _single_quote(f"{key}: [REDACTED_SECRET]"))
        else:
            header_parts.append("-H " + _single_quote(f"{key}: {headers[key]}"))

    safe_body = _redact_body(body)
    body_json = json.dumps(safe_body, ensure_ascii=False, separators=(",", ":"))
    url = base_url.rstrip("/") + "/" + endpoint.lstrip("/")
    comment = f"# trace_id={trace_id} provider={provider} model={model} attempt={attempt}"
    curl = " ".join(
        [
            "curl",
            "-X",
            method.upper(),
            _single_quote(url),
            *header_parts,
            "-d",
            _single_quote(body_json),
            comment,
        ]
    )
    return SafeCurl(curl=curl, redacted_headers=redacted_headers)


__all__ = ["SafeCurl", "build_safe_curl"]
