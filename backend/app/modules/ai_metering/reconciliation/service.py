"""REQ-061 US9 daily/invoice reconciliation service (T116).

Implements:

- point conservation checks
- attempt / rate / provider usage coverage
- invoice matching with 0.5% daily difference threshold (FR-083 / SC-039)
- orphan cost detection
- issue lifecycle helpers
- projection rebuild compare-before-write checks

Pure helpers are unit/integration testable without DB. ``ReconciliationService``
optionally persists ``ReconciliationRun`` / ``ReconciliationIssue`` rows.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ids import new_uuid_v7
from app.modules.ai_metering.usage_cost.models import (
    ReconciliationIssue,
    ReconciliationRun,
)

# FR-083 / SC-039: daily / invoice difference alert threshold.
DAILY_DIFF_THRESHOLD = Decimal("0.005")  # 0.5%


class RunType(StrEnum):
    POINT_CONSERVATION = "point_conservation"
    ATTEMPT_COVERAGE = "attempt_coverage"
    COST_RATE_COVERAGE = "cost_rate_coverage"
    PROVIDER_USAGE = "provider_usage"
    PROVIDER_INVOICE = "provider_invoice"
    PROJECTION_REBUILD = "projection_rebuild"
    DAILY = "daily"


class IssueClass(StrEnum):
    POINT_IMBALANCE = "point_imbalance"
    MISSING_ATTEMPT_COST = "missing_attempt_cost"
    UNKNOWN_RATE = "unknown_rate"
    ORPHAN_COST = "orphan_cost"
    DIFF_ABOVE_THRESHOLD = "diff_above_threshold"
    FX_CORRECTION = "fx_correction"
    LATE_USAGE = "late_usage"
    ALLOCATION_MISMATCH = "allocation_mismatch"
    PROJECTION_MISMATCH = "projection_mismatch"
    INVOICE_MISMATCH = "invoice_mismatch"


class IssueStatus(StrEnum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    CORRECTED = "corrected"
    CLOSED = "closed"


@dataclass(frozen=True, slots=True)
class ConservationSnapshot:
    opening_available: int
    opening_reserved: int
    grants: int
    compensations: int
    settled: int
    expired: int
    closing_available: int
    closing_reserved: int

    @property
    def left(self) -> int:
        return self.closing_available + self.closing_reserved

    @property
    def right(self) -> int:
        return (
            self.opening_available
            + self.opening_reserved
            + self.grants
            + self.compensations
            - self.settled
            - self.expired
        )

    @property
    def balanced(self) -> bool:
        return self.left == self.right


@dataclass(frozen=True, slots=True)
class DiffResult:
    expected: Decimal
    actual: Decimal
    difference: Decimal
    difference_pct: Decimal | None
    above_threshold: bool
    threshold: Decimal = DAILY_DIFF_THRESHOLD


@dataclass(frozen=True, slots=True)
class IssueDraft:
    issue_class: IssueClass | str
    severity: str = "P2"
    affected_identities: dict[str, Any] = field(default_factory=dict)
    owner: str | None = None
    status: IssueStatus | str = IssueStatus.OPEN


@dataclass(frozen=True, slots=True)
class ReconciliationResult:
    run_type: str
    status: str
    expected_total: Decimal | None
    actual_total: Decimal | None
    difference: Decimal | None
    difference_pct: Decimal | None
    issues: tuple[IssueDraft, ...]
    evidence: dict[str, Any] = field(default_factory=dict)
    run_id: str | None = None

    @property
    def passed(self) -> bool:
        return self.status in {"passed", "matched"} and not self.issues


def compute_difference(
    *,
    expected: Decimal | str | int | float,
    actual: Decimal | str | int | float,
    threshold: Decimal = DAILY_DIFF_THRESHOLD,
) -> DiffResult:
    exp = Decimal(str(expected))
    act = Decimal(str(actual))
    diff = act - exp
    if exp == 0:
        pct: Decimal | None = None if act == 0 else Decimal("1")
        above = act != 0
    else:
        pct = (abs(diff) / abs(exp)).quantize(Decimal("0.000001"))
        above = pct > threshold
    return DiffResult(
        expected=exp,
        actual=act,
        difference=diff,
        difference_pct=pct,
        above_threshold=above,
        threshold=threshold,
    )


def check_point_conservation(snapshot: ConservationSnapshot) -> ReconciliationResult:
    issues: list[IssueDraft] = []
    if not snapshot.balanced:
        issues.append(
            IssueDraft(
                issue_class=IssueClass.POINT_IMBALANCE,
                severity="P1",
                affected_identities={
                    "left": snapshot.left,
                    "right": snapshot.right,
                    "delta": snapshot.left - snapshot.right,
                },
            )
        )
    return ReconciliationResult(
        run_type=RunType.POINT_CONSERVATION,
        status="passed" if not issues else "failed",
        expected_total=Decimal(snapshot.right),
        actual_total=Decimal(snapshot.left),
        difference=Decimal(snapshot.left - snapshot.right),
        difference_pct=None,
        issues=tuple(issues),
        evidence={"balanced": snapshot.balanced},
    )


def check_attempt_coverage(
    *,
    attempt_ids: set[str],
    cost_event_attempt_ids: set[str],
) -> ReconciliationResult:
    missing = sorted(attempt_ids - cost_event_attempt_ids)
    issues = [
        IssueDraft(
            issue_class=IssueClass.MISSING_ATTEMPT_COST,
            severity="P1",
            affected_identities={"attempt_id": attempt_id},
        )
        for attempt_id in missing
    ]
    return ReconciliationResult(
        run_type=RunType.ATTEMPT_COVERAGE,
        status="passed" if not issues else "failed",
        expected_total=Decimal(len(attempt_ids)),
        actual_total=Decimal(len(attempt_ids) - len(missing)),
        difference=Decimal(-len(missing)),
        difference_pct=None,
        issues=tuple(issues),
        evidence={"missing_count": len(missing)},
    )


def check_unknown_rates(*, unknown_rate_task_count: int) -> ReconciliationResult:
    issues: list[IssueDraft] = []
    if unknown_rate_task_count > 0:
        issues.append(
            IssueDraft(
                issue_class=IssueClass.UNKNOWN_RATE,
                severity="P1",
                affected_identities={"unknown_rate_task_count": unknown_rate_task_count},
            )
        )
    return ReconciliationResult(
        run_type=RunType.COST_RATE_COVERAGE,
        status="passed" if not issues else "failed",
        expected_total=Decimal("0"),
        actual_total=Decimal(unknown_rate_task_count),
        difference=Decimal(unknown_rate_task_count),
        difference_pct=None,
        issues=tuple(issues),
    )


def find_orphan_costs(
    *,
    cost_events: list[dict[str, Any]],
) -> ReconciliationResult:
    """Orphan = no task/attempt link and not marked platform shared (FR-152)."""
    orphans: list[IssueDraft] = []
    for event in cost_events:
        task_id = event.get("task_id")
        attempt_id = event.get("external_attempt_id") or event.get("attempt_id")
        platform = event.get("platform_cost_category")
        attribution = event.get("attribution")
        is_platform = platform is not None or attribution == "platform_shared"
        if not task_id and not attempt_id and not is_platform:
            orphans.append(
                IssueDraft(
                    issue_class=IssueClass.ORPHAN_COST,
                    severity="P1",
                    affected_identities={"event_id": event.get("id")},
                )
            )
    return ReconciliationResult(
        run_type="orphan_cost_scan",
        status="passed" if not orphans else "failed",
        expected_total=Decimal("0"),
        actual_total=Decimal(len(orphans)),
        difference=Decimal(len(orphans)),
        difference_pct=None,
        issues=tuple(orphans),
        evidence={"orphan_count": len(orphans)},
    )


def check_allocation_conservation(
    *,
    source_amount: Decimal,
    allocated_parts: list[Decimal],
) -> ReconciliationResult:
    total = sum(allocated_parts, Decimal("0"))
    issues: list[IssueDraft] = []
    if total != source_amount:
        issues.append(
            IssueDraft(
                issue_class=IssueClass.ALLOCATION_MISMATCH,
                severity="P1",
                affected_identities={
                    "source": str(source_amount),
                    "allocated": str(total),
                },
            )
        )
    return ReconciliationResult(
        run_type="shared_allocation",
        status="passed" if not issues else "failed",
        expected_total=source_amount,
        actual_total=total,
        difference=total - source_amount,
        difference_pct=None,
        issues=tuple(issues),
    )


def reconcile_provider_totals(
    *,
    internal_total: Decimal | str | int | float,
    provider_total: Decimal | str | int | float,
    run_type: str = RunType.PROVIDER_INVOICE,
    threshold: Decimal = DAILY_DIFF_THRESHOLD,
) -> ReconciliationResult:
    diff = compute_difference(
        expected=internal_total, actual=provider_total, threshold=threshold
    )
    issues: list[IssueDraft] = []
    if diff.above_threshold:
        issues.append(
            IssueDraft(
                issue_class=IssueClass.DIFF_ABOVE_THRESHOLD
                if run_type == RunType.DAILY
                else IssueClass.INVOICE_MISMATCH,
                severity="P1",
                affected_identities={
                    "expected": str(diff.expected),
                    "actual": str(diff.actual),
                    "difference_pct": str(diff.difference_pct),
                    "threshold": str(threshold),
                },
            )
        )
    status = "matched" if not issues else "failed"
    return ReconciliationResult(
        run_type=run_type,
        status=status,
        expected_total=diff.expected,
        actual_total=diff.actual,
        difference=diff.difference,
        difference_pct=diff.difference_pct,
        issues=tuple(issues),
        evidence={"threshold": str(threshold)},
    )


def apply_late_usage_correction(
    *,
    estimated_amount: Decimal,
    confirmed_amount: Decimal,
    user_points_already_settled: int,
) -> dict[str, Any]:
    """Late provider confirmation adjusts internal cost only — never raises user points."""
    delta = confirmed_amount - estimated_amount
    return {
        "cost_delta": delta,
        "new_cost_status": "provider_confirmed",
        "user_points_delta": 0,
        "user_points_already_settled": user_points_already_settled,
        "requires_independent_compensation": False,
    }


def apply_fx_correction(
    *,
    original_amount: Decimal,
    old_fx: Decimal,
    new_fx: Decimal,
) -> dict[str, Any]:
    old_rmb = (original_amount * old_fx).quantize(Decimal("0.0000000001"))
    new_rmb = (original_amount * new_fx).quantize(Decimal("0.0000000001"))
    return {
        "delta_rmb": new_rmb - old_rmb,
        "user_points_delta": 0,
        "cost_status": "reconciled",
        "adjustment_reason": "fx_correction",
    }


def estimate_confirm_reconcile_reverse_flow(
    *,
    estimated: Decimal,
    confirmed: Decimal,
    reverse_delta: Decimal,
) -> list[dict[str, Any]]:
    """Document the append-only cost status chain for integration tests."""
    steps = [
        {"status": "estimated", "amount": estimated},
        {
            "status": "provider_confirmed",
            "amount": confirmed,
            "delta": confirmed - estimated,
            "preserves_estimate": True,
        },
        {
            "status": "reconciled",
            "amount": confirmed,
            "invoice_matched": True,
        },
    ]
    if reverse_delta != 0:
        steps.append(
            {
                "status": "reversed",
                "amount": confirmed + reverse_delta,
                "delta": reverse_delta,
                "append_only": True,
            }
        )
    return steps


def check_projection_rebuild(
    *,
    ledger_available: int,
    ledger_reserved: int,
    projection_available: int,
    projection_reserved: int,
    dry_run: bool = True,
) -> ReconciliationResult:
    mismatches: list[IssueDraft] = []
    if (
        ledger_available != projection_available
        or ledger_reserved != projection_reserved
    ):
        mismatches.append(
            IssueDraft(
                issue_class=IssueClass.PROJECTION_MISMATCH,
                severity="P1",
                affected_identities={
                    "ledger_available": ledger_available,
                    "ledger_reserved": ledger_reserved,
                    "projection_available": projection_available,
                    "projection_reserved": projection_reserved,
                },
            )
        )
    status = "passed" if not mismatches else "failed"
    return ReconciliationResult(
        run_type=RunType.PROJECTION_REBUILD,
        status=status,
        expected_total=Decimal(ledger_available + ledger_reserved),
        actual_total=Decimal(projection_available + projection_reserved),
        difference=Decimal(
            (projection_available + projection_reserved)
            - (ledger_available + ledger_reserved)
        ),
        difference_pct=None,
        issues=tuple(mismatches),
        evidence={
            "dry_run": dry_run,
            "may_write": (not dry_run) and not mismatches,
            "ledger_facts_mutated": False,
        },
    )


def run_daily_reconciliation(
    *,
    business_date: date,
    conservation: ConservationSnapshot | None = None,
    attempt_ids: set[str] | None = None,
    cost_event_attempt_ids: set[str] | None = None,
    unknown_rate_task_count: int = 0,
    internal_cost_total: Decimal | None = None,
    provider_usage_total: Decimal | None = None,
    cost_events: list[dict[str, Any]] | None = None,
) -> ReconciliationResult:
    """Compose the FR-161 preliminary daily reconciliation checks."""
    issues: list[IssueDraft] = []
    evidence: dict[str, Any] = {
        "business_date": business_date.isoformat(),
        "timezone": "Asia/Shanghai",
        "checks": [],
    }
    expected = Decimal("0")
    actual = Decimal("0")

    if conservation is not None:
        cons = check_point_conservation(conservation)
        evidence["checks"].append(cons.run_type)
        issues.extend(cons.issues)

    if attempt_ids is not None and cost_event_attempt_ids is not None:
        cov = check_attempt_coverage(
            attempt_ids=attempt_ids,
            cost_event_attempt_ids=cost_event_attempt_ids,
        )
        evidence["checks"].append(cov.run_type)
        issues.extend(cov.issues)

    rate = check_unknown_rates(unknown_rate_task_count=unknown_rate_task_count)
    evidence["checks"].append(rate.run_type)
    issues.extend(rate.issues)

    if cost_events is not None:
        orphans = find_orphan_costs(cost_events=cost_events)
        evidence["checks"].append(orphans.run_type)
        issues.extend(orphans.issues)

    if internal_cost_total is not None and provider_usage_total is not None:
        money = reconcile_provider_totals(
            internal_total=internal_cost_total,
            provider_total=provider_usage_total,
            run_type=RunType.DAILY,
        )
        evidence["checks"].append(money.run_type)
        issues.extend(money.issues)
        expected = money.expected_total or Decimal("0")
        actual = money.actual_total or Decimal("0")

    status = "passed" if not issues else "failed"
    diff = actual - expected if internal_cost_total is not None else None
    pct = None
    if expected != 0 and diff is not None:
        pct = (abs(diff) / abs(expected)).quantize(Decimal("0.000001"))
    return ReconciliationResult(
        run_type=RunType.DAILY,
        status=status,
        expected_total=expected if internal_cost_total is not None else None,
        actual_total=actual if provider_usage_total is not None else None,
        difference=diff,
        difference_pct=pct,
        issues=tuple(issues),
        evidence=evidence,
    )


def transition_issue(
    *,
    current_status: str,
    target_status: str,
) -> str:
    allowed = {
        IssueStatus.OPEN: {IssueStatus.ACKNOWLEDGED, IssueStatus.CORRECTED, IssueStatus.CLOSED},
        IssueStatus.ACKNOWLEDGED: {IssueStatus.CORRECTED, IssueStatus.CLOSED},
        IssueStatus.CORRECTED: {IssueStatus.CLOSED},
        IssueStatus.CLOSED: set(),
    }
    cur = IssueStatus(current_status)
    tgt = IssueStatus(target_status)
    if tgt not in allowed[cur]:
        raise ValueError(f"invalid issue transition {current_status} -> {target_status}")
    return tgt.value


class ReconciliationService:
    """Optional persistence wrapper around pure reconciliation helpers."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def persist_result(
        self,
        result: ReconciliationResult,
        *,
        scope: dict[str, Any] | None = None,
    ) -> ReconciliationRun:
        run = ReconciliationRun(
            id=new_uuid_v7(),
            run_type=result.run_type,
            scope=scope or dict(result.evidence),
            expected_total=result.expected_total,
            actual_total=result.actual_total,
            difference=result.difference,
            difference_pct=result.difference_pct,
            status=result.status,
            evidence_ref=None,
            started_at=datetime.now(timezone.utc),
            finished_at=datetime.now(timezone.utc),
        )
        self.session.add(run)
        await self.session.flush()
        for draft in result.issues:
            issue = ReconciliationIssue(
                id=new_uuid_v7(),
                run_id=run.id,
                issue_class=str(draft.issue_class),
                severity=draft.severity,
                affected_identities=dict(draft.affected_identities),
                owner=draft.owner,
                status=str(draft.status),
            )
            self.session.add(issue)
        await self.session.flush()
        return run

    async def run_and_persist_daily(
        self,
        *,
        business_date: date,
        **kwargs: Any,
    ) -> tuple[ReconciliationResult, ReconciliationRun]:
        result = run_daily_reconciliation(business_date=business_date, **kwargs)
        run = await self.persist_result(
            result,
            scope={"business_date": business_date.isoformat(), "timezone": "Asia/Shanghai"},
        )
        return result, run


__all__ = [
    "ConservationSnapshot",
    "DAILY_DIFF_THRESHOLD",
    "DiffResult",
    "IssueClass",
    "IssueDraft",
    "IssueStatus",
    "ReconciliationResult",
    "ReconciliationService",
    "RunType",
    "apply_fx_correction",
    "apply_late_usage_correction",
    "check_allocation_conservation",
    "check_attempt_coverage",
    "check_point_conservation",
    "check_projection_rebuild",
    "check_unknown_rates",
    "compute_difference",
    "estimate_confirm_reconcile_reverse_flow",
    "find_orphan_costs",
    "reconcile_provider_totals",
    "run_daily_reconciliation",
    "transition_issue",
]
