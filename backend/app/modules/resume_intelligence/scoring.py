"""Versioned deterministic REQ-059 job-fit scoring."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class Coverage(StrEnum):
    COVERED = "covered"
    WEAK = "weak"
    EVIDENCE_NOT_SHOWN = "evidence_not_shown"
    MISSING_EVIDENCE = "missing_evidence"
    REAL_GAP = "real_gap"
    UNKNOWN = "unknown"


DIMENSION_WEIGHTS = {
    "hard_requirements": 0.30,
    "experience_evidence": 0.25,
    "skills_keywords": 0.15,
    "outcomes_quantification": 0.15,
    "responsibility_relevance": 0.10,
    "expression_readability": 0.05,
}
PRIORITY_WEIGHTS = {"hard": 5.0, "important": 3.0, "nice": 1.0}
COVERAGE_FACTORS = {
    Coverage.COVERED: 1.0,
    Coverage.WEAK: 0.6,
    Coverage.EVIDENCE_NOT_SHOWN: 0.45,
    Coverage.UNKNOWN: 0.25,
    Coverage.MISSING_EVIDENCE: 0.0,
    Coverage.REAL_GAP: 0.0,
}


@dataclass(frozen=True)
class RequirementScoreInput:
    requirement_id: str
    priority: str
    dimension: str
    coverage: Coverage


@dataclass
class ScoringInput:
    requirements: list[RequirementScoreInput]
    outcomes_quantification: float
    expression_readability: float
    jd_completeness: float
    evidence_trace_coverage: float
    schema_validation_quality: float


@dataclass(frozen=True)
class DimensionScore:
    key: str
    weight: float
    score: float


@dataclass(frozen=True)
class JobFitScore:
    overall_score: float
    confidence_score: float
    confidence_band: str
    dimensions: list[DimensionScore]
    hard_blockers: list[str] = field(default_factory=list)
    scoring_version: str = "scoring.v1"


def _bounded(value: float) -> float:
    return max(0.0, min(100.0, float(value)))


def calculate_job_fit(data: ScoringInput) -> JobFitScore:
    by_dimension: dict[str, list[RequirementScoreInput]] = {
        key: [] for key in DIMENSION_WEIGHTS
    }
    for requirement in data.requirements:
        if requirement.dimension in by_dimension:
            by_dimension[requirement.dimension].append(requirement)

    dimensions: list[DimensionScore] = []
    for key, weight in DIMENSION_WEIGHTS.items():
        if key == "outcomes_quantification":
            value = _bounded(data.outcomes_quantification)
        elif key == "expression_readability":
            value = _bounded(data.expression_readability)
        else:
            items = by_dimension[key]
            denominator = sum(PRIORITY_WEIGHTS.get(item.priority, 1.0) for item in items)
            if denominator:
                numerator = sum(
                    PRIORITY_WEIGHTS.get(item.priority, 1.0)
                    * COVERAGE_FACTORS[item.coverage]
                    for item in items
                )
                value = 100.0 * numerator / denominator
            else:
                value = 0.0
        dimensions.append(DimensionScore(key=key, weight=weight, score=round(value, 2)))

    overall = round(sum(item.weight * item.score for item in dimensions), 2)
    confidence = round(
        max(
            0.0,
            min(
                1.0,
                0.35 * data.jd_completeness
                + 0.40 * data.evidence_trace_coverage
                + 0.25 * data.schema_validation_quality,
            ),
        ),
        3,
    )
    band = "high" if confidence >= 0.85 else "medium" if confidence >= 0.65 else "low"
    blockers = sorted(
        item.requirement_id
        for item in data.requirements
        if item.priority == "hard"
        and item.coverage in {Coverage.MISSING_EVIDENCE, Coverage.REAL_GAP}
    )
    return JobFitScore(
        overall_score=overall,
        confidence_score=confidence,
        confidence_band=band,
        dimensions=dimensions,
        hard_blockers=blockers,
    )
