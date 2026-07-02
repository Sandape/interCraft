"""REQ-038 US1 P1 — LLM Structured Output Hardening.

Public API surface (per ac-matrix AC-000):
    - with_structured_output: registry entry callable
    - parse_structured_output: client wrapper callable
    - StructuredOutputError: errors module callable
    - STRUCTURED_NODES: registry list of node IDs
    - Schema: schemas module type root

[ac-completed: AC-000]
"""
from app.agents.structured_output.client import (
    parse_structured_output,
    with_structured_output,
)
from app.agents.structured_output.errors import (
    OutOfBounds,
    ParseFail,
    Quota,
    SchemaInvalid,
    StructuredOutputError,
    Timeout,
)
from app.agents.structured_output.registry import (
    NODE_SCHEMAS,
    STRUCTURED_NODES,
)
from app.agents.structured_output.schemas import Schema

__all__ = [
    "with_structured_output",
    "parse_structured_output",
    "StructuredOutputError",
    "SchemaInvalid",
    "ParseFail",
    "Timeout",
    "Quota",
    "OutOfBounds",
    "STRUCTURED_NODES",
    "NODE_SCHEMAS",
    "Schema",
]