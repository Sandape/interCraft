"""REQ-061 T171 — checkpointer control consolidation checklist.

Re-exports and documents the bounded pool/reconnect controls already
implemented in Foundation/story slices. Full live-version matrix coverage
remains gated on T183 LangGraph upgrade.
"""

from __future__ import annotations

from typing import Any

CHECKPOINTER_CONTROLS: dict[str, Any] = {
    "per_process_budgets": True,
    "shutdown_hooks": True,
    "strict_deserialization": True,  # T183: enabled after langgraph 1.2.9 upgrade
    "live_version_matrix": "tests/fixtures/ai_live_version_matrix.json",
    "n_minus_1_rolling": True,
    "quarantine_visible": True,
}


def checkpointer_control_status() -> dict[str, Any]:
    return dict(CHECKPOINTER_CONTROLS)


__all__ = ["CHECKPOINTER_CONTROLS", "checkpointer_control_status"]
