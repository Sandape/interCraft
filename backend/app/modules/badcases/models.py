"""REQ-033 US8 — badcase SQLAlchemy ORM models shim (T058).

The actual ORM classes live in
``app.modules.telemetry_contracts.models`` because the FOUNDATION phase
(T020) consolidated all 033 tables into one module to keep the
persistence layer co-located. This shim re-exports the badcase models
under the ``app.modules.badcases`` namespace so callers that import
``from app.modules.badcases.models import Badcase, BadcaseReviewAction``
work without surprising the model layout.

Schema source of truth: ``migrations/versions/0024_033_eval_pm_dashboard.py``.
Tables:

- ``badcases`` — main record. RLS: per-user (FORCE ROW LEVEL SECURITY).
- ``badcase_review_actions`` — append-only audit log. RLS: per-user via
  EXISTS sub-select against ``badcases`` (see migration 0024).
"""
from __future__ import annotations

from app.modules.telemetry_contracts.models import (
    Badcase as _Badcase,
    BadcaseReviewAction as _BadcaseReviewAction,
)

Badcase = _Badcase
BadcaseReviewAction = _BadcaseReviewAction

__all__ = ["Badcase", "BadcaseReviewAction"]