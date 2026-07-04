"""REQ-039 B1 + REQ-044 US1 + US2 + US3 — admin_console module public surface.

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
- :mod:`app.modules.admin_console.decision_signals` — REQ-044 US1
  sub-module that exposes the command-center decision queue
  (``DecisionSignal`` schemas, service, router mounted at
  ``/api/v1/admin-console/command-center``).
- :mod:`app.modules.admin_console.product_analytics` — REQ-044 US2
  sub-module that exposes the Product Analytics workspace
  (``QuestionTemplate`` / ``Funnel`` / ``Cohort`` / ``FeatureAdoption``
  schemas, service, router mounted at
  ``/api/v1/admin-console/product-analytics`` plus
  ``/api/v1/admin-console/users`` for privacy-safe lookup).
- :mod:`app.modules.admin_console.auth` — capability check helpers
  (``require_capability``).
- :mod:`app.modules.admin_console.rate_limit` — sliding-window
  in-process limiter for Replay (≤5/min) and Diff (≤20/min).
- :mod:`app.modules.admin_console.audit` — append-only audit log
  writer.

The observability router is exported as ``router``; the
command-center router is exported as ``decision_signals_router``; the
product-analytics routers are exported as
``product_analytics_router`` + ``users_router``. All four are included
by :func:`app.main.create_app`.
"""
from __future__ import annotations

from app.modules.admin_console import (
    ai_operations,
    api,
    audit,
    auth,
    decision_signals,
    models,
    product_analytics,
    rate_limit,
    repository,
    schemas,
    service,
)
from app.modules.admin_console.ai_operations import router as ai_operations_router
from app.modules.admin_console.api import router
from app.modules.admin_console.decision_signals import router as decision_signals_router
from app.modules.admin_console.product_analytics import (
    product_analytics_router,
    users_router,
)

__all__ = [
    "ai_operations",
    "ai_operations_router",
    "api",
    "audit",
    "auth",
    "decision_signals",
    "decision_signals_router",
    "models",
    "product_analytics",
    "product_analytics_router",
    "rate_limit",
    "repository",
    "router",
    "schemas",
    "service",
    "users_router",
]