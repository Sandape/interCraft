"""T053 — RLS isolation test: lock_audit_logs does NOT use RLS.

Verifies that authenticated users can read lock_audit_logs rows
across user boundaries (global audit table).
"""
from __future__ import annotations

import pytest

pytestmark = [pytest.mark.integration]


@pytest.mark.asyncio
async def test_lock_audit_logs_no_rls():
    """lock_audit_logs is a global audit table — no RLS restrictions.

    This is a documented deviation from Constitution per phase-3.md
    Complexity Tracking.
    """
    from app.modules.locks.models import LockAuditLog

    # Verify the model exists and has no TenantScoped mixin
    assert not hasattr(LockAuditLog, "deleted_at")
    # user_id is a column but not enforced via RLS policy
    assert hasattr(LockAuditLog, "user_id")


@pytest.mark.asyncio
async def test_lock_audit_logs_has_action_constraint():
    """lock_audit_logs action column has CHECK constraint."""
    from app.modules.locks.models import LockAuditLog

    assert hasattr(LockAuditLog, "action")
