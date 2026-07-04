"""REQ-044 US1 — admin_console.decision_signals sub-module.

Exposes:

- :mod:`app.modules.admin_console.decision_signals.schemas` — Pydantic v2
  models for ``DecisionSignal`` (FR-008) + 4-tier ``confidence`` enum
  (FR-009) + list response envelope.
- :mod:`app.modules.admin_console.decision_signals.service` — pure
  orchestration: returns a prioritized list of DecisionSignals by
  ``(priority desc, freshness_at desc)``.
- :mod:`app.modules.admin_console.decision_signals.api` — FastAPI
  router mounted at ``/api/v1/admin-console/command-center``.

Auth: capability check via :func:`app.modules.admin_console.auth.require_capability`
or the PM role resolver (stub for now, real RBAC lands in REQ-044 US6).

[CROSS-TEAM-DEBT] Phase 2 batch 2 will replace ``seed_demo_signals`` with
a real aggregator that reads the 6 pm_dashboard panels (overview /
funnel / resume-diagnosis / mock-interview / ai-operations /
version-experiment) and translates metric deltas into DecisionSignals.
For US1 we ship the static seed so the PM-facing surface is verifiable
end-to-end without seeding real metric data.
"""
from __future__ import annotations

from app.modules.admin_console.decision_signals import api, schemas, service
from app.modules.admin_console.decision_signals.api import router

__all__ = [
    "api",
    "router",
    "schemas",
    "service",
]