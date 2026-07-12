"""REQ-061 T170 — prefer explicit unavailable over seed/demo fallbacks."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any


_ENV = "AI_OPS_DISABLE_SEED_FALLBACKS"


def seed_fallbacks_disabled() -> bool:
    raw = (os.environ.get(_ENV) or "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def unavailable_payload(*, surface: str, reason: str = "projection_unavailable") -> dict[str, Any]:
    return {
        "available": False,
        "surface": surface,
        "reason": reason,
        "freshness_at": None,
        "generated_at": datetime.now(UTC).isoformat(),
        "items": [],
        "seed": False,
    }


__all__ = ["seed_fallbacks_disabled", "unavailable_payload"]
