"""REQ-051 — admin console models contract test (simplified)."""
from __future__ import annotations

from app.core.db import Base
from app.modules.admin_console.models import AdminAuditLog, TaskTag, Trace


def test_req051_admin_models_registered_in_base() -> None:
    """TaskTag, AdminAuditLog, and Trace are registered in Base.metadata."""
    tables = Base.metadata.tables.keys()
    assert "task_tags" in tables
    assert "admin_audit_log" in tables
    assert "traces" in tables


def test_task_tag_columns() -> None:
    """TaskTag has the required columns for RLS-isolated tagging."""
    cols = set(TaskTag.__table__.c.keys())
    assert {"task_id", "user_id", "tag", "created_at"}.issubset(cols)


def test_admin_audit_log_columns() -> None:
    """AdminAuditLog has the required audit columns."""
    cols = set(AdminAuditLog.__table__.c.keys())
    assert {"id", "user_id", "action", "target_kind", "target_id", "created_at"}.issubset(cols)


def test_trace_columns() -> None:
    """Trace read-only projection has required columns."""
    cols = set(Trace.__table__.c.keys())
    required = {"id", "task_id", "task_type", "prompt_version", "model", "status"}
    assert required.issubset(cols)
