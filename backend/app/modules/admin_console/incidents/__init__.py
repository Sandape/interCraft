"""REQ-044 US4 — Incidents & Badcases workspace (FR-021~FR-023 业务层).

Module surface:

- :mod:`schemas` — Pydantic v2 models for incidents / badcases / evidence
  links / comments / audit trail.
- :mod:`service` — seed + list + get + evidence + comment + status change
  + badcase escalate orchestration.
- :mod:`api` — FastAPI router mounted at
  ``/api/v1/admin-console/incidents`` + ``/api/v1/admin-console/badcases``.

[CROSS-TEAM-DEBT] Real incident persistence lands in Phase 2 batch 4
together with governance US6 audit. Until then all incidents and
badcases are seed-driven (in-memory) and the audit trail is the
``admin_console.audit._AUDIT_LOG`` ring buffer (US1 baseline).
"""
from app.modules.admin_console.incidents import service
from app.modules.admin_console.incidents.api import (
    badcases_router,
    incidents_router,
    operational_badcases_router,
)

__all__ = [
    "badcases_router",
    "incidents_router",
    "operational_badcases_router",
    "service",
]
