"""REQ-061 US11 — gray release batches, cohorts, gates, stop/rollback (T147).

Implements FR-114..FR-121 as an in-memory service skeleton. Persistence
and admin API (T148) plug in later.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any
from uuid import uuid4

GRAY_STAGES: tuple[int, ...] = (1, 5, 20, 50, 100)
MIN_OBSERVATIONS_PER_STAGE = 200
MIN_OBSERVATION_HOURS = 24
LOW_TRAFFIC_MIN_OBSERVATIONS = 50
LOW_TRAFFIC_DAYS = 7


class ReleaseStatus(StrEnum):
    DRAFT = "draft"
    OFFLINE_PENDING = "offline_pending"
    OFFLINE_REJECTED = "offline_rejected"
    GRAY = "gray"
    STABLE = "stable"
    STOPPED = "stopped"
    ROLLED_BACK = "rolled_back"


class GateVerdict(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    MANUAL_REVIEW = "manual_review"


@dataclass
class OfflineGateResult:
    verdict: GateVerdict
    reasons: list[str] = field(default_factory=list)
    p0_p1_safe: bool = True
    structure_pass: bool = True
    quality_delta_pp: float = 0.0
    p95_latency_delta_pct: float = 0.0
    cost_delta_pct: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict.value,
            "reasons": list(self.reasons),
            "p0_p1_safe": self.p0_p1_safe,
            "structure_pass": self.structure_pass,
            "quality_delta_pp": self.quality_delta_pp,
            "p95_latency_delta_pct": self.p95_latency_delta_pct,
            "cost_delta_pct": self.cost_delta_pct,
        }


@dataclass
class CohortAssignment:
    user_id: str
    lineage_id: str
    release_batch_id: str
    stage_percent: int
    sticky: bool = True
    assigned_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


@dataclass
class OverrideRecord:
    override_id: str
    release_batch_id: str
    pm_approver: str
    technical_approver: str
    reason: str
    scope: str
    expires_at: str | None
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    safety_gate_bypassed: bool = False  # MUST remain False (FR-121)


@dataclass
class ReleaseBatch:
    release_batch_id: str
    capability_code: str
    candidate_policy_version: str
    stable_policy_version: str
    status: ReleaseStatus = ReleaseStatus.DRAFT
    stage_percent: int = 0
    stage_index: int = -1
    observations: int = 0
    stage_started_at: datetime | None = None
    offline_gate: OfflineGateResult | None = None
    stop_reason: str | None = None
    rollback_target: str | None = None
    overrides: list[OverrideRecord] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "release_batch_id": self.release_batch_id,
            "capability_code": self.capability_code,
            "candidate_policy_version": self.candidate_policy_version,
            "stable_policy_version": self.stable_policy_version,
            "status": self.status.value,
            "stage_percent": self.stage_percent,
            "stage_index": self.stage_index,
            "observations": self.observations,
            "stage_started_at": (
                self.stage_started_at.isoformat() if self.stage_started_at else None
            ),
            "offline_gate": self.offline_gate.to_dict() if self.offline_gate else None,
            "stop_reason": self.stop_reason,
            "rollback_target": self.rollback_target or self.stable_policy_version,
            "overrides": [
                {
                    "override_id": o.override_id,
                    "pm_approver": o.pm_approver,
                    "technical_approver": o.technical_approver,
                    "reason": o.reason,
                    "scope": o.scope,
                    "expires_at": o.expires_at,
                    "created_at": o.created_at,
                    "safety_gate_bypassed": o.safety_gate_bypassed,
                }
                for o in self.overrides
            ],
            "created_at": self.created_at,
        }


class ReleaseServiceError(RuntimeError):
    """Release governance failure."""


class ReleaseService:
    """In-memory gray-release controller."""

    def __init__(self) -> None:
        self._batches: dict[str, ReleaseBatch] = {}
        self._cohorts: dict[str, CohortAssignment] = {}  # key: user_id|lineage_id

    def create_batch(
        self,
        *,
        capability_code: str,
        candidate_policy_version: str,
        stable_policy_version: str,
    ) -> ReleaseBatch:
        batch = ReleaseBatch(
            release_batch_id=f"rel-{uuid4()}",
            capability_code=capability_code,
            candidate_policy_version=candidate_policy_version,
            stable_policy_version=stable_policy_version,
            status=ReleaseStatus.OFFLINE_PENDING,
            rollback_target=stable_policy_version,
        )
        self._batches[batch.release_batch_id] = batch
        return batch

    def get_batch(self, release_batch_id: str) -> ReleaseBatch | None:
        return self._batches.get(release_batch_id)

    def list_batches(self) -> list[ReleaseBatch]:
        return list(self._batches.values())

    def evaluate_offline_gate(
        self,
        release_batch_id: str,
        *,
        p0_p1_safe: bool,
        structure_pass: bool,
        quality_delta_pp: float,
        p95_latency_delta_pct: float,
        cost_delta_pct: float,
        dual_approved_cost: bool = False,
    ) -> OfflineGateResult:
        batch = self._require(release_batch_id)
        reasons: list[str] = []
        verdict = GateVerdict.PASS

        if not p0_p1_safe:
            reasons.append("p0_p1_regression")
            verdict = GateVerdict.FAIL
        if not structure_pass:
            reasons.append("structure_or_fact_fail")
            verdict = GateVerdict.FAIL
        if quality_delta_pp < -2.0:
            reasons.append("quality_drop_exceeds_2pp")
            verdict = GateVerdict.FAIL
        if p95_latency_delta_pct > 20.0:
            reasons.append("p95_latency_worsened_over_20pct")
            if verdict == GateVerdict.PASS:
                verdict = GateVerdict.MANUAL_REVIEW
        if cost_delta_pct > 20.0 and not dual_approved_cost:
            reasons.append("cost_increase_over_20pct")
            if verdict == GateVerdict.PASS:
                verdict = GateVerdict.MANUAL_REVIEW
        # Quality up but cost/latency over → manual (FR-115).
        if quality_delta_pp > 0 and (
            p95_latency_delta_pct > 20.0 or (cost_delta_pct > 20.0 and not dual_approved_cost)
        ):
            if verdict == GateVerdict.PASS:
                verdict = GateVerdict.MANUAL_REVIEW
            reasons.append("quality_cost_tradeoff_requires_review")
        # Cost down but quality down → manual.
        if cost_delta_pct < 0 and quality_delta_pp < 0 and verdict == GateVerdict.PASS:
            verdict = GateVerdict.MANUAL_REVIEW
            reasons.append("cost_quality_tradeoff_requires_review")

        result = OfflineGateResult(
            verdict=verdict,
            reasons=reasons,
            p0_p1_safe=p0_p1_safe,
            structure_pass=structure_pass,
            quality_delta_pp=quality_delta_pp,
            p95_latency_delta_pct=p95_latency_delta_pct,
            cost_delta_pct=cost_delta_pct,
        )
        batch.offline_gate = result
        if verdict == GateVerdict.FAIL:
            batch.status = ReleaseStatus.OFFLINE_REJECTED
        return result

    def start_gray(self, release_batch_id: str, *, now: datetime | None = None) -> ReleaseBatch:
        batch = self._require(release_batch_id)
        if batch.offline_gate is None or batch.offline_gate.verdict != GateVerdict.PASS:
            raise ReleaseServiceError("offline_gate_not_passed")
        if batch.status == ReleaseStatus.OFFLINE_REJECTED:
            raise ReleaseServiceError("offline_rejected")
        batch.status = ReleaseStatus.GRAY
        batch.stage_index = 0
        batch.stage_percent = GRAY_STAGES[0]
        batch.observations = 0
        batch.stage_started_at = now or datetime.now(UTC)
        batch.stop_reason = None
        return batch

    def assign_cohort(
        self,
        *,
        user_id: str,
        lineage_id: str,
        release_batch_id: str,
    ) -> CohortAssignment:
        """Sticky cohort: same user+lineage keeps the batch for the task (FR-119)."""
        batch = self._require(release_batch_id)
        key = f"{user_id}|{lineage_id}"
        existing = self._cohorts.get(key)
        if existing is not None and existing.sticky:
            return existing
        assignment = CohortAssignment(
            user_id=user_id,
            lineage_id=lineage_id,
            release_batch_id=release_batch_id,
            stage_percent=batch.stage_percent,
            sticky=True,
        )
        self._cohorts[key] = assignment
        return assignment

    def get_cohort(self, user_id: str, lineage_id: str) -> CohortAssignment | None:
        return self._cohorts.get(f"{user_id}|{lineage_id}")

    def record_observation(
        self, release_batch_id: str, *, count: int = 1
    ) -> ReleaseBatch:
        batch = self._require(release_batch_id)
        if batch.status != ReleaseStatus.GRAY:
            raise ReleaseServiceError("not_in_gray")
        batch.observations += count
        return batch

    def can_advance(
        self,
        release_batch_id: str,
        *,
        now: datetime | None = None,
        low_traffic: bool = False,
        dual_approved_low_traffic: bool = False,
    ) -> tuple[bool, str]:
        batch = self._require(release_batch_id)
        if batch.status != ReleaseStatus.GRAY:
            return False, "not_in_gray"
        if batch.stage_index < 0 or batch.stage_index >= len(GRAY_STAGES) - 1:
            return False, "already_at_final_or_unstarted"
        started = batch.stage_started_at or datetime.now(UTC)
        elapsed = (now or datetime.now(UTC)) - started
        if low_traffic:
            if dual_approved_low_traffic and batch.observations >= LOW_TRAFFIC_MIN_OBSERVATIONS:
                if elapsed >= timedelta(days=LOW_TRAFFIC_DAYS):
                    return True, "low_traffic_dual_approved"
            return False, "low_traffic_gate_not_met"
        if batch.observations < MIN_OBSERVATIONS_PER_STAGE:
            return False, "insufficient_observations"
        if elapsed < timedelta(hours=MIN_OBSERVATION_HOURS):
            return False, "observation_window_open"
        return True, "ok"

    def advance_stage(
        self,
        release_batch_id: str,
        *,
        now: datetime | None = None,
        low_traffic: bool = False,
        dual_approved_low_traffic: bool = False,
    ) -> ReleaseBatch:
        ok, reason = self.can_advance(
            release_batch_id,
            now=now,
            low_traffic=low_traffic,
            dual_approved_low_traffic=dual_approved_low_traffic,
        )
        if not ok:
            raise ReleaseServiceError(reason)
        batch = self._require(release_batch_id)
        batch.stage_index += 1
        batch.stage_percent = GRAY_STAGES[batch.stage_index]
        batch.observations = 0
        batch.stage_started_at = now or datetime.now(UTC)
        if batch.stage_percent >= 100:
            batch.status = ReleaseStatus.STABLE
        return batch

    def check_stop_thresholds(
        self,
        release_batch_id: str,
        *,
        safety_incident: bool = False,
        success_rate_delta_pp: float = 0.0,
        p95_latency_delta_pct: float = 0.0,
        unit_cost_delta_pct: float = 0.0,
        negative_feedback_delta_pp: float = 0.0,
        erroneous_charge_rate: float = 0.0,
    ) -> tuple[bool, str | None]:
        """FR-118 automatic stop conditions."""
        if safety_incident:
            return True, "safety_incident"
        if success_rate_delta_pp <= -2.0:
            return True, "success_rate_drop_2pp"
        if p95_latency_delta_pct >= 30.0:
            return True, "p95_latency_up_30pct"
        if unit_cost_delta_pct >= 25.0:
            return True, "unit_cost_up_25pct"
        if negative_feedback_delta_pp >= 3.0:
            return True, "negative_feedback_up_3pp"
        if erroneous_charge_rate > 0:
            return True, "erroneous_charge_rate_positive"
        return False, None

    def stop_and_rollback(
        self, release_batch_id: str, *, reason: str
    ) -> ReleaseBatch:
        batch = self._require(release_batch_id)
        batch.status = ReleaseStatus.ROLLED_BACK
        batch.stop_reason = reason
        batch.stage_percent = 0
        batch.rollback_target = batch.stable_policy_version
        return batch

    def record_override(
        self,
        release_batch_id: str,
        *,
        pm_approver: str,
        technical_approver: str,
        reason: str,
        scope: str,
        expires_at: str | None = None,
        bypass_safety_gate: bool = False,
    ) -> OverrideRecord:
        """Dual-approval override (FR-121). Safety gates cannot be bypassed."""
        if bypass_safety_gate:
            raise ReleaseServiceError("safety_gate_cannot_be_overridden")
        if not pm_approver or not technical_approver:
            raise ReleaseServiceError("dual_approval_required")
        if pm_approver.strip().lower() == technical_approver.strip().lower():
            raise ReleaseServiceError("approvers_must_be_distinct")
        batch = self._require(release_batch_id)
        record = OverrideRecord(
            override_id=f"ovr-{uuid4()}",
            release_batch_id=release_batch_id,
            pm_approver=pm_approver,
            technical_approver=technical_approver,
            reason=reason,
            scope=scope,
            expires_at=expires_at,
            safety_gate_bypassed=False,
        )
        batch.overrides.append(record)
        return record

    def compare_candidate_stable(self, release_batch_id: str) -> dict[str, Any]:
        batch = self._require(release_batch_id)
        return {
            "release_batch_id": batch.release_batch_id,
            "capability_code": batch.capability_code,
            "candidate": batch.candidate_policy_version,
            "stable": batch.stable_policy_version,
            "status": batch.status.value,
            "stage_percent": batch.stage_percent,
            "stop_reason": batch.stop_reason,
            "rollback_target": batch.rollback_target or batch.stable_policy_version,
            "offline_gate": batch.offline_gate.to_dict() if batch.offline_gate else None,
            "override_count": len(batch.overrides),
        }

    def _require(self, release_batch_id: str) -> ReleaseBatch:
        batch = self._batches.get(release_batch_id)
        if batch is None:
            raise ReleaseServiceError(f"unknown_batch:{release_batch_id}")
        return batch


_DEFAULT: ReleaseService | None = None


def get_release_service() -> ReleaseService:
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = ReleaseService()
    return _DEFAULT


def reset_release_service() -> None:
    global _DEFAULT
    _DEFAULT = None


__all__ = [
    "GRAY_STAGES",
    "CohortAssignment",
    "GateVerdict",
    "LOW_TRAFFIC_DAYS",
    "LOW_TRAFFIC_MIN_OBSERVATIONS",
    "MIN_OBSERVATION_HOURS",
    "MIN_OBSERVATIONS_PER_STAGE",
    "OfflineGateResult",
    "OverrideRecord",
    "ReleaseBatch",
    "ReleaseService",
    "ReleaseServiceError",
    "ReleaseStatus",
    "get_release_service",
    "reset_release_service",
]
