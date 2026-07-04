"""REQ-044 US6 — Governance / Audit / Export / Retention workspace.

Module surface:

- :mod:`schemas` — Pydantic v2 models for access matrix, reveal request,
  audit event, export, retention policy, data status.
- :mod:`repository` — in-memory seed for access matrix 5x8x6, reveal
  request buffer, audit event buffer, retention policy map, retention
  cache (EC-3 invalidation target).
- :mod:`service` — orchestration: access matrix render, reveal
  request create + audit, audit list, export create + audit, retention
  policy get/put + cache invalidation + self-audit (EC-4).
- :mod:`api` — FastAPI router mounted at
  ``/api/v1/admin-console/governance``.

[CROSS-TEAM-DEBT] Real governance DB lands in Phase 2 batch 5 with
DB-backed RBAC matrix + audit log + retention scheduler. Until then
all governance state is seed-driven and the audit event write-behind
is the in-memory :data:`governance.repository._AUDIT_LOG` ring buffer.
"""
from app.modules.admin_console.governance import repository, service
from app.modules.admin_console.governance.api import governance_router

__all__ = ["governance_router", "repository", "service"]
