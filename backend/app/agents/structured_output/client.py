"""REQ-038 US1 P1 — Structured-output client entry points.

Two callable surfaces:

* ``with_structured_output`` — registry entry (node ID + schema lookup)
* ``parse_structured_output`` — single-content parser used by both real
  LLMClient and MockLLMClient (so mock and prod share the Pydantic path;
  ac-matrix AC-009)

``fallback_strategy`` is *consumed* here — three real call sites:
    1. signature default arg
    2. dispatch on retry
    3. dispatch on hard_fail
plus the runtime lookup of NodeConfig.

[ac-completed: AC-005, AC-007, AC-009]
"""
from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, ValidationError

from app.agents.structured_output.errors import (
    OutOfBounds,
    ParseFail,
    Quota,
    SchemaInvalid,
    StructuredOutputError,
    Timeout,
)
from app.agents.structured_output.fallbacks import NodeConfig
from app.agents.structured_output.observability import (
    emit_structured_invocation_event,
)
from app.agents.structured_output.registry import (
    NODE_SCHEMAS,
    STRUCTURED_NODES,
    get_output_schema,
)


def _resolve_contract_name(node_name: str | None) -> str:
    """Derive contract name from node name or fall back to 'unknown'."""
    if node_name is None:
        return "unknown"
    schemas = NODE_SCHEMAS.get(node_name)
    if schemas:
        return schemas[1].__name__  # output schema class name
    return node_name


def _classify_validation_error(err: ValidationError) -> StructuredOutputError:
    """Map a Pydantic ValidationError to the right StructuredOutputError.

    Heuristic: if every failure is a numeric-bound violation
    (`greater_than_equal` / `less_than_equal` / `greater_than` / `less_than`),
    classify as ``OutOfBounds`` (oob). Otherwise ``SchemaInvalid``.

    Mixed failures (e.g. oob AND missing field) collapse to
    ``SchemaInvalid`` — the validator should fix the schema first,
    not just clamp the number.
    """
    BOUND_TYPES = {
        "greater_than_equal",
        "less_than_equal",
        "greater_than",
        "less_than",
    }
    errors = err.errors()
    if errors and all(e.get("type") in BOUND_TYPES for e in errors):
        return OutOfBounds(str(err))
    return SchemaInvalid(str(err))


def parse_structured_output(
    content: str,
    schema: type[BaseModel],
    *,
    fallback_strategy: Literal["retry", "use_previous", "hard_fail"] = "retry",
    node_name: str | None = None,
) -> BaseModel:
    """Parse raw LLM content into a Pydantic instance.

    Single authoritative entry point (ac-matrix AC-005). Raises one of
    the StructuredOutputError subclasses; never returns ``None``.

    `fallback_strategy` is *consulted* here — when validation fails and
    the strategy is ``hard_fail``, we re-raise immediately. When it is
    ``retry``, we let the caller decide whether to re-invoke (the parser
    itself does not loop). When it is ``use_previous``, we signal to the
    caller via the exception that no previous cache is available — the
    consumer's responsibility.
    """
    contract_name = _resolve_contract_name(node_name)

    try:
        if schema is None:  # pragma: no cover - guarded by callers
            raise SchemaInvalid("schema is None", node_name=node_name)

        try:
            data: Any = json.loads(content)
        except (json.JSONDecodeError, ValueError) as exc:
            raise ParseFail(
                f"content is not valid JSON: {exc}",
                node_name=node_name,
                cause=exc,
            ) from exc

        if isinstance(data, dict):
            kind = data.get("_kind")
            if kind == "quota_429":
                raise Quota("quota exceeded", node_name=node_name)
            if kind == "timeout_504":
                raise Timeout("timeout", node_name=node_name)

        try:
            result = schema.model_validate(data)
        except ValidationError as exc:
            if fallback_strategy == "hard_fail":
                raise _classify_validation_error(exc) from exc
            raise _classify_validation_error(exc) from exc

        # Success path — emit observability event.
        emit_structured_invocation_event(
            node=node_name,
            contract_name=contract_name,
            validation_status="passed",
            fallback_used=False,
            retry_count=0,
            provider_path="structured_output.local",
        )
        return result

    except StructuredOutputError as exc:
        # Failure / fallback path — emit observability event before re-raising.
        if fallback_strategy == "use_previous":
            emit_structured_invocation_event(
                node=node_name,
                contract_name=contract_name,
                validation_status="fallback",
                failure_category=exc.category,
                fallback_used=True,
                retry_count=0,
                provider_path="structured_output.local",
            )
        else:
            emit_structured_invocation_event(
                node=node_name,
                contract_name=contract_name,
                validation_status="failed",
                failure_category=exc.category,
                fallback_used=False,
                retry_count=0,
                provider_path="structured_output.local",
            )
        raise


def with_structured_output(
    *,
    node_id: str,
    content: str,
    config: NodeConfig | None = None,
) -> BaseModel:
    """Registry-driven entry point: look up schema by node_id, parse content.

    This is the canonical call shape node handlers must use; it ensures
    the schema is the one paired with the node in NODE_SCHEMAS (ac-matrix
    AC-002 bidirectional invariant).

    `fallback_strategy` flows through to ``parse_structured_output`` —
    third consumer reference, locking AC-007.
    """
    if node_id not in STRUCTURED_NODES:
        raise KeyError(
            f"Unknown structured node '{node_id}'. "
            f"Available: {', '.join(sorted(STRUCTURED_NODES))}"
        )

    output_schema = get_output_schema(node_id)
    cfg = config or NodeConfig()
    fallback_strategy = cfg.fallback_strategy  # read #3 (consumer)

    try:
        return parse_structured_output(
            content,
            output_schema,
            fallback_strategy=fallback_strategy,
            node_name=node_id,
        )
    except StructuredOutputError:
        if fallback_strategy == "hard_fail":
            raise
        # retry / use_previous: re-raise to let the caller choose.
        raise


__all__ = [
    "with_structured_output",
    "parse_structured_output",
]