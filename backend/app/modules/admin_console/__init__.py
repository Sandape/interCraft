"""REQ-039 B1 — admin_console module public surface.

Module re-exports for the Log Center backend foundation (Batch 1).

The full admin console surface spans:

- :mod:`app.modules.admin_console.models` — ORM tables (``TaskTag``,
  ``AdminAuditLog``) and the ``Trace`` / ``TraceNode`` projection
  helpers.
- :mod:`app.modules.admin_console.schemas` — Pydantic v2 request /
  response schemas for the 7 endpoints (tag CRUD, replay, diff,
  payload pagination).
- :mod:`app.modules.admin_console.repository` — async DB helpers
  (RLS-aware).
- :mod:`app.modules.admin_console.service` — business logic (tag
  validation, replay trigger, diff compute, payload byte-range slicing,
  hash normalization).
- :mod:`app.modules.admin_console.api` — FastAPI router mounted at
  ``/api/v1/admin-console/observability``.
- :mod:`app.modules.admin_console.auth` — capability check helpers
  (``require_capability``).
- :mod:`app.modules.admin_console.rate_limit` — sliding-window
  in-process limiter for Replay (≤5/min) and Diff (≤20/min).
- :mod:`app.modules.admin_console.audit` — append-only audit log
  writer.

The router is exported so :func:`app.main.create_app` can include it
with the canonical ``/admin-console/observability`` prefix.
"""
from __future__ import annotations

from app.modules.admin_console import (
    api,
    audit,
    auth,
    models,
    rate_limit,
    repository,
    schemas,
    service,
)
from app.modules.admin_console.api import router

__all__ = [
    "api",
    "audit",
    "auth",
    "models",
    "rate_limit",
    "repository",
    "router",
    "schemas",
    "service",
]