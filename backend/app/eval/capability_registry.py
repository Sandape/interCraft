"""REQ-061 US11 — versioned eval capability registry (T143).

Maps every reachable REQ-061 capability/action to an eval node id,
risk class, and minimum active-case thresholds (FR-112).
Interview nodes remain the only live graph dispatch; other capabilities
register stub handlers until adapters are cut over.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Callable, Awaitable

# Write / fact-generation / charging capabilities need ≥50 active cases (FR-112).
WRITE_FACT_CHARGING_CAPABILITIES: frozenset[str] = frozenset(
    {
        "resume_intelligence",
        "resume_derive",
        "interview",
        "wechat_agent",
        "proactive_research",
        "point_safety",
    }
)

MIN_ACTIVE_CASES_DEFAULT = 30
MIN_ACTIVE_CASES_WRITE_FACT = 50

REQUIRED_CASE_CLASSES: frozenset[str] = frozenset(
    {"normal", "boundary", "failure", "privacy", "adversarial"}
)


class RiskClass(StrEnum):
    ORDINARY = "ordinary"
    HIGH_RISK = "high_risk"
    P0_P1 = "p0_p1"


@dataclass(frozen=True)
class EvalCapabilityEntry:
    """One capability/action eval registration."""

    capability_code: str
    action_code: str
    node: str
    risk_class: RiskClass = RiskClass.ORDINARY
    owners: tuple[str, ...] = ()
    engine_kind: str = "stub"
    min_active_cases: int = MIN_ACTIVE_CASES_DEFAULT
    case_classes: frozenset[str] = field(default_factory=lambda: REQUIRED_CASE_CLASSES)
    stub: bool = True

    @property
    def key(self) -> str:
        return f"{self.capability_code}.{self.action_code}"


# Stable node ids for runner dispatch.
NODE_INTERVIEW_SCORE = "interview.score"
NODE_INTERVIEW_SCORE_LLM = "interview.score_llm"
NODE_INTERVIEW_REPORT = "interview.report"

_BUILTIN: list[EvalCapabilityEntry] = [
    EvalCapabilityEntry(
        capability_code="resume_intelligence",
        action_code="analyze",
        node="resume_intelligence.analyze",
        risk_class=RiskClass.HIGH_RISK,
        owners=("resume-intelligence", "ai-runtime"),
        engine_kind="background_pipeline",
        min_active_cases=MIN_ACTIVE_CASES_WRITE_FACT,
        stub=True,
    ),
    EvalCapabilityEntry(
        capability_code="resume_intelligence",
        action_code="suggest",
        node="resume_intelligence.suggest",
        risk_class=RiskClass.HIGH_RISK,
        owners=("resume-intelligence", "ai-runtime"),
        engine_kind="background_pipeline",
        min_active_cases=MIN_ACTIVE_CASES_WRITE_FACT,
        stub=True,
    ),
    EvalCapabilityEntry(
        capability_code="resume_derive",
        action_code="derive",
        node="resume_derive.derive",
        risk_class=RiskClass.HIGH_RISK,
        owners=("resume-derive", "ai-runtime"),
        engine_kind="background_pipeline",
        min_active_cases=MIN_ACTIVE_CASES_WRITE_FACT,
        stub=True,
    ),
    EvalCapabilityEntry(
        capability_code="interview",
        action_code="start",
        node=NODE_INTERVIEW_SCORE,
        risk_class=RiskClass.HIGH_RISK,
        owners=("interview", "ai-runtime"),
        engine_kind="langgraph",
        min_active_cases=MIN_ACTIVE_CASES_WRITE_FACT,
        stub=False,
    ),
    EvalCapabilityEntry(
        capability_code="interview",
        action_code="conduct",
        node=NODE_INTERVIEW_REPORT,
        risk_class=RiskClass.HIGH_RISK,
        owners=("interview", "ai-runtime"),
        engine_kind="langgraph",
        min_active_cases=MIN_ACTIVE_CASES_WRITE_FACT,
        stub=False,
    ),
    EvalCapabilityEntry(
        capability_code="general_coach",
        action_code="chat",
        node="general_coach.chat",
        risk_class=RiskClass.ORDINARY,
        owners=("coach", "ai-runtime"),
        engine_kind="synchronous_adapter",
        stub=True,
    ),
    EvalCapabilityEntry(
        capability_code="error_coach",
        action_code="drill",
        node="error_coach.drill",
        risk_class=RiskClass.ORDINARY,
        owners=("coach", "ai-runtime"),
        engine_kind="synchronous_adapter",
        stub=True,
    ),
    EvalCapabilityEntry(
        capability_code="ability_insight",
        action_code="diagnose",
        node="ability_insight.diagnose",
        risk_class=RiskClass.ORDINARY,
        owners=("ability-profile", "ai-runtime"),
        engine_kind="synchronous_adapter",
        stub=True,
    ),
    EvalCapabilityEntry(
        capability_code="proactive_research",
        action_code="research",
        node="proactive_research.research",
        risk_class=RiskClass.HIGH_RISK,
        owners=("research", "ai-runtime"),
        engine_kind="background_pipeline",
        min_active_cases=MIN_ACTIVE_CASES_WRITE_FACT,
        stub=True,
    ),
    EvalCapabilityEntry(
        capability_code="wechat_agent",
        action_code="run",
        node="wechat_agent.run",
        risk_class=RiskClass.HIGH_RISK,
        owners=("wechat-agent", "ai-runtime"),
        engine_kind="tool_loop",
        min_active_cases=MIN_ACTIVE_CASES_WRITE_FACT,
        stub=True,
    ),
    # Cross-cutting eval suites (not production start actions).
    EvalCapabilityEntry(
        capability_code="failure_recovery",
        action_code="replay",
        node="failure_recovery.replay",
        risk_class=RiskClass.ORDINARY,
        owners=("ai-runtime",),
        engine_kind="stub",
        stub=True,
    ),
    EvalCapabilityEntry(
        capability_code="point_safety",
        action_code="settle",
        node="point_safety.settle",
        risk_class=RiskClass.P0_P1,
        owners=("ai-metering",),
        engine_kind="stub",
        min_active_cases=MIN_ACTIVE_CASES_WRITE_FACT,
        stub=True,
    ),
    EvalCapabilityEntry(
        capability_code="privacy",
        action_code="redact",
        node="privacy.redact",
        risk_class=RiskClass.P0_P1,
        owners=("privacy", "ai-runtime"),
        engine_kind="stub",
        stub=True,
    ),
]


class CapabilityRegistry:
    """In-memory registry of eval capabilities and node→handler stubs."""

    def __init__(self, entries: list[EvalCapabilityEntry] | None = None) -> None:
        self._entries = list(entries if entries is not None else _BUILTIN)
        self._by_node: dict[str, EvalCapabilityEntry] = {
            e.node: e for e in self._entries
        }
        # Alias interview.score_llm → same entry as interview.score.
        interview_start = next(
            (e for e in self._entries if e.node == NODE_INTERVIEW_SCORE), None
        )
        if interview_start is not None:
            self._by_node[NODE_INTERVIEW_SCORE_LLM] = interview_start
        self._handlers: dict[str, Callable[..., Awaitable[dict[str, Any]]]] = {}

    def list_entries(self) -> list[EvalCapabilityEntry]:
        return list(self._entries)

    def get_by_node(self, node: str) -> EvalCapabilityEntry | None:
        return self._by_node.get(node)

    def get_by_key(self, capability_code: str, action_code: str) -> EvalCapabilityEntry | None:
        key = f"{capability_code}.{action_code}"
        for entry in self._entries:
            if entry.key == key:
                return entry
        return None

    def registered_nodes(self) -> frozenset[str]:
        return frozenset(self._by_node.keys())

    def register_handler(
        self,
        node: str,
        handler: Callable[..., Awaitable[dict[str, Any]]],
    ) -> None:
        self._handlers[node] = handler

    def get_handler(
        self, node: str
    ) -> Callable[..., Awaitable[dict[str, Any]]] | None:
        return self._handlers.get(node)

    def min_active_cases_for(self, capability_code: str) -> int:
        if capability_code in WRITE_FACT_CHARGING_CAPABILITIES:
            return MIN_ACTIVE_CASES_WRITE_FACT
        return MIN_ACTIVE_CASES_DEFAULT


_DEFAULT: CapabilityRegistry | None = None


def get_capability_registry() -> CapabilityRegistry:
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = CapabilityRegistry()
        _register_default_stubs(_DEFAULT)
    return _DEFAULT


def reset_capability_registry() -> None:
    global _DEFAULT
    _DEFAULT = None


async def _stub_dispatch(
    node: str, state: dict[str, Any], llm_response: str = ""
) -> dict[str, Any]:
    """Deterministic stub for non-interview capabilities (no live graph)."""
    return {
        "node": node,
        "stub": True,
        "echo_state_keys": sorted(state.keys()),
        "llm_response_len": len(llm_response or ""),
        "status": "ok",
    }


def _register_default_stubs(registry: CapabilityRegistry) -> None:
    for entry in registry.list_entries():
        if not entry.stub:
            continue
        node = entry.node

        async def _handler(
            state: dict[str, Any],
            *,
            llm_response: str = "",
            _node: str = node,
        ) -> dict[str, Any]:
            return await _stub_dispatch(_node, state, llm_response)

        registry.register_handler(node, _handler)


def load_fixture_capability_codes(
    fixture_path: Path | None = None,
) -> list[str]:
    """Load capability codes from the shared REQ-061 fixture JSON."""
    path = fixture_path or (
        Path(__file__).resolve().parents[2]
        / "tests"
        / "fixtures"
        / "ai_capability_registry.json"
    )
    if not path.is_file():
        return sorted({e.capability_code for e in get_capability_registry().list_entries()})
    payload = json.loads(path.read_text(encoding="utf-8"))
    return sorted(
        {
            str(row["capability_code"])
            for row in payload.get("entries") or []
            if row.get("rollout_status") != "disabled"
        }
    )


def coverage_report(
    active_counts: dict[str, int],
    *,
    class_coverage: dict[str, set[str]] | None = None,
) -> dict[str, Any]:
    """Return per-capability coverage vs FR-112 thresholds (soft report)."""
    registry = get_capability_registry()
    gaps: list[dict[str, Any]] = []
    for entry in registry.list_entries():
        cap = entry.capability_code
        required = entry.min_active_cases
        actual = int(active_counts.get(cap, 0))
        classes = class_coverage.get(cap, set()) if class_coverage else set()
        missing_classes = sorted(REQUIRED_CASE_CLASSES - classes)
        if actual < required or missing_classes:
            gaps.append(
                {
                    "capability_code": cap,
                    "action_code": entry.action_code,
                    "node": entry.node,
                    "active_cases": actual,
                    "required": required,
                    "missing_classes": missing_classes,
                }
            )
    return {
        "schema_version": "061.eval.coverage.v1",
        "gap_count": len(gaps),
        "gaps": gaps,
        "meets_fr112": len(gaps) == 0,
    }


__all__ = [
    "CapabilityRegistry",
    "EvalCapabilityEntry",
    "MIN_ACTIVE_CASES_DEFAULT",
    "MIN_ACTIVE_CASES_WRITE_FACT",
    "NODE_INTERVIEW_REPORT",
    "NODE_INTERVIEW_SCORE",
    "NODE_INTERVIEW_SCORE_LLM",
    "REQUIRED_CASE_CLASSES",
    "RiskClass",
    "WRITE_FACT_CHARGING_CAPABILITIES",
    "coverage_report",
    "get_capability_registry",
    "load_fixture_capability_codes",
    "reset_capability_registry",
]
