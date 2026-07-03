"""REQ-038 US3 — Structured output observability hook.

``emit_structured_invocation_event`` is the single hook called by
``parse_structured_output`` / ``with_structured_output`` after every
invocation (success, validation failure, fallback). It:

- Emits a structlog event ``structured_invocation`` with the full payload.
- Increments the Prometheus ``structured_invocation_total`` counter.
- Redacts PII from input/output summaries before persistence.

[ac-completed: AC-001, AC-002, AC-003, AC-005]
"""
from __future__ import annotations

from typing import Any

import structlog

from app.agents.structured_output.errors import CategoryType
from app.core.metrics import structured_invocation_total
from app.modules.agent_memory.redactor import redact

logger = structlog.get_logger("structured_output.observability")

# Default provider path when no real provider is available.
_LOCAL_PROVIDER = "structured_output.local"
_DEFAULT_CONTRACT_VERSION = "v1"


def emit_structured_invocation_event(
    *,
    node: str | None,
    contract_name: str,
    contract_version: str = _DEFAULT_CONTRACT_VERSION,
    validation_status: str,
    failure_category: str | None = None,
    fallback_used: bool = False,
    retry_count: int = 0,
    provider_path: str = _LOCAL_PROVIDER,
    input_summary: str | None = None,
    output_summary: str | None = None,
) -> dict[str, Any]:
    """Emit a structured invocation observable event.

    Returns the payload dict for test assertions. Side effects:
    1. structlog event ``structured_invocation`` with the full payload.
    2. Prometheus ``structured_invocation_total`` counter +1.

    PII redaction: ``input_summary`` and ``output_summary`` are redacted
    before being included in the returned payload / log event.
    """
    # Redact PII before persistence (AC-005).
    redacted_input: str | None = None
    redacted_output: str | None = None
    if input_summary is not None:
        redacted_input, _ = redact(input_summary)
    if output_summary is not None:
        redacted_output, _ = redact(output_summary)

    payload: dict[str, Any] = {
        "node": node,
        "contract_name": contract_name,
        "contract_version": contract_version,
        "validation_status": validation_status,
        "failure_category": failure_category,
        "fallback_used": fallback_used,
        "retry_count": retry_count,
        "provider_path": provider_path,
    }
    # Include redacted summaries if provided (used by AC-005).
    if redacted_input is not None:
        payload["input_summary"] = redacted_input
    if redacted_output is not None:
        payload["output_summary"] = redacted_output

    # Emit structlog event.
    logger.info("structured_invocation", **payload)

    # Increment Prometheus counter (AC-003).
    # Labels: node, contract, status, failure_category, fallback_used
    structured_invocation_total.labels(
        node=str(node or "unknown"),
        contract=contract_name,
        status=validation_status,
        failure_category=failure_category or "",
        fallback_used=str(fallback_used).lower(),
    ).inc()

    return payload


__all__ = ["emit_structured_invocation_event"]
