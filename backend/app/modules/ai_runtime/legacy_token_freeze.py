"""REQ-061 T169 — legacy monthly token write freeze controls."""

from __future__ import annotations

import os

# When set to "1" / "true", direct monthly_token_used writes and monthly
# reset schedules are disabled after points cutover. Compatibility columns
# remain; they are simply no longer mutated.
_ENV = "AI_LEGACY_MONTHLY_TOKEN_WRITES_FROZEN"


def legacy_monthly_token_writes_frozen() -> bool:
    raw = (os.environ.get(_ENV) or "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def should_write_monthly_token_used() -> bool:
    return not legacy_monthly_token_writes_frozen()


__all__ = [
    "legacy_monthly_token_writes_frozen",
    "should_write_monthly_token_used",
]
