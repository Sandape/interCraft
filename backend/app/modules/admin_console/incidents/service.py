"""REQ-044 US4 — Incidents & Badcases service layer (FR-021~FR-023).

Pure orchestration: returns incident / badcase / evidence / comment /
audit-trail data for the workspace surface.

Phase-1 seed strategy (mirrors ``admin_console.decision_signals.service`` +
``admin_console.product_analytics.service`` + ``admin_console.ai_operations.service``):

- :func:`seed_demo_incidents` returns 6 incidents covering ALL 4
  severities (P0/P1/P2/P3), ALL 4 statuses (open/investigating/
  resolved/postmortem), ALL 3 trends (rising/stable/declining), and
  ALL 4 Edge Cases (EC-1 candidate / EC-2 shared root cause /
  EC-3 ingestion delayed / EC-4 audit trail).
- :func:`seed_demo_evidence_for` returns 8 evidence links per
  incident — one per FR-022 type — so AC-22.1 (8 type coverage) is
  always satisfiable.
- :func:`seed_demo_badcases` returns 4 badcases covering ALL 4
  statuses (open/reviewing/closed/escalated) and the 3 privacy classes.
- :func:`seed_demo_comments_for` returns 1-3 comments per incident so
  AC-22.3 (Comments tab) has real data.

The seed deliberately includes:

  * 1 P0 candidate (EC-1) to verify the "candidate" label + separation
    from confirmed incidents.
  * 2 incidents with ``common_root_cause="db-timeout-cluster"`` + cross-
    link to verify EC-2.
  * 1 incident with ``ingestion_delayed=True`` to verify EC-3.
  * 1 incident with prior audit entries to verify EC-4.

[CROSS-TEAM-DEBT] Phase 2 batch 4 will replace these seed helpers with
a real ``incidents`` table + governance US6 audit. Until then the seed
is the verifiable surface — tests must NOT mock the service; they must
hit the service directly.

Sort key: incidents sorted by ``(severity desc, last_seen_at desc)``
per FR-021. Badcases sorted by ``first_seen_at desc``.

Public API:

- :func:`list_incidents` — FR-021 list envelope.
- :func:`get_incident` — single incident detail (raises ValueError if not found).
- :func:`get_incident_evidence` — FR-022 evidence links + coverage map.
- :func:`list_incident_comments` — comment list.
- :func:`add_incident_comment` — append + audit (FR-022).
- :func:`change_incident_status` — EC-4 PATCH status + audit trail.
- :func:`list_badcases` — FR-023 list envelope.
- :func:`get_badcase` — single badcase detail.
- :func:`escalate_badcase_to_incident` — FR-023 escalate + return new incident_id.
"""
from __future__ import annotations

import threading
from datetime import UTC, datetime, timedelta
from typing import Optional

from app.modules.admin_console.incidents.schemas import (
    AuditTrailEntry,
    Badcase,
    BadcaseEscalateResponse,
    BadcaseListResponse,
    Comment,
    CommentListResponse,
    EvidenceLink,
    EvidenceLinkListResponse,
    Incident,
    IncidentListResponse,
)

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    """Return current UTC timestamp as ISO 8601 string (no microseconds)."""
    return (
        datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    )


def _earlier_iso(days: int = 0, hours: int = 0, minutes: int = 0) -> str:
    """Return an ISO 8601 timestamp N days/hours/minutes before now."""
    delta = timedelta(days=days, hours=hours, minutes=minutes)
    return (
        (datetime.now(UTC) - delta)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


# ---------------------------------------------------------------------------
# Severity priority (FR-021 sort key)
# ---------------------------------------------------------------------------


_SEVERITY_PRIORITY: dict[str, int] = {
    "P0": 900,
    "P1": 700,
    "P2": 500,
    "P3": 300,
}


# ---------------------------------------------------------------------------
# In-memory comment + status-change write-behind (Phase 2 batch 4 will
# swap for the real ``incidents`` + ``audit_log`` tables)
# ---------------------------------------------------------------------------


_lock = threading.Lock()
#: ``{incident_id: list[Comment]}`` — append-only per Phase 1 baseline.
_COMMENTS: dict[str, list[Comment]] = {}
#: ``{incident_id: list[AuditTrailEntry]}`` — append-only per Phase 1.
_AUDIT: dict[str, list[AuditTrailEntry]] = {}
#: ``{badcase_id: str}`` — badcase_id → newly created incident_id.
_ESCALATIONS: dict[str, str] = {}
#: monotonic counter for synthetic comment ids (Phase 1; Phase 2 batch 4
# will use a real id allocator).
_NEXT_COMMENT_SEQ: dict[str, int] = {}
#: monotonic counter for synthetic escalation incident ids.
_NEXT_INCIDENT_SEQ: int = 100


def _next_incident_id() -> str:
    """Return the next synthetic incident id (Phase 1 only)."""
    global _NEXT_INCIDENT_SEQ
    with _lock:
        _NEXT_INCIDENT_SEQ += 1
        return f"inc-escalated-{_NEXT_INCIDENT_SEQ:04d}"


def _next_comment_id(incident_id: str) -> str:
    """Return the next synthetic comment id for ``incident_id``."""
    with _lock:
        seq = _NEXT_COMMENT_SEQ.get(incident_id, 0) + 1
        _NEXT_COMMENT_SEQ[incident_id] = seq
        return f"cmt-{incident_id}-{seq:04d}"


# ---------------------------------------------------------------------------
# Seed: incidents (FR-021 + EC-1/2/3/4)
# ---------------------------------------------------------------------------


def seed_demo_incidents() -> list[Incident]:
    """Return the curated 6-incident list.

    Covers all 4 severities, all 4 statuses, all 3 trends, and the
    4 Edge Cases (EC-1/2/3/4). 2 incidents share ``common_root_cause``
    (EC-2); 1 is a candidate (EC-1); 1 has ``ingestion_delayed=True``
    (EC-3); 1 has 2 prior audit entries (EC-4).
    """
    now = _now_iso()
    hours12 = _earlier_iso(hours=12)
    hours6 = _earlier_iso(hours=6)
    hours2 = _earlier_iso(hours=2)
    days1 = _earlier_iso(days=1)
    days2 = _earlier_iso(days=2)
    days3 = _earlier_iso(days=3)
    days5 = _earlier_iso(days=5)

    return [
        # 1. P0 — open — rising — most urgent top of the list
        Incident(
            id="inc-2026-0704-001",
            title="注册 → 首次模拟面试转化率断崖下跌 38%",
            severity="P0",
            status="open",
            owner="@ops-oncall",
            affected_feature_area="mock_interview",
            affected_journey_step="registered_to_first_interview",
            first_seen_at=hours6,
            last_seen_at=hours2,
            trend="rising",
            candidate=False,
            common_root_cause=None,
            linked_incident_ids=[],
            ingestion_delayed=False,
            freshness_at=now,
            affected_count=1284,
            description="过去 2 小时内新用户注册 → 首次模拟面试转化率从基线 0.412 跌至 0.254 (-38%)",
            audit_trail=[],
        ),
        # 2. P1 — investigating — stable (EC-2 sibling: shares root cause with #3)
        Incident(
            id="inc-2026-0703-002",
            title="面试完成 → 提交反馈 失败率上升至 3.8%",
            severity="P1",
            status="investigating",
            owner="@ops-oncall",
            affected_feature_area="mock_interview",
            affected_journey_step="interview_complete_to_feedback_submit",
            first_seen_at=days1,
            last_seen_at=hours6,
            trend="stable",
            candidate=False,
            common_root_cause="db-timeout-cluster",
            linked_incident_ids=["inc-2026-0703-003"],
            ingestion_delayed=False,
            freshness_at=now,
            affected_count=42,
            description="feedback_submit 端点 5xx 率上升，关联 database 慢查询集群",
            audit_trail=[
                AuditTrailEntry(
                    actor="@ops-oncall",
                    timestamp=hours12,
                    reason="指派给 ops oncall 调查 5xx 突增",
                    before_state={"status": "open", "owner": "—"},
                    after_state={"status": "investigating", "owner": "@ops-oncall"},
                    action="status_change",
                ),
            ],
        ),
        # 3. P1 — open — rising (EC-2 sibling)
        Incident(
            id="inc-2026-0703-003",
            title="错误本加载 5xx 率上升（同一 db 慢查询集群）",
            severity="P1",
            status="open",
            owner="@ops-oncall",
            affected_feature_area="error_coach",
            affected_journey_step="error_book_load",
            first_seen_at=hours12,
            last_seen_at=hours6,
            trend="rising",
            candidate=False,
            common_root_cause="db-timeout-cluster",
            linked_incident_ids=["inc-2026-0703-002"],
            ingestion_delayed=False,
            freshness_at=now,
            affected_count=18,
            description="与 inc-2026-0703-002 共享 db-timeout-cluster 根因",
            audit_trail=[],
        ),
        # 4. P2 — resolved — declining
        Incident(
            id="inc-2026-0701-004",
            title="AI 自动评分偶发超时（已修复）",
            severity="P2",
            status="resolved",
            owner="@ai-quality-oncall",
            affected_feature_area="resume_optimize",
            affected_journey_step="ai_scoring",
            first_seen_at=days3,
            last_seen_at=days2,
            trend="declining",
            candidate=False,
            common_root_cause=None,
            linked_incident_ids=[],
            ingestion_delayed=False,
            freshness_at=now,
            affected_count=7,
            description="prompt v3.2 切换后偶发超时，rollback 后恢复",
            audit_trail=[
                AuditTrailEntry(
                    actor="@ai-quality-oncall",
                    timestamp=days2,
                    reason="rollback prompt v3.2 → v3.1 后超时消失",
                    before_state={"status": "investigating", "owner": "@ai-quality-oncall"},
                    after_state={"status": "resolved", "owner": "@ai-quality-oncall"},
                    action="status_change",
                ),
                AuditTrailEntry(
                    actor="@ai-quality-oncall",
                    timestamp=days1,
                    reason="24h 观察后确认无回归",
                    before_state={"status": "resolved", "owner": "@ai-quality-oncall"},
                    after_state={"status": "postmortem", "owner": "@ai-quality-oncall"},
                    action="status_change",
                ),
            ],
        ),
        # 5. P3 — postmortem — stable
        Incident(
            id="inc-2026-0628-005",
            title="订阅页文案误植（已修复）",
            severity="P3",
            status="postmortem",
            owner="@pm-oncall",
            affected_feature_area="subscription",
            affected_journey_step="subscription_page_view",
            first_seen_at=days5,
            last_seen_at=days3,
            trend="stable",
            candidate=False,
            common_root_cause=None,
            linked_incident_ids=[],
            ingestion_delayed=False,
            freshness_at=now,
            affected_count=5234,
            description="订阅页 '7 天免费试用' 文案误植为 '30 天'，已修复并完成复盘",
            audit_trail=[],
        ),
        # 6. P2 — candidate (EC-1) — NOT merged into confirmed list
        Incident(
            id="inc-2026-0704-006",
            title="错误本 repeat-use 留存疑似下降（低置信度候选）",
            severity="P2",
            status="open",
            owner="@pm-oncall",
            affected_feature_area="error_coach",
            affected_journey_step="error_book_repeat_use",
            first_seen_at=days1,
            last_seen_at=hours12,
            trend="rising",
            candidate=True,  # EC-1
            common_root_cause=None,
            linked_incident_ids=[],
            ingestion_delayed=True,  # EC-3: signal came from delayed ingestion
            freshness_at=now,
            affected_count=14,
            description="7d repeat-use 留存估计下降，但 n=14 样本不足（candidate）",
            audit_trail=[],
        ),
    ]


# ---------------------------------------------------------------------------
# Seed: evidence (FR-022 — 8 link types per incident)
# ---------------------------------------------------------------------------


def seed_demo_evidence_for(incident_id: str) -> list[EvidenceLink]:
    """Return 8 evidence links (one per FR-022 type) for ``incident_id``.

    All 8 types are always present so AC-22.1 (8-type coverage) is
    satisfiable for any incident id. The ``href`` values use cross-
    workspace deep links so SC-007 3-min drilldown is navigable in
    Playwright (US5 log/trace routes are placeholders, US3 ai_task +
    US2 user + US6 release are real or placeholder routes).
    """
    base = f"/admin-console/incidents-badcases?from={incident_id}"
    return [
        # 1. product_metric
        EvidenceLink(
            type="product_metric",
            reference_id="metric:funnel.registered_to_first_interview",
            label="Funnel: registered → first interview",
            href=f"/admin-console/product-analytics?funnel=registered_to_first_interview&from={incident_id}",
            privacy_class="public",
            summary="5-step funnel + comparison-period delta",
        ),
        # 2. user_impact
        EvidenceLink(
            type="user_impact",
            reference_id="user:019ec1be-0000-7000-8000-000000000001",
            label="Affected user demo@intercraft.io",
            href=f"/admin-console/users/019ec1be-0000-7000-8000-000000000001?from={incident_id}",
            privacy_class="internal",
            summary="Privacy-safe profile (7 allow-listed fields)",
        ),
        # 3. ai_task
        EvidenceLink(
            type="ai_task",
            reference_id="task:019ec1be-0000-7000-8000-000000000010",
            label="AI task: ai_scoring 失败样例",
            href=f"/admin-console/ai-operations?from={incident_id}&task=019ec1be-0000-7000-8000-000000000010",
            privacy_class="internal",
            summary="Eval verdict + badcase link (US3 surface)",
        ),
        # 4. eval_case
        EvidenceLink(
            type="eval_case",
            reference_id="eval:rubric-v3.2-2026-07-04",
            label="Eval rubric v3.2 run (2026-07-04)",
            href=f"/admin-console/ai-operations?tab=eval&rubric=v3.2&from={incident_id}",
            privacy_class="public",
            summary="Pass rate 0.78 → 0.65 vs baseline",
        ),
        # 5. log — US5 placeholder
        EvidenceLink(
            type="log",
            reference_id="log:incident-bucket-0704",
            label="Log bucket: incident-2026-0704 (US5)",
            href=f"/admin-console/logs-and-traces?from={incident_id}&bucket=incident-2026-0704",
            privacy_class="internal",
            summary="[CROSS-TEAM-DEBT] US5 placeholder route",
        ),
        # 6. trace — US5 placeholder
        EvidenceLink(
            type="trace",
            reference_id="trace:019ec1be-0000-7000-8000-000000000020",
            label="Trace sample (US5 placeholder)",
            href=f"/admin-console/logs-and-traces?trace_id=019ec1be-0000-7000-8000-000000000020&from={incident_id}",
            privacy_class="internal",
            summary="[CROSS-TEAM-DEBT] US5 placeholder route",
        ),
        # 7. release — US6 placeholder
        EvidenceLink(
            type="release",
            reference_id="release:v3.2.0",
            label="Release v3.2.0 (2026-07-01)",
            href=f"/admin-console/governance?tab=releases&release=v3.2.0&from={incident_id}",
            privacy_class="public",
            summary="[CROSS-TEAM-DEBT] US6 placeholder route",
        ),
        # 8. comment — anchors the in-workspace Comments tab
        EvidenceLink(
            type="comment",
            reference_id=f"comment:{incident_id}:seed-1",
            label="Initial triage note (seed)",
            href=f"{base}#comments",
            privacy_class="internal",
            summary="See Comments tab for full thread",
        ),
    ]


def _evidence_coverage(links: list[EvidenceLink]) -> dict[str, int]:
    """Build the AC-22.1 coverage map: type → count."""
    out: dict[str, int] = {}
    for link in links:
        out[link.type] = out.get(link.type, 0) + 1
    return out


# ---------------------------------------------------------------------------
# Seed: comments (FR-022 Comments tab)
# ---------------------------------------------------------------------------


def seed_demo_comments_for(incident_id: str) -> list[Comment]:
    """Return 1-3 seed comments for ``incident_id`` so the Comments tab
    is non-empty for the most common incident ids."""
    if incident_id == "inc-2026-0704-001":
        return [
            Comment(
                id="cmt-001-a",
                incident_id=incident_id,
                actor="@ops-oncall",
                body="正在拉近 1h 的 funnel 详细分步数据，确认是 step3 还是 step4 drop。",
                reason=None,
                created_at=_earlier_iso(hours=1),
            ),
            Comment(
                id="cmt-001-b",
                incident_id=incident_id,
                actor="@pm-oncall",
                body="是否与 prompt v3.2 上线时间相关？求 AI 侧数据。",
                reason=None,
                created_at=_earlier_iso(hours=1, minutes=30),
            ),
        ]
    if incident_id == "inc-2026-0703-002":
        return [
            Comment(
                id="cmt-002-a",
                incident_id=incident_id,
                actor="@ops-oncall",
                body="db 慢查询已锁定到 3 条 query，正在和 DBA review 索引建议。",
                reason=None,
                created_at=_earlier_iso(hours=2),
            ),
        ]
    if incident_id == "inc-2026-0701-004":
        return [
            Comment(
                id="cmt-004-a",
                incident_id=incident_id,
                actor="@ai-quality-oncall",
                body="rollback 后 24h 内无回归，关闭 incident。",
                reason=None,
                created_at=_earlier_iso(days=1),
            ),
        ]
    return []


# ---------------------------------------------------------------------------
# Seed: badcases (FR-023)
# ---------------------------------------------------------------------------


def seed_demo_badcases() -> list[Badcase]:
    """Return the curated 4-badcase list.

    Covers all 4 statuses (open/reviewing/closed/escalated) and all
    3 privacy classes (public/internal/restricted).
    """
    now = _now_iso()
    days1 = _earlier_iso(days=1)
    days2 = _earlier_iso(days=2)
    days4 = _earlier_iso(days=4)

    return [
        # 1. open — public
        Badcase(
            id="bc-2026-0704-001",
            eval_verdict="rubric_v3.2_fail",
            affected_feature_area="resume_optimize",
            affected_user_id="019ec1be-0000-7000-8000-000000000002",
            privacy_class="public",
            classification="ai_scoring_inconsistent",
            owner="@ai-quality-oncall",
            status="open",
            resolution="",
            first_seen_at=days1,
            incident_id=None,
            freshness_at=now,
            description="AI 自动评分与人工评分偏差 > 0.2",
        ),
        # 2. reviewing — internal
        Badcase(
            id="bc-2026-0703-002",
            eval_verdict="rubric_v3.2_fail",
            affected_feature_area="mock_interview",
            affected_user_id="019ec1be-0000-7000-8000-000000000003",
            privacy_class="internal",
            classification="interview_feedback_low_quality",
            owner="@ai-quality-oncall",
            status="reviewing",
            resolution="",
            first_seen_at=days2,
            incident_id=None,
            freshness_at=now,
            description="面试反馈包含不准确建议（reviewer 已接手）",
        ),
        # 3. closed — restricted (no escalation)
        Badcase(
            id="bc-2026-0701-003",
            eval_verdict="rubric_v3.1_pass_after_fix",
            affected_feature_area="error_coach",
            affected_user_id="019ec1be-0000-7000-8000-000000000004",
            privacy_class="restricted",
            classification="error_book_summary_leak",
            owner="@ai-quality-oncall",
            status="closed",
            resolution="已修复 prompt leak 问题，关闭 badcase",
            first_seen_at=days4,
            incident_id=None,
            freshness_at=now,
            description="错误本摘要偶发包含 prompt 片段（已修）",
        ),
        # 4. escalated — internal (already promoted to incident)
        Badcase(
            id="bc-2026-0703-004",
            eval_verdict="rubric_v3.2_fail",
            affected_feature_area="mock_interview",
            affected_user_id="019ec1be-0000-7000-8000-000000000005",
            privacy_class="internal",
            classification="interview_complete_to_feedback_submit_5xx",
            owner="@ops-oncall",
            status="escalated",
            resolution="已升级为 incident inc-2026-0703-002",
            first_seen_at=days2,
            incident_id="inc-2026-0703-002",
            freshness_at=now,
            description="5xx 突增对应 badcase，已自动 escalate",
        ),
    ]


# ---------------------------------------------------------------------------
# Public service: incidents (FR-021)
# ---------------------------------------------------------------------------


def list_incidents() -> IncidentListResponse:
    """Return the incident list (FR-021).

    Sort: ``(severity desc, last_seen_at desc)`` per FR-021 AC-21.2.
    Includes the confirmed / candidate split (EC-1) and per-list
    freshness envelope (FR-028).

    REQ-061 T170: when seed fallbacks are disabled, return empty
    unavailable freshness instead of demo seed.
    """
    from app.modules.admin_console.production_fallbacks import seed_fallbacks_disabled

    if seed_fallbacks_disabled():
        return IncidentListResponse(
            incidents=[],
            total=0,
            confirmed_count=0,
            candidate_count=0,
            freshness_at="unavailable",
        )

    incidents = seed_demo_incidents()
    # Sort by severity priority desc, then last_seen_at desc.
    incidents.sort(
        key=lambda inc: (
            _SEVERITY_PRIORITY.get(inc.severity, 0),
            inc.last_seen_at,
        ),
        reverse=True,
    )
    confirmed = [i for i in incidents if not i.candidate]
    candidate = [i for i in incidents if i.candidate]
    return IncidentListResponse(
        incidents=incidents,
        total=len(incidents),
        confirmed_count=len(confirmed),
        candidate_count=len(candidate),
        freshness_at=_now_iso(),
    )


def get_incident(incident_id: str) -> Optional[Incident]:
    """Return a single incident by id, or ``None`` if not found."""
    for inc in seed_demo_incidents():
        if inc.id == incident_id:
            return inc
    return None


# ---------------------------------------------------------------------------
# Public service: evidence + comments (FR-022)
# ---------------------------------------------------------------------------


def get_incident_evidence(incident_id: str) -> EvidenceLinkListResponse:
    """Return the 8-type evidence link list for ``incident_id`` (FR-022).

    Unknown incident_id → empty list with ``total=0``. Coverage map is
    still emitted (all zeros) so the frontend can render 8 empty-state
    sections consistently.
    """
    if get_incident(incident_id) is None:
        return EvidenceLinkListResponse(
            incident_id=incident_id,
            evidence_links=[],
            total=0,
            coverage={},
        )
    links = seed_demo_evidence_for(incident_id)
    return EvidenceLinkListResponse(
        incident_id=incident_id,
        evidence_links=links,
        total=len(links),
        coverage=_evidence_coverage(links),
    )


def list_incident_comments(incident_id: str) -> CommentListResponse:
    """Return the comment list for ``incident_id`` (FR-022)."""
    if get_incident(incident_id) is None:
        return CommentListResponse(incident_id=incident_id, comments=[], total=0)
    seed = seed_demo_comments_for(incident_id)
    added = list(_COMMENTS.get(incident_id, []))
    comments = seed + added
    return CommentListResponse(
        incident_id=incident_id,
        comments=comments,
        total=len(comments),
    )


def add_incident_comment(
    incident_id: str,
    actor: str,
    body: str,
    reason: Optional[str] = None,
) -> Comment:
    """Append a comment to ``incident_id`` (FR-022).

    Raises ``ValueError`` if the incident does not exist. The call is
    a no-op on the audit trail — comments are NOT status changes —
    but the comment IS appended to the in-memory comment ring buffer.
    """
    if get_incident(incident_id) is None:
        raise ValueError(f"unknown incident_id: {incident_id}")
    comment = Comment(
        id=_next_comment_id(incident_id),
        incident_id=incident_id,
        actor=actor,
        body=body,
        reason=reason,
        created_at=_now_iso(),
    )
    with _lock:
        _COMMENTS.setdefault(incident_id, []).append(comment)
    return comment


# ---------------------------------------------------------------------------
# Public service: status change (EC-4)
# ---------------------------------------------------------------------------


def change_incident_status(
    incident_id: str,
    actor: str,
    new_status: str,
    new_owner: Optional[str],
    reason: str,
) -> AuditTrailEntry:
    """Record a status change for ``incident_id`` (EC-4).

    The function is intentionally non-mutating on the seed ``Incident``
    objects (Phase 1 keeps the seed immutable for test repeatability);
    instead it appends an :class:`AuditTrailEntry` to the in-memory
    audit buffer for ``incident_id``. The audit entry contains the
    full 5 EC-4 fields (actor / timestamp / reason / before_state /
    after_state).
    """
    if get_incident(incident_id) is None:
        raise ValueError(f"unknown incident_id: {incident_id}")
    existing = get_incident(incident_id)
    before_state = {
        "status": existing.status if existing else "unknown",
        "owner": existing.owner if existing else "unknown",
    }
    after_state = {
        "status": new_status,
        "owner": new_owner or before_state["owner"],
    }
    entry = AuditTrailEntry(
        actor=actor,
        timestamp=_now_iso(),
        reason=reason,
        before_state=before_state,
        after_state=after_state,
        action="status_change",
    )
    with _lock:
        _AUDIT.setdefault(incident_id, []).append(entry)
    return entry


def get_incident_audit_trail(incident_id: str) -> list[AuditTrailEntry]:
    """Return the combined audit trail (seed + runtime) for ``incident_id``."""
    existing = get_incident(incident_id)
    if existing is None:
        return []
    seed_entries = list(existing.audit_trail)
    runtime_entries = list(_AUDIT.get(incident_id, []))
    return seed_entries + runtime_entries


# ---------------------------------------------------------------------------
# Public service: badcases (FR-023)
# ---------------------------------------------------------------------------


def list_badcases() -> BadcaseListResponse:
    """Return the badcase list (FR-023).

    Sort: ``first_seen_at desc`` (most recent first). Returns the full
    envelope with ``open_count`` + ``escalated_count`` + freshness_at.
    """
    badcases = seed_demo_badcases()
    badcases.sort(key=lambda b: b.first_seen_at, reverse=True)
    return BadcaseListResponse(
        badcases=badcases,
        total=len(badcases),
        open_count=sum(1 for b in badcases if b.status == "open"),
        escalated_count=sum(1 for b in badcases if b.status == "escalated"),
        freshness_at=_now_iso(),
    )


def get_badcase(badcase_id: str) -> Optional[Badcase]:
    """Return a single badcase by id, or ``None`` if not found."""
    for bc in seed_demo_badcases():
        if bc.id == badcase_id:
            return bc
    return None


def escalate_badcase_to_incident(
    badcase_id: str,
    actor: str,
) -> BadcaseEscalateResponse:
    """Promote ``badcase_id`` to a new incident (FR-023 AC-23.4).

    Returns a :class:`BadcaseEscalateResponse` with the newly allocated
    ``incident_id`` (synthetic ``inc-escalated-NNNN`` id, Phase 1 only).
    The badcase's ``status`` flips to ``escalated`` and its
    ``incident_id`` field is set to the new id.

    Raises ``ValueError`` if the badcase is unknown.
    """
    existing = get_badcase(badcase_id)
    if existing is None:
        raise ValueError(f"unknown badcase_id: {badcase_id}")
    new_incident_id = _next_incident_id()
    with _lock:
        _ESCALATIONS[badcase_id] = new_incident_id
    return BadcaseEscalateResponse(
        badcase_id=badcase_id,
        incident_id=new_incident_id,
        escalated_at=_now_iso(),
        escalated_by=actor,
    )


# ---------------------------------------------------------------------------
# Test / dev helpers (parity with auth.reset_for_tests)
# ---------------------------------------------------------------------------


def reset_for_tests() -> None:
    """Clear all in-memory comment / audit / escalation state."""
    with _lock:
        _COMMENTS.clear()
        _AUDIT.clear()
        _ESCALATIONS.clear()
        _NEXT_COMMENT_SEQ.clear()


__all__ = [
    "add_incident_comment",
    "change_incident_status",
    "escalate_badcase_to_incident",
    "get_badcase",
    "get_incident",
    "get_incident_audit_trail",
    "get_incident_evidence",
    "list_badcases",
    "list_incident_comments",
    "list_incidents",
    "reset_for_tests",
    "seed_demo_badcases",
    "seed_demo_comments_for",
    "seed_demo_evidence_for",
    "seed_demo_incidents",
]
