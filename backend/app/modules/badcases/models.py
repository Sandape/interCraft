"""REQ-033 / REQ-061 Bad Case ORM surface.

Re-exports production ORM classes from ``telemetry_contracts.models``
(aligned with migrations 0024 + 0060) so callers can import from
``app.modules.badcases.models``.
"""
from __future__ import annotations

from app.modules.telemetry_contracts.models import (
    Badcase as _Badcase,
    BadcaseClosureEvidence as _BadcaseClosureEvidence,
    BadcaseContentAuthorization as _BadcaseContentAuthorization,
    BadcaseImpactLink as _BadcaseImpactLink,
    BadcaseReviewAction as _BadcaseReviewAction,
)

Badcase = _Badcase
BadcaseReviewAction = _BadcaseReviewAction
BadcaseImpactLink = _BadcaseImpactLink
BadcaseContentAuthorization = _BadcaseContentAuthorization
BadcaseClosureEvidence = _BadcaseClosureEvidence

__all__ = [
    "Badcase",
    "BadcaseClosureEvidence",
    "BadcaseContentAuthorization",
    "BadcaseImpactLink",
    "BadcaseReviewAction",
]
