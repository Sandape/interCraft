"""REQ-044 US2 — admin_console.product_analytics sub-module.

Exposes:

- :mod:`app.modules.admin_console.product_analytics.schemas` — Pydantic v2
  models for ``QuestionTemplate`` (FR-011) + ``FunnelStep`` (FR-012) +
  ``CohortSegment`` (FR-013) + ``FeatureAdoptionMetric`` (FR-014) +
  ``UserPrivacySafe`` (FR-015).
- :mod:`app.modules.admin_console.product_analytics.service` — pure
  orchestration: returns question templates, funnel rows, cohort list,
  feature adoption rows, and privacy-safe user lookup.
- :mod:`app.modules.admin_console.product_analytics.api` — FastAPI
  router mounted at ``/api/v1/admin-console/product-analytics`` + the
  user lookup router mounted at ``/api/v1/admin-console/users``.

Auth: capability check via :func:`app.modules.admin_console.auth.require_capability`
with the new ``PRODUCT_ANALYTICS_VIEW`` capability token (added in this
US to ``admin_console.auth``). The default role map grants this to
``pm``, ``owner``, ``admin``, ``operations``, and ``maintainer``.

[CROSS-TEAM-DEBT] Phase 2 batch 2 will replace ``seed_demo_*`` with a
real aggregator that reads the 6 pm_dashboard panels + cohort/snapshot
tables and translates metric deltas into Funnel/Cohort/Adoption rows.
For US2 we ship the static seed so the PM-facing surface is verifiable
end-to-end without seeding real metric data.
"""
from __future__ import annotations

from app.modules.admin_console.product_analytics import (
    api,
    schemas,
    service,
)
from app.modules.admin_console.product_analytics.api import (
    product_analytics_router,
    users_router,
)

__all__ = [
    "api",
    "product_analytics_router",
    "schemas",
    "service",
    "users_router",
]