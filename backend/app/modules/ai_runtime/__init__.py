"""REQ-061 — AI Runtime control plane.

Canonical module for AI task orchestration: tasks, executions, events,
capability adapters, recovery, and projections. This package is the
single source of truth for AI lifecycle state and audit evidence.
"""

from app.modules.ai_runtime.execution_context import (
    ExecutionContext,
    build_execution_context,
)

MODULE_NAME = "ai_runtime"
VERSION = "0.1.0"

__all__ = [
    "MODULE_NAME",
    "VERSION",
    "ExecutionContext",
    "build_execution_context",
]
