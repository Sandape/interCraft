"""REQ-061 locked milestone price catalog (T049 / FR-064).

Tasks lock a price-table version at quote/acceptance. Later catalog edits
create a new version; this module exposes the initial locked rates and
lookup helpers used by quotes and settlement.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

INITIAL_DAILY_GRANT_POINTS = 2000
INITIAL_PRICE_TABLE_VERSION = "points-v1"


@dataclass(frozen=True, slots=True)
class MilestonePrice:
    code: str
    weight: float  # fraction of max_points (sum ≈ 1.0)


@dataclass(frozen=True, slots=True)
class PriceEntry:
    capability_code: str
    action_code: str
    service_tier: str
    max_points: int
    milestones: tuple[MilestonePrice, ...]
    billing_note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "capability_code": self.capability_code,
            "action_code": self.action_code,
            "service_tier": self.service_tier,
            "max_points": self.max_points,
            "milestones": [
                {"code": m.code, "weight": m.weight} for m in self.milestones
            ],
            "billing_note": self.billing_note,
        }


def _entry(
    capability: str,
    action: str,
    *,
    standard: int,
    quality: int,
    milestones: Sequence[tuple[str, float]],
    note: str = "",
) -> list[PriceEntry]:
    ms = tuple(MilestonePrice(code=c, weight=w) for c, w in milestones)
    return [
        PriceEntry(
            capability_code=capability,
            action_code=action,
            service_tier="standard",
            max_points=standard,
            milestones=ms,
            billing_note=note,
        ),
        PriceEntry(
            capability_code=capability,
            action_code=action,
            service_tier="quality",
            max_points=quality,
            milestones=ms,
            billing_note=note,
        ),
    ]


# FR-064 first-ship point table (capability/action codes locked for adapters).
INITIAL_PRICE_TABLE: tuple[PriceEntry, ...] = tuple(
    [
        *_entry(
            "resume_checkup",
            "analyze_and_suggest",
            standard=40,
            quality=100,
            milestones=[("analysis", 0.7), ("suggestions", 0.3)],
            note="分析 70%，建议 30%",
        ),
        *_entry(
            "resume_intelligence",
            "analyze",
            standard=60,
            quality=150,
            milestones=[("analysis", 0.7), ("suggestions", 0.3)],
            note="分析 70%，建议 30%",
        ),
        *_entry(
            "resume_derive",
            "derive",
            standard=120,
            quality=300,
            milestones=[
                ("draft", 0.6),
                ("job_analysis", 0.25),
                ("suggestions", 0.15),
            ],
            note="派生稿 60%，分析 25%，建议 15%",
        ),
        *_entry(
            "resume_intelligence",
            "suggest",
            standard=20,
            quality=50,
            milestones=[("suggestions", 1.0)],
            note="成功交付新建议后计费",
        ),
        *_entry(
            "interview",
            "quick_5",
            standard=80,
            quality=200,
            milestones=[("round_score", 0.8), ("report", 0.2)],
            note="各轮合计 80%，报告 20%",
        ),
        *_entry(
            "interview",
            "full_10",
            standard=180,
            quality=450,
            milestones=[("round_score", 0.8), ("report", 0.2)],
            note="各轮合计 80%，报告 20%",
        ),
        *_entry(
            "interview",
            "full_15",
            standard=260,
            quality=650,
            milestones=[("round_score", 0.8), ("report", 0.2)],
            note="各轮合计 80%，报告 20%",
        ),
        *_entry(
            "error_coach",
            "drill",
            standard=40,
            quality=100,
            milestones=[("scored_round", 1.0)],
            note="按已完成评分轮次等比例结算",
        ),
        *_entry(
            "general_coach",
            "answer",
            standard=3,
            quality=8,
            milestones=[("assistant_answer", 1.0)],
            note="回答正文交付后计费",
        ),
        *_entry(
            "wechat_agent",
            "run",
            standard=3,
            quality=8,
            milestones=[("user_reply", 1.0)],
            note="成功回答或已确认工具结果后计费",
        ),
        *_entry(
            "proactive_research",
            "research",
            standard=100,
            quality=250,
            milestones=[("sourced_report", 1.0)],
            note="完整报告成功交付后一次性计费",
        ),
        *_entry(
            "ability_insight",
            "diagnose",
            standard=0,
            quality=0,
            milestones=[("ai_insight", 1.0)],
            note="已包含在面试费用中",
        ),
    ]
)

_INDEX: dict[tuple[str, str, str], PriceEntry] = {
    (e.capability_code, e.action_code, e.service_tier): e for e in INITIAL_PRICE_TABLE
}


def lookup_price(
    *,
    capability_code: str,
    action_code: str,
    service_tier: str,
    table: Sequence[PriceEntry] | None = None,
) -> PriceEntry:
    """Resolve a locked capability/action/tier price entry."""
    if table is None:
        entry = _INDEX.get((capability_code, action_code, service_tier))
        if entry is None:
            raise KeyError(
                f"no price for {capability_code}/{action_code}/{service_tier}"
            )
        return entry
    for candidate in table:
        if (
            candidate.capability_code == capability_code
            and candidate.action_code == action_code
            and candidate.service_tier == service_tier
        ):
            return candidate
    raise KeyError(f"no price for {capability_code}/{action_code}/{service_tier}")


def milestone_charge(
    *,
    capability_code: str,
    action_code: str,
    service_tier: str,
    delivered_milestones: Sequence[str],
    table: Sequence[PriceEntry] | None = None,
) -> int:
    """Charge points for delivered milestones (partial settlement).

    Uses fractional weights from FR-064. Total never exceeds ``max_points``.
    """
    entry = lookup_price(
        capability_code=capability_code,
        action_code=action_code,
        service_tier=service_tier,
        table=table,
    )
    delivered = set(delivered_milestones)
    charged = 0
    for milestone in entry.milestones:
        if milestone.code in delivered:
            charged += int(round(entry.max_points * milestone.weight))
    return min(charged, entry.max_points)


def initial_price_table_entries() -> list[dict[str, Any]]:
    """JSON-serializable entries for ``PointPriceTableVersion.entries``."""
    return [e.to_dict() for e in INITIAL_PRICE_TABLE]


__all__ = [
    "INITIAL_DAILY_GRANT_POINTS",
    "INITIAL_PRICE_TABLE",
    "INITIAL_PRICE_TABLE_VERSION",
    "MilestonePrice",
    "PriceEntry",
    "initial_price_table_entries",
    "lookup_price",
    "milestone_charge",
]
