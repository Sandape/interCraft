"""REQ-044 US7 — Review Snapshots service layer (FR-027~FR-030 + Edge Cases).

Pure orchestration: generates a snapshot from seed values + writes the
audit event (FR-029 + FR-034), returns the snapshot with frozen + live
delta (FR-030 + AC-30.1/30.3), and enforces snapshot immutability
(AC-30.4 — there is no update/delete helper).

Functions:

- :func:`generate_snapshot` — POST /review-snapshots (FR-029 AC-29.1).
  Validates filters (EC-3 expired payload rejection). Computes
  frozen + current values from seed. Writes audit event. Returns
  ReviewSnapshotResponse.
- :func:`list_snapshots` — GET /review-snapshots (FR-029).
- :func:`get_snapshot_with_delta` — GET /review-snapshots/{id}
  (FR-030 AC-30.1). Re-computes current_values (simulating late-
  arriving data) and emits EC-1 late_arriving_warnings when current
  differs from frozen.
- :func:`assert_snapshot_immutable` — AC-30.4 guard for the explicit
  PUT/PATCH/DELETE 405 handlers. Raises :class:`SnapshotImmutableError`.

Audit write order is locked by AC-29.2: the helper
:func:`_write_snapshot_audit` is invoked BEFORE the snapshot is
returned so the caller can prove the audit-trail invariant.

[CROSS-TEAM-DEBT] Real review_snapshot DB lands in Phase 2 batch 5.
Until then all state is in-process + seed-driven.
"""
from __future__ import annotations

import threading
from datetime import UTC, datetime, timedelta
from typing import Any

from app.modules.admin_console.governance.repository import (
    append_audit_event,
    next_audit_event_id,
)
from app.modules.admin_console.governance.schemas import (
    DataStatus,
    WorkspaceId,
)
from app.modules.admin_console.review_snapshots import repository
from app.modules.admin_console.review_snapshots.schemas import (
    ComparisonDelta,
    CurrentValue,
    EvidenceLink,
    FrozenValue,
    MetricDefinition10Field,
    ReviewSnapshotFormat,
    ReviewSnapshotListResponse,
    ReviewSnapshotResponse,
)

_lock = threading.Lock()

#: Reused from US6 governance — DO NOT redeclare.
EXPORT_FIELDS_REDACTED: list[str] = [
    "raw_resume",
    "raw_interview_answer",
    "raw_prompt",
    "raw_model_output",
]


def _now_iso() -> str:
    return (
        datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    )


# ---------------------------------------------------------------------------
# EC-3 — Expired payloads rejection (mirror US6 ExportBlockedError)
# ---------------------------------------------------------------------------


class SnapshotBlockedError(Exception):
    """Raised when a snapshot request includes expired sensitive payloads (EC-3).

    Mirrors US6 :class:`admin_console.governance.service.ExportBlockedError`
    so the API layer returns the same 422 shape.
    """

    def __init__(self, expired_record_ids: list[str]):
        self.expired_record_ids = expired_record_ids
        super().__init__(
            f"snapshot blocked: {len(expired_record_ids)} expired records"
        )


# ---------------------------------------------------------------------------
# AC-30.4 — Snapshot immutability guard
# ---------------------------------------------------------------------------


class SnapshotImmutableError(Exception):
    """Raised when PUT / PATCH / DELETE is attempted on a snapshot.

    AC-30.4: snapshots are immutable. The API layer maps this to 405.
    """

    def __init__(self, snapshot_id: str):
        self.snapshot_id = snapshot_id
        super().__init__(f"snapshot {snapshot_id} is immutable (FR-030)")


def assert_snapshot_immutable(snapshot_id: str) -> None:
    """Raise :class:`SnapshotImmutableError` unconditionally.

    Per AC-30.4 the API layer invokes this on every PUT/PATCH/DELETE
    attempt BEFORE consulting the buffer (the buffer has no
    update/delete helpers, but we lock the invariant here too).
    """
    raise SnapshotImmutableError(snapshot_id)


# ---------------------------------------------------------------------------
# FR-029 / AC-29.1 — generate snapshot
# ---------------------------------------------------------------------------


def _expired_record_ids_for_filters(filters: dict[str, Any]) -> list[str]:
    """Return expired record ids from the filters dict (EC-3 detector)."""
    expired = filters.get("expired_record_ids")
    if isinstance(expired, list):
        return [str(x) for x in expired]
    return []


def _metric_def_for_workspace(workspace: WorkspaceId) -> list[MetricDefinition10Field]:
    """Return the metric definitions associated with the workspace.

    For US7 all 4 demo metrics are available to every workspace; a
    real implementation would filter per-workspace here. The seed
    exposes the union to drive SC-012's "metric definitions" field.
    """
    return repository.seed_demo_metric_definitions()


def _frozen_values_for_workspace(workspace: WorkspaceId) -> list[FrozenValue]:
    return repository.seed_demo_frozen_values()


def _current_values_for_workspace(workspace: WorkspaceId) -> list[CurrentValue]:
    return repository.seed_demo_current_values()


def _evidence_links_for_workspace(workspace: WorkspaceId) -> list[EvidenceLink]:
    return repository.seed_demo_evidence_links()


def _freshness_warnings_for_filters(filters: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    if filters.get("period") == "stale_window":
        warnings.append(
            "selected period overlaps stale data window (>30d); recompute recommended"
        )
    if filters.get("cohort_changed"):
        warnings.append(
            "cohort definition changed during selected period; values may be skewed"
        )
    return warnings


def _comparison_deltas(
    frozen: list[FrozenValue],
    current: list[CurrentValue],
    comparison_period: str,
) -> list[ComparisonDelta]:
    """Compute delta_pct between frozen and current values (AC-30.3).

    delta_pct = (current - frozen) / frozen * 100, when frozen != 0.
    """
    frozen_map = {f.metric_id: f.value for f in frozen}
    out: list[ComparisonDelta] = []
    for c in current:
        fv = frozen_map.get(c.metric_id, 0.0)
        if fv == 0.0:
            delta_pct = 100.0 if c.value != 0 else 0.0
        else:
            delta_pct = round((c.value - fv) / fv * 100.0, 2)
        out.append(
            ComparisonDelta(
                metric_id=c.metric_id,
                delta_pct=delta_pct,
                period=comparison_period,
            )
        )
    return out


def _late_arriving_warnings(
    deltas: list[ComparisonDelta],
    tolerance_pct: float = 0.5,
) -> list[str]:
    """Return warnings for EC-1 (late-arriving data changed values).

    A delta outside ±tolerance_pct is flagged as "late-arriving".
    """
    warnings: list[str] = []
    for d in deltas:
        if abs(d.delta_pct) > tolerance_pct:
            direction = "increased" if d.delta_pct > 0 else "decreased"
            warnings.append(
                f"{d.metric_id} {direction} by {abs(d.delta_pct):.1f}% since snapshot"
            )
    return warnings


def _quality_flags_map(
    current: list[CurrentValue],
) -> dict[str, DataStatus]:
    """Build the metric_id -> DataStatus map (FR-028 + SC-011)."""
    return {c.metric_id: c.data_status for c in current}


def generate_snapshot(
    workspace: WorkspaceId,
    filters: dict[str, Any],
    comparison_period: str,
    annotations: str,
    actor: str,
    fmt: ReviewSnapshotFormat = "json",
) -> ReviewSnapshotResponse:
    """Generate a review snapshot (FR-029 AC-29.1).

    Steps:

    1. EC-3 check — expired payloads in filters → :class:`SnapshotBlockedError`.
    2. Build frozen_values, current_values, comparison_deltas,
       metric_definitions, freshness_warnings, quality_flags,
       evidence_links from seed helpers.
    3. Compute late_arriving_warnings (EC-1).
    4. Compute cohort_definition_changed (EC-2).
    5. Write audit event with action=review_snapshot + target_kind=snapshot
       (AC-29.2).
    6. Persist to in-memory buffer.
    7. Return ReviewSnapshotResponse (8 SC-012 fields populated).
    """
    # EC-3
    expired = _expired_record_ids_for_filters(filters)
    if expired:
        audit_id = next_audit_event_id()
        append_audit_event(
            _build_audit_event(
                event_id=audit_id,
                actor=actor,
                action="review_snapshot",
                target_id=None,
                reason="snapshot blocked: period contains expired records (EC-3)",
                result="denied",
                visibility_mode="hidden",
            )
        )
        raise SnapshotBlockedError(expired)

    snapshot_id = repository.next_snapshot_id()
    generated_at = _now_iso()

    frozen = _frozen_values_for_workspace(workspace)
    current = _current_values_for_workspace(workspace)
    deltas = _comparison_deltas(frozen, current, comparison_period)
    metric_defs = _metric_def_for_workspace(workspace)
    freshness_warnings = _freshness_warnings_for_filters(filters)
    quality_flags = _quality_flags_map(current)
    evidence_links = _evidence_links_for_workspace(workspace)
    late_warnings = _late_arriving_warnings(deltas)

    # EC-2 — cohort definition changed since snapshot would have been
    # generated; for US7 we treat seed cohorts as v1 at generation time
    # and surface the boolean for the test fixture to flip.
    cohort_versions = repository.get_cohort_versions()
    cohort_changed = False
    cohort_change_warning: str | None = None
    if filters.get("cohort_changed") is True:
        cohort_changed = True
        cohort_change_warning = (
            "cohort definition changed since snapshot: "
            + ", ".join(sorted(cohort_versions.keys()))
        )

    expires_at = (
        (datetime.now(UTC) + timedelta(hours=24))
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )
    download_url = (
        f"/api/v1/admin-console/governance/exports/{snapshot_id}/download"
    )

    snapshot = ReviewSnapshotResponse(
        snapshot_id=snapshot_id,
        workspace=workspace,
        generated_at=generated_at,
        generated_by=actor,
        filters=filters,
        frozen_values=frozen,
        comparison_deltas=deltas,
        metric_definitions=metric_defs,
        freshness_warnings=freshness_warnings,
        quality_flags=quality_flags,
        annotations=annotations,
        evidence_links=evidence_links,
        current_values=current,
        cohort_definition_changed=cohort_changed,
        cohort_change_warning=cohort_change_warning,
        late_arriving_warnings=late_warnings,
        download_url=download_url,
        expires_at=expires_at,
        data_status="valid_zero",
        visibility_mode="full",
        comparison_period=comparison_period,
    )

    # AC-29.2 — audit event BEFORE returning snapshot.
    audit_id = next_audit_event_id()
    append_audit_event(
        _build_audit_event(
            event_id=audit_id,
            actor=actor,
            action="review_snapshot",
            target_id=snapshot_id,
            reason=(
                f"snapshot generated for workspace={workspace} "
                f"format={fmt} comparison={comparison_period}"
            ),
            result="executed",
            visibility_mode="full",
        )
    )

    # Persist to buffer.
    repository.append_snapshot(snapshot.model_dump(mode="json"))
    return snapshot


# ---------------------------------------------------------------------------
# Audit builder — uses US6 governance AuditEvent schema (avoid redeclare)
# ---------------------------------------------------------------------------


def _build_audit_event(
    *,
    event_id: str,
    actor: str,
    action: str,
    target_id: str | None,
    reason: str,
    result: str,
    visibility_mode: str,
) -> Any:
    """Build a US6 AuditEvent (governance AuditEvent)."""
    from app.modules.admin_console.governance.schemas import (
        AuditEvent,
        AuditResult,
        AuditTargetKind,
        VisibilityMode as _VisibilityMode,
    )

    # action: review_snapshot / sensitive_reveal / export / governance etc.
    # target_kind: snapshot / governance (depends on action)
    if action == "review_snapshot":
        target_kind: AuditTargetKind = "snapshot"
    elif action == "sensitive_reveal":
        target_kind = "user_resume"
    elif action == "export":
        target_kind = "export"
    else:
        target_kind = "snapshot"

    return AuditEvent(
        event_id=event_id,
        actor=actor,
        timestamp=_now_iso(),
        target_kind=target_kind,
        target_id=target_id,
        action=action,
        reason=reason,
        result=result,
        visibility_mode=visibility_mode,
    )


# ---------------------------------------------------------------------------
# FR-029 / FR-030 — list + get
# ---------------------------------------------------------------------------


def list_snapshots() -> ReviewSnapshotListResponse:
    items = repository.list_snapshots()
    snapshots: list[ReviewSnapshotResponse] = []
    for item in items:
        # Re-hydrate as Pydantic (preserve round-trip).
        snapshots.append(ReviewSnapshotResponse.model_validate(item))
    return ReviewSnapshotListResponse(
        snapshots=snapshots,
        total=len(snapshots),
        data_status="valid_zero" if not snapshots else "valid_zero",
    )


def get_snapshot_with_delta(snapshot_id: str) -> ReviewSnapshotResponse:
    """Return the snapshot with FRESH current_values re-fetched.

    Simulates "late-arriving data changed since snapshot" by re-running
    the current-value seed at GET time. If the current differs from
    frozen by > tolerance, EC-1 warning is appended.

    Raises :class:`SnapshotNotFoundError` when missing.
    """
    raw = repository.get_snapshot(snapshot_id)
    if raw is None:
        raise SnapshotNotFoundError(snapshot_id)

    # Re-hydrate frozen snapshot.
    snapshot = ReviewSnapshotResponse.model_validate(raw)

    # Re-fetch current values (simulates live re-pull).
    current = _current_values_for_workspace(snapshot.workspace)
    snapshot.current_values = current

    # Re-compute deltas + warnings from fresh current vs frozen.
    frozen_map = {f.metric_id: f.value for f in snapshot.frozen_values}
    new_deltas: list[ComparisonDelta] = []
    for c in current:
        fv = frozen_map.get(c.metric_id, 0.0)
        if fv == 0.0:
            delta_pct = 100.0 if c.value != 0 else 0.0
        else:
            delta_pct = round((c.value - fv) / fv * 100.0, 2)
        new_deltas.append(
            ComparisonDelta(
                metric_id=c.metric_id,
                delta_pct=delta_pct,
                period=snapshot.comparison_period,
            )
        )
    snapshot.comparison_deltas = new_deltas
    snapshot.late_arriving_warnings = _late_arriving_warnings(new_deltas)
    snapshot.quality_flags = _quality_flags_map(current)

    # Update freshness_at to "now" to signal re-pull.
    snapshot.generated_at = _now_iso()
    return snapshot


class SnapshotNotFoundError(Exception):
    """Raised when GET /review-snapshots/{id} misses."""

    def __init__(self, snapshot_id: str):
        self.snapshot_id = snapshot_id
        super().__init__(f"snapshot not found: {snapshot_id}")


# ---------------------------------------------------------------------------
# Frontend helper — direct list for snapshots page (no audit gate)
# ---------------------------------------------------------------------------


def get_metric_definitions_for_workspace(
    workspace: WorkspaceId,
) -> list[MetricDefinition10Field]:
    """Return metric definitions for the workspace (FR-027 AC-27.1/27.2)."""
    return _metric_def_for_workspace(workspace)


__all__ = [
    "EXPORT_FIELDS_REDACTED",
    "SnapshotBlockedError",
    "SnapshotImmutableError",
    "SnapshotNotFoundError",
    "assert_snapshot_immutable",
    "generate_snapshot",
    "get_metric_definitions_for_workspace",
    "get_snapshot_with_delta",
    "list_snapshots",
]