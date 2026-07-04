"""REQ-044 US3 — admin_console.ai_operations sub-module.

Exposes:

- :mod:`app.modules.admin_console.ai_operations.schemas` — Pydantic v2
  models for ``KPIBundle`` (FR-016) + ``VolumeByFeature`` +
  ``FailureCategoryBreakdown`` + ``LatencyBands`` + ``TokenUsage`` +
  ``CostSummary`` + ``VersionSelectorChoice`` (FR-017) +
  ``AIQualityIssue`` (FR-018) + ``CostQualityFlag`` (FR-019) +
  ``EvalBadcaseSummary`` (FR-020).
- :mod:`app.modules.admin_console.ai_operations.service` — pure
  orchestration: returns 9 endpoints' worth of payload via 9 seed
  helpers.
- :mod:`app.modules.admin_console.ai_operations.api` — FastAPI router
  mounted at ``/api/v1/admin-console/ai-operations`` exposing the 9
  endpoints.

Auth: capability check via :func:`app.modules.admin_console.auth.require_capability`
with the new ``AI_OPERATIONS_VIEW`` capability token (added in this US
to ``admin_console.auth``). The default role map grants this to
``pm``, ``owner``, ``admin``, ``operations``, and ``maintainer``.

[CROSS-TEAM-DEBT] Phase 2 batch 3 will replace ``seed_demo_*`` with a
real aggregator that reads AIInvocationRecord + eval_results +
badcases tables (REQ-033 pm_dashboard ``ai-operations`` + REQ-026
``eval`` + REQ-033 ``badcases``) and translates them into KPI / volume
/ failure / latency / cost summaries. For US3 we ship the static seed
so the PM-facing surface is verifiable end-to-end without seeding
real metric data.
"""
from __future__ import annotations

from app.modules.admin_console.ai_operations import api, schemas, service
from app.modules.admin_console.ai_operations.api import router

__all__ = [
    "api",
    "router",
    "schemas",
    "service",
]
