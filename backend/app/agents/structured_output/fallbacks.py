"""REQ-038 US1 P1 — Fallback strategy configuration.

The strategy is *consumed* by ``client.parse_structured_output`` (see
client.py), not just declared. AC-007 asserts the field is snake_case
exact and that ``client.py`` references it >= 3 times.

[ac-completed: AC-007]
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# snake_case exact, 3 literal values locked at ac-matrix AC-007.
FallbackStrategy = Literal["retry", "use_previous", "hard_fail"]


class NodeConfig(BaseModel):
    """Per-node runtime configuration.

    `fallback_strategy` decides what `parse_structured_output` does when
    validation fails:

        retry         — re-invoke the LLM (default; safe)
        use_previous  — return the last cached validated output if any
        hard_fail     — raise StructuredOutputError immediately
    """

    fallback_strategy: Literal["retry", "use_previous", "hard_fail"] = Field(
        default="retry",
        description="Action taken when LLM output fails structured validation.",
    )
    max_retries: int = Field(default=2, ge=0, le=10)


__all__ = ["NodeConfig", "FallbackStrategy"]