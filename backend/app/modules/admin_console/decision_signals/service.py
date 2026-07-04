"""REQ-044 US1 — Decision Signals service layer (FR-007~FR-010).

Pure orchestration: returns a prioritized list of :class:`DecisionSignal`
objects.

Phase-1 seed strategy:

- :func:`seed_demo_signals` returns a curated list of 8 signals that
  covers ALL 6 FR-007 categories AND ALL 4 FR-009 confidence tiers.
  The seed deliberately includes:

    * 3 high-severity signals (so the PM landing surface can be
      verified to surface a prioritized queue — SC-001).
    * 1 candidate (low confidence) signal so the FR-009 visual
      separation can be verified.
    * 1 stale signal so the freshness-stale Edge Case is visible.
    * 1 partial-baseline signal so the partial-baseline Edge Case
      is visible.

- :func:`list_decision_signals` sorts by ``(priority desc,
  freshness_at desc)`` per FR-007.

[CROSS-TEAM-DEBT] Phase 2 batch 2 will replace this seed with a real
aggregator that walks the 6 pm_dashboard panels (overview / funnel /
resume-diagnosis / mock-interview / ai-operations / version-experiment)
and translates metric deltas into DecisionSignals. Until then the seed
is the verifiable surface — tests must NOT mock the service; they
must hit ``list_decision_signals`` directly.

Functions:

- :func:`list_decision_signals` — returns ``DecisionSignalListResponse``
  with sorted signals + counts + quiet_steady_state flag (FR-010).
- :func:`get_command_center_overview` — returns the 4 KPI tiles.
- :func:`seed_demo_signals` — internal helper that returns the curated
  list; pure data, no I/O.

Sort key: ``(priority desc, freshness_at desc)``.

Priority assignment policy (locked at US1, can be tuned later):

- ``critical`` → 900
- ``high``     → 700
- ``medium``   → 500
- ``low``      → 300
- ``info``     → 100
"""
from __future__ import annotations

from datetime import UTC, datetime

from app.modules.admin_console.decision_signals.schemas import (
    CommandCenterOverview,
    CommandCenterOverviewResponse,
    DecisionSignal,
    DecisionSignalListResponse,
    EvidenceLink,
    SignalQualityFlags,
)

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


_SEVERITY_PRIORITY: dict[str, int] = {
    "critical": 900,
    "high": 700,
    "medium": 500,
    "low": 300,
    "info": 100,
}


def _now_iso() -> str:
    """Return current UTC timestamp as ISO 8601 string (no microseconds)."""
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _priorities_for(signals: list[DecisionSignal]) -> list[DecisionSignal]:
    """Stamp the ``priority`` field based on severity if not set.

    Phase-2 batch-2 may override priorities from real metric deltas;
    for now severity is the dominant signal.
    """
    out: list[DecisionSignal] = []
    for sig in signals:
        if sig.priority == 0:
            sig = sig.model_copy(
                update={"priority": _SEVERITY_PRIORITY.get(sig.severity, 0)}
            )
        out.append(sig)
    return out


# ---------------------------------------------------------------------------
# Seed data (Phase 1 — verifiable surface, see module docstring)
# ---------------------------------------------------------------------------


def seed_demo_signals() -> list[DecisionSignal]:
    """Return the curated demo decision-signal list.

    Covers ALL 6 FR-007 categories AND ALL 4 FR-009 confidence tiers
    with at least one stale + one partial-baseline row.
    """
    now = _now_iso()
    earlier = "2026-07-03T22:00:00Z"
    stale = "2026-07-02T10:00:00Z"  # >24h old → stale per AC-10 freshness policy

    return _priorities_for(
        [
            # 1. AI quality — high (top of queue)
            DecisionSignal(
                id="sig-ai-success-rate-drop",
                title="AI 任务成功率近 24h 下降 8.4%",
                category="ai-quality",
                what_changed="ai_success_rate 从 0.842 下降至 0.771（近 24h vs 前 7d）",
                affected_segment="mock_interview / 全部 model='deepseek-v4'",
                comparison_baseline="前 7 天（2026-06-27 ~ 2026-07-03）",
                severity="high",
                confidence="confirmed",
                owner="@ai-quality-oncall",
                freshness_at=now,
                next_review_link="/admin-console/ai-operations?from=sig-ai-success-rate-drop",
                priority=700,
                detected_at=now,
                headline_metric_id="ai_operations.ai_success_rate",
                evidence_links=[
                    EvidenceLink(
                        label="Eval rubric v3.2 failures",
                        href="/admin-console/ai-operations?tab=eval&rubric=v3.2",
                        kind="eval",
                    ),
                    EvidenceLink(
                        label="Badcase #bc-2026-0412",
                        href="/admin-console/incidents-badcases?id=bc-2026-0412",
                        kind="badcase",
                    ),
                ],
            ),
            # 2. AI cost — high
            DecisionSignal(
                id="sig-ai-cost-increase",
                title="近 24h Token 成本上升 22%，质量未提升",
                category="ai-cost",
                what_changed="estimated_cost_usd 从 142.30 上升至 173.85；ai_success_rate 同期下降",
                affected_segment="resume_optimize / 全部 cohort",
                comparison_baseline="前 7 天（2026-06-27 ~ 2026-07-03）",
                severity="high",
                confidence="confirmed",
                owner="@ai-cost-oncall",
                freshness_at=now,
                next_review_link="/admin-console/ai-operations?from=sig-ai-cost-increase",
                priority=700,
                detected_at=now,
                headline_metric_id="ai_operations.estimated_cost_usd",
                evidence_links=[
                    EvidenceLink(
                        label="Resume optimize token breakdown",
                        href="/admin-console/ai-operations?tab=cost&feature=resume_optimize",
                        kind="metric",
                    ),
                ],
            ),
            # 3. Product — critical (funnel drop)
            DecisionSignal(
                id="sig-funnel-drop",
                title="注册 → 首次模拟面试转化率下降 12.6%",
                category="product",
                what_changed="funnel.registered_to_first_interview 从 0.412 下降至 0.286",
                affected_segment="registered cohort（过去 24h）",
                comparison_baseline="前 7 天（2026-06-27 ~ 2026-07-03）",
                severity="critical",
                confidence="confirmed",
                owner="@pm-oncall",
                freshness_at=now,
                next_review_link="/admin-console/product-analytics?funnel=registered_to_first_interview",
                priority=900,
                detected_at=now,
                headline_metric_id="funnel.registered_to_first_interview",
                evidence_links=[
                    EvidenceLink(
                        label="Funnel definition",
                        href="/admin-console/product-analytics?funnel=registered_to_first_interview",
                        kind="metric",
                    ),
                ],
            ),
            # 4. System health — medium
            DecisionSignal(
                id="sig-system-incident",
                title="Incident #inc-2026-0703-001 仍未关闭",
                category="system-health",
                what_changed="affects 1.2% of recent ai tasks；first_seen 距今 14h",
                affected_segment="ai task type='error_coach'",
                comparison_baseline="过去 30 天基线 incident rate",
                severity="medium",
                confidence="sampled",
                owner="@ops-oncall",
                freshness_at=earlier,
                next_review_link="/admin-console/incidents-badcases?id=inc-2026-0703-001",
                priority=500,
                detected_at=earlier,
                headline_metric_id=None,
                evidence_links=[
                    EvidenceLink(
                        label="Incident detail",
                        href="/admin-console/incidents-badcases?id=inc-2026-0703-001",
                        kind="report",
                    ),
                ],
            ),
            # 5. Incident — high
            DecisionSignal(
                id="sig-incident-feedback-delay",
                title="feedback 提交失败率上升（sampled）",
                category="incident",
                what_changed="feedback submit failure rate 从 0.5% 上升至 3.8%（基于采样 12% 流量）",
                affected_segment="interview.complete → feedback.submit",
                comparison_baseline="前 7 天",
                severity="high",
                confidence="sampled",
                owner="@ops-oncall",
                freshness_at=now,
                next_review_link="/admin-console/incidents-badcases?from=sig-incident-feedback-delay",
                priority=700,
                detected_at=now,
                headline_metric_id=None,
                evidence_links=[
                    EvidenceLink(
                        label="Trace sample",
                        href="/admin-console/logs-and-traces?task_type=feedback_submit",
                        kind="trace",
                    ),
                ],
            ),
            # 6. Data quality — partial baseline (Edge Case 322)
            DecisionSignal(
                id="sig-data-partial-baseline",
                title="comparison_baseline 不完整：mock_interview 7d 数据缺 18h",
                category="data-quality",
                what_changed="comparison period 2026-06-27 ~ 2026-07-03 仅覆盖 84% 的预期窗口",
                affected_segment="mock_interview 全部 cohort",
                comparison_baseline="前 7 天（partial baseline —— 数据延迟到达）",
                severity="info",
                confidence="inferred",
                owner="@data-quality-oncall",
                freshness_at=now,
                next_review_link="/admin-console/governance?tab=data-quality",
                priority=100,
                detected_at=now,
                headline_metric_id=None,
                evidence_links=[],
                quality_flags=SignalQualityFlags(
                    partial_baseline=True,
                    delayed_ingestion=True,
                    missing_version_fields=["model"],
                ),
            ),
            # 7. Data quality — stale (Edge Case 320)
            DecisionSignal(
                id="sig-data-stale",
                title="ability_diagnose 数据新鲜度 > 24h",
                category="data-quality",
                what_changed="ability_diagnose.freshness_at 距今 31h，超过 24h 阈值",
                affected_segment="ability_diagnose 全部用户",
                comparison_baseline="前 7 天",
                severity="low",
                confidence="inferred",
                owner="@data-quality-oncall",
                freshness_at=stale,
                next_review_link="/admin-console/governance?tab=freshness",
                priority=300,
                detected_at=stale,
                headline_metric_id=None,
                evidence_links=[],
                quality_flags=SignalQualityFlags(stale=True, delayed_ingestion=True),
            ),
            # 8. candidate — low confidence (FR-009)
            DecisionSignal(
                id="sig-candidate-feature-adoption",
                title="error_book repeat-use 候选信号（低置信度）",
                category="product",
                what_changed="error_book repeat-use 7d retention 估计下降，但样本不足（n=14）",
                affected_segment="error_book / 7d active users",
                comparison_baseline="前 14 天（n=210）",
                severity="low",
                confidence="candidate",
                owner="@pm-oncall",
                freshness_at=now,
                next_review_link="/admin-console/product-analytics?cohort=error_book&feature=repeat_use",
                priority=300,
                detected_at=now,
                headline_metric_id=None,
                evidence_links=[],
                quality_flags=SignalQualityFlags(sampled_data=True, partial_data=True),
            ),
        ]
    )


# ---------------------------------------------------------------------------
# Public service API
# ---------------------------------------------------------------------------


def list_decision_signals() -> DecisionSignalListResponse:
    """Return the prioritized decision-signal queue.

    Sort order: ``priority desc`` then ``freshness_at desc``.
    Returns the full :class:`DecisionSignalListResponse` envelope
    including ``high_severity_count``, ``quiet_steady_state``,
    ``freshness_at``, ``last_reviewed_at``, ``open_reviews``.
    """
    signals = seed_demo_signals()

    # Sort: priority desc, freshness_at desc. Unknown freshness sorts
    # last because ISO strings sort lexically and "unknown" begins
    # with 'u' which is > any digit — so "unknown" naturally lands
    # at the bottom, which is the desired UX.
    signals.sort(key=lambda s: (s.priority, s.freshness_at), reverse=True)

    high_severity_count = sum(1 for s in signals if s.severity in {"critical", "high"})

    return DecisionSignalListResponse(
        signals=signals,
        total=len(signals),
        high_severity_count=high_severity_count,
        quiet_steady_state=high_severity_count == 0,
        freshness_at=_now_iso(),
        # [CROSS-TEAM-DEBT] Phase 2 batch 2: last_reviewed_at will be
        # computed from the review_queue table. For US1 we hardcode a
        # recent timestamp so the QuietState visual still renders.
        last_reviewed_at="2026-07-03T16:42:00Z",
        open_reviews=2,
    )


def get_command_center_overview() -> CommandCenterOverviewResponse:
    """Return the 4 KPI tiles for the workspace header.

    [CROSS-TEAM-DEBT] Phase 2 batch 2 will replace these static values
    with real reads from the pm_dashboard overview panel.
    """
    overview = CommandCenterOverview(
        product_health=0.78,
        product_health_unit="score",
        ai_quality=0.771,
        ai_quality_unit="rate",
        ai_cost=173.85,
        ai_cost_unit="usd",
        system_health=0.92,
        system_health_unit="score",
        freshness_at=_now_iso(),
    )
    return CommandCenterOverviewResponse(
        overview=overview,
        freshness_at=_now_iso(),
    )


__all__ = [
    "get_command_center_overview",
    "list_decision_signals",
    "seed_demo_signals",
]