"""Requirement normalization and gap classification helpers."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any

from app.modules.resume_intelligence.schemas import GapCoverage

_WS_RE = re.compile(r"\s+")
_PUNCT_RE = re.compile(r"[^\w\u4e00-\u9fff+#.-]+", re.UNICODE)


@dataclass(frozen=True)
class NormalizedRequirement:
    requirement_id: str
    text: str
    normalized_text: str
    priority: str = "important"
    category: str = "hard_requirements"
    original: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GapClassification:
    requirement_id: str
    requirement_excerpt: str
    priority: str
    coverage: GapCoverage
    confidence: float
    evidence_refs: list[dict[str, Any]]
    explanation: str
    recommended_action: str
    can_rewrite: bool
    needs_supplement: bool
    must_not_claim: bool
    category: str = "hard_requirements"

    def to_payload(self) -> dict[str, Any]:
        return {
            "id": self.requirement_id,
            "requirement_excerpt": self.requirement_excerpt,
            "priority": self.priority,
            "coverage": self.coverage.value,
            "confidence": self.confidence,
            "evidence_refs": self.evidence_refs,
            "explanation": self.explanation,
            "recommended_action": self.recommended_action,
            "can_rewrite": self.can_rewrite,
            "needs_supplement": self.needs_supplement,
            "must_not_claim": self.must_not_claim,
            "category": self.category,
        }


def normalize_requirement_text(text: str) -> str:
    lowered = _WS_RE.sub(" ", str(text or "").strip()).casefold()
    return _PUNCT_RE.sub(" ", lowered).strip()


def stable_requirement_id(text: str, *, prefix: str = "req") -> str:
    normalized = normalize_requirement_text(text)
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}-{digest}"


def normalize_requirements(raw_requirements: list[dict[str, Any]]) -> list[NormalizedRequirement]:
    seen: set[str] = set()
    out: list[NormalizedRequirement] = []
    for index, raw in enumerate(raw_requirements):
        text = str(raw.get("text") or raw.get("requirement_excerpt") or raw.get("description") or "").strip()
        if not text:
            continue
        normalized = normalize_requirement_text(text)
        req_id = str(raw.get("requirement_id") or raw.get("id") or stable_requirement_id(text))
        if req_id in seen:
            req_id = f"{req_id}-{index + 1}"
        seen.add(req_id)
        out.append(
            NormalizedRequirement(
                requirement_id=req_id,
                text=text,
                normalized_text=normalized,
                priority=str(raw.get("priority") or "important"),
                category=str(raw.get("category") or "hard_requirements"),
                original=dict(raw),
            )
        )
    return out


def _coverage_from_evidence(item: dict[str, Any]) -> GapCoverage:
    explicit = item.get("coverage")
    if explicit:
        return GapCoverage(str(explicit))

    current = bool(item.get("current_evidence_refs") or item.get("current_refs"))
    root = bool(item.get("root_evidence_refs") or item.get("root_refs"))
    supplementable = bool(item.get("needs_user_confirmation") or item.get("can_be_supplemented"))
    declared_gap = bool(item.get("known_absent") or item.get("real_gap"))
    weak = bool(item.get("weak") or item.get("ambiguous"))

    if current and weak:
        return GapCoverage.WEAK
    if current:
        return GapCoverage.COVERED
    if root:
        return GapCoverage.EVIDENCE_NOT_SHOWN
    if declared_gap:
        return GapCoverage.REAL_GAP
    if supplementable:
        return GapCoverage.MISSING_EVIDENCE
    return GapCoverage.UNKNOWN


def classify_requirement_gap(
    requirement: NormalizedRequirement,
    evidence: dict[str, Any] | None,
) -> GapClassification:
    evidence = dict(evidence or {})
    coverage = _coverage_from_evidence(evidence)
    refs = list(
        evidence.get("evidence_refs")
        or evidence.get("current_evidence_refs")
        or evidence.get("root_evidence_refs")
        or []
    )
    confidence = max(0.0, min(1.0, float(evidence.get("confidence", 0.5 if refs else 0.25))))
    explanation = str(evidence.get("explanation") or _default_explanation(coverage))
    return GapClassification(
        requirement_id=requirement.requirement_id,
        requirement_excerpt=requirement.text,
        priority=requirement.priority,
        coverage=coverage,
        confidence=confidence,
        evidence_refs=refs,
        explanation=explanation,
        recommended_action=_recommended_action(coverage),
        can_rewrite=coverage in {GapCoverage.COVERED, GapCoverage.WEAK, GapCoverage.EVIDENCE_NOT_SHOWN},
        needs_supplement=coverage in {GapCoverage.MISSING_EVIDENCE, GapCoverage.UNKNOWN},
        must_not_claim=coverage == GapCoverage.REAL_GAP,
        category=requirement.category,
    )


def classify_gaps(
    requirements: list[dict[str, Any]],
    evidence_map: dict[str, dict[str, Any]] | list[dict[str, Any]],
) -> list[GapClassification]:
    normalized = normalize_requirements(requirements)
    if isinstance(evidence_map, list):
        by_id = {
            str(item.get("requirement_id") or item.get("id")): dict(item)
            for item in evidence_map
        }
    else:
        by_id = {str(key): dict(value) for key, value in evidence_map.items()}
    return [
        classify_requirement_gap(requirement, by_id.get(requirement.requirement_id))
        for requirement in normalized
    ]


def gap_payloads(
    requirements: list[dict[str, Any]],
    evidence_map: dict[str, dict[str, Any]] | list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [item.to_payload() for item in classify_gaps(requirements, evidence_map)]


def _default_explanation(coverage: GapCoverage) -> str:
    return {
        GapCoverage.COVERED: "当前简历已有可追溯证据。",
        GapCoverage.WEAK: "当前证据存在但表达或强度不足。",
        GapCoverage.EVIDENCE_NOT_SHOWN: "根简历有证据，但当前稿未展示。",
        GapCoverage.MISSING_EVIDENCE: "需要用户确认补充真实证据。",
        GapCoverage.REAL_GAP: "现有证据不支持声称该要求已满足。",
        GapCoverage.UNKNOWN: "证据不足，无法安全判断。",
    }[coverage]


def _recommended_action(coverage: GapCoverage) -> str:
    return {
        GapCoverage.COVERED: "可在现有证据范围内优化表达。",
        GapCoverage.WEAK: "强化已有证据的上下文、结果或关键词。",
        GapCoverage.EVIDENCE_NOT_SHOWN: "从根简历证据中选择性加入当前稿。",
        GapCoverage.MISSING_EVIDENCE: "向用户询问并确认补充事实。",
        GapCoverage.REAL_GAP: "不要生成该能力主张。",
        GapCoverage.UNKNOWN: "先澄清岗位要求或候选人事实。",
    }[coverage]


__all__ = [
    "GapClassification",
    "NormalizedRequirement",
    "classify_gaps",
    "classify_requirement_gap",
    "gap_payloads",
    "normalize_requirement_text",
    "normalize_requirements",
    "stable_requirement_id",
]
