"""REQ-061 US11 — risk-based online sampling (T145 / FR-144).

Sampling rates:
  - ordinary text tasks: 5%
  - high-risk (resume facts / research / interview score / agent writes): 20%
  - P0/P1, negative feedback, anomalous point tasks: 100%

Produces durable evaluation links (task_id → evaluation_link_id).
"""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from app.eval.capability_registry import RiskClass, get_capability_registry

ORDINARY_SAMPLE_RATE = 0.05
HIGH_RISK_SAMPLE_RATE = 0.20
MANDATORY_SAMPLE_RATE = 1.0


class SampleReason(StrEnum):
    ORDINARY_RANDOM = "ordinary_random"
    HIGH_RISK_RANDOM = "high_risk_random"
    P0_P1_MANDATORY = "p0_p1_mandatory"
    NEGATIVE_FEEDBACK = "negative_feedback"
    ANOMALOUS_POINTS = "anomalous_points"
    SKIPPED = "skipped"


@dataclass
class EvaluationLink:
    """Durable join key between a production task and an eval sample."""

    evaluation_link_id: str
    task_id: str
    execution_id: str | None
    capability_code: str
    action_code: str
    sample_reason: SampleReason
    sampled: bool
    sample_rate: float
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    rubric_version: str = "unknown"
    evidence_ref: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "evaluation_link_id": self.evaluation_link_id,
            "task_id": self.task_id,
            "execution_id": self.execution_id,
            "capability_code": self.capability_code,
            "action_code": self.action_code,
            "sample_reason": self.sample_reason.value,
            "sampled": self.sampled,
            "sample_rate": self.sample_rate,
            "created_at": self.created_at,
            "rubric_version": self.rubric_version,
            "evidence_ref": self.evidence_ref,
        }


@dataclass
class OnlineSampler:
    """Decide whether a completed task enters online subjective evaluation."""

    seed: int | None = None
    _links: dict[str, EvaluationLink] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self._rng = random.Random(self.seed)

    def rate_for(
        self,
        *,
        capability_code: str,
        action_code: str = "",
        severity: str | None = None,
        negative_feedback: bool = False,
        anomalous_points: bool = False,
    ) -> tuple[float, SampleReason]:
        if severity and severity.upper() in {"P0", "P1"}:
            return MANDATORY_SAMPLE_RATE, SampleReason.P0_P1_MANDATORY
        if negative_feedback:
            return MANDATORY_SAMPLE_RATE, SampleReason.NEGATIVE_FEEDBACK
        if anomalous_points:
            return MANDATORY_SAMPLE_RATE, SampleReason.ANOMALOUS_POINTS

        registry = get_capability_registry()
        entry = registry.get_by_key(capability_code, action_code) if action_code else None
        risk = entry.risk_class if entry else RiskClass.ORDINARY
        if risk == RiskClass.P0_P1:
            return MANDATORY_SAMPLE_RATE, SampleReason.P0_P1_MANDATORY
        if risk == RiskClass.HIGH_RISK:
            return HIGH_RISK_SAMPLE_RATE, SampleReason.HIGH_RISK_RANDOM
        return ORDINARY_SAMPLE_RATE, SampleReason.ORDINARY_RANDOM

    def should_sample(
        self,
        *,
        capability_code: str,
        action_code: str = "",
        severity: str | None = None,
        negative_feedback: bool = False,
        anomalous_points: bool = False,
        task_id: str | None = None,
    ) -> tuple[bool, float, SampleReason]:
        rate, reason = self.rate_for(
            capability_code=capability_code,
            action_code=action_code,
            severity=severity,
            negative_feedback=negative_feedback,
            anomalous_points=anomalous_points,
        )
        if rate >= 1.0:
            return True, rate, reason
        # Sticky per-task: same task_id always yields the same draw.
        if task_id:
            digest = hashlib.sha256(f"{task_id}:{rate}".encode()).hexdigest()
            draw = int(digest[:8], 16) / 0xFFFFFFFF
        else:
            draw = self._rng.random()
        sampled = draw < rate
        return sampled, rate, reason if sampled else SampleReason.SKIPPED

    def sample_task(
        self,
        *,
        task_id: str,
        capability_code: str,
        action_code: str = "",
        execution_id: str | None = None,
        severity: str | None = None,
        negative_feedback: bool = False,
        anomalous_points: bool = False,
        rubric_version: str = "unknown",
        evidence_ref: str | None = None,
    ) -> EvaluationLink:
        sampled, rate, reason = self.should_sample(
            capability_code=capability_code,
            action_code=action_code,
            severity=severity,
            negative_feedback=negative_feedback,
            anomalous_points=anomalous_points,
            task_id=task_id,
        )
        link = EvaluationLink(
            evaluation_link_id=f"eval-link-{uuid4()}",
            task_id=task_id,
            execution_id=execution_id,
            capability_code=capability_code,
            action_code=action_code,
            sample_reason=reason,
            sampled=sampled,
            sample_rate=rate,
            rubric_version=rubric_version,
            evidence_ref=evidence_ref,
        )
        if sampled:
            self._links[link.evaluation_link_id] = link
        return link

    def get_link(self, evaluation_link_id: str) -> EvaluationLink | None:
        return self._links.get(evaluation_link_id)

    def list_links(self) -> list[EvaluationLink]:
        return list(self._links.values())


__all__ = [
    "EvaluationLink",
    "HIGH_RISK_SAMPLE_RATE",
    "MANDATORY_SAMPLE_RATE",
    "ORDINARY_SAMPLE_RATE",
    "OnlineSampler",
    "SampleReason",
]
