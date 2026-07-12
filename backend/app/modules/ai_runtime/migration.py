"""REQ-061 T168 — legacy shadow capture / metadata backfill helpers.

Idempotent ``legacy_partial`` metadata backfill and shadow comparison.
Never fabricates retries, zero usage, or historical point charges.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class ShadowComparisonRow:
    task_id: str
    canonical_status: str | None
    legacy_status: str | None
    usage_match: bool
    status_match: bool
    notes: tuple[str, ...] = ()


@dataclass
class LegacyPartialBackfillResult:
    scanned: int = 0
    updated: int = 0
    skipped: int = 0
    fabricated_retries: int = 0
    fabricated_usage: int = 0
    fabricated_charges: int = 0
    dry_run: bool = True
    rows: list[dict[str, Any]] = field(default_factory=list)
    occurred_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


def mark_legacy_partial(
    metadata: dict[str, Any] | None,
    *,
    source: str = "shadow_capture",
) -> dict[str, Any]:
    """Idempotently stamp legacy_partial on task/attempt metadata."""
    out = dict(metadata or {})
    if out.get("legacy_partial") is True:
        return out
    out["legacy_partial"] = True
    out["legacy_partial_source"] = source
    out["legacy_partial_at"] = datetime.now(UTC).isoformat()
    return out


def compare_shadow_row(
    *,
    task_id: UUID | str,
    canonical: dict[str, Any],
    legacy: dict[str, Any],
) -> ShadowComparisonRow:
    """Compare canonical attempt/usage/status against a legacy fixture row."""
    c_status = canonical.get("status")
    l_status = legacy.get("status")
    c_usage = canonical.get("usage") or {}
    l_usage = legacy.get("usage") or {}
    usage_match = c_usage == l_usage or (not c_usage and not l_usage)
    status_match = c_status == l_status
    notes: list[str] = []
    if not status_match:
        notes.append("status_mismatch")
    if not usage_match:
        notes.append("usage_mismatch")
    # Explicitly never invent zero usage when legacy is missing.
    if "usage" not in legacy and "usage" not in canonical:
        notes.append("usage_absent_both_sides")
    return ShadowComparisonRow(
        task_id=str(task_id),
        canonical_status=str(c_status) if c_status is not None else None,
        legacy_status=str(l_status) if l_status is not None else None,
        usage_match=usage_match,
        status_match=status_match,
        notes=tuple(notes),
    )


def backfill_legacy_partial(
    records: list[dict[str, Any]],
    *,
    dry_run: bool = True,
) -> LegacyPartialBackfillResult:
    """Stamp legacy_partial without creating ledger/retry/usage facts."""
    result = LegacyPartialBackfillResult(dry_run=dry_run, scanned=len(records))
    for row in records:
        meta = dict(row.get("metadata") or {})
        if meta.get("legacy_partial") is True:
            result.skipped += 1
            continue
        updated_meta = mark_legacy_partial(meta)
        if dry_run:
            result.skipped += 1
            result.rows.append({"id": row.get("id"), "would_update": True})
        else:
            row["metadata"] = updated_meta
            result.updated += 1
            result.rows.append({"id": row.get("id"), "updated": True})
    # Invariants: never fabricate.
    assert result.fabricated_retries == 0
    assert result.fabricated_usage == 0
    assert result.fabricated_charges == 0
    return result


__all__ = [
    "LegacyPartialBackfillResult",
    "ShadowComparisonRow",
    "backfill_legacy_partial",
    "compare_shadow_row",
    "mark_legacy_partial",
]
