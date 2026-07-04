"""REQ-044 US2 — Product Analytics service layer (FR-011~FR-015).

Pure orchestration: returns question templates, funnel rows, cohort
list, feature adoption rows, and privacy-safe user lookup.

Phase-1 seed strategy (mirrors ``admin_console.decision_signals.service``):

- :func:`seed_demo_question_templates` returns ≥3 templates per tab
  across all 7 FR-011 tabs (≥21 total). Each template declares
  ``metric_id`` + ``owner`` + ``freshness_at`` so SC-004 7-field
  tooltip can be wired without backend changes.
- :func:`seed_demo_cohorts` returns 4 cohort definitions spanning
  registered / active / power / new cohorts.
- :func:`seed_demo_users` returns 3 privacy-safe user profiles with
  varied visibility levels (full / masked / hidden).
- :func:`get_funnel` returns a 5-step funnel with entry_conversion +
  comparison_delta + time_to_convert P50/CI band.
- :func:`get_feature_adoption` returns 3 features × 5 metrics grid.

[CROSS-TEAM-DEBT] Phase 2 batch 2 will replace these seed helpers with
a real aggregator that walks the pm_dashboard 6 panels + cohort
snapshots. Until then the seed is the verifiable surface — tests
must NOT mock the service; they must hit the service directly.

Sort key: cohorts sorted by ``name`` asc; funnel steps preserve
declared order; feature adoption sorted by ``feature_id`` asc.
"""
from __future__ import annotations

from datetime import UTC, datetime

from app.modules.admin_console.product_analytics.schemas import (
    CohortListResponse,
    CohortSegment,
    FeatureAdoptionMetric,
    FeatureAdoptionResponse,
    FeatureAdoptionRow,
    FunnelComparisonDelta,
    FunnelResponse,
    FunnelStep,
    QuestionTemplate,
    QuestionTemplateListResponse,
    TimeToConvertBand,
    UserPrivacySafe,
    UserPrivacySafeField,
)

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    """Return current UTC timestamp as ISO 8601 string (no microseconds)."""
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _earlier_iso(days: int) -> str:
    """Return an ISO 8601 timestamp N days before now."""
    from datetime import timedelta

    return (datetime.now(UTC) - timedelta(days=days)).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


# ---------------------------------------------------------------------------
# Seed: question templates (FR-011 + AC-11.2 = ≥3 per tab × 7 tabs)
# ---------------------------------------------------------------------------


def seed_demo_question_templates() -> list[QuestionTemplate]:
    """Return ≥21 curated question templates (3 per tab × 7 tabs)."""
    now = _now_iso()

    def _t(
        tid: str,
        tab: str,
        title: str,
        desc: str,
        metric: str,
        cohort: str | None = None,
        days: int = 7,
        freshness: str | None = None,
    ) -> QuestionTemplate:
        return QuestionTemplate(
            template_id=tid,
            tab=tab,
            title=title,
            description=desc,
            required_cohort_id=cohort,
            required_period_days=days,
            metric_id=metric,
            owner="@pm-oncall",
            freshness_at=freshness or now,
        )

    return [
        # activation tab (3)
        _t(
            "q-act-1",
            "activation",
            "近 7 天新用户激活率",
            "新注册用户在 7 天内完成首次模拟面试 / 简历创建的占比",
            "funnel.registered_to_first_interview",
            cohort="cohort-registered",
        ),
        _t(
            "q-act-2",
            "activation",
            "注册 → 首次简历创建转化",
            "新用户从注册到首次简历创建的时间分布与转化率",
            "funnel.registered_to_first_resume",
            cohort="cohort-registered",
            days=3,
        ),
        _t(
            "q-act-3",
            "activation",
            "激活路径漏斗 (注册 → 登录 → 创建 → 首次面试)",
            "5 步激活漏斗，定位最大 drop-off 步骤",
            "funnel.activation_5step",
            cohort="cohort-registered",
            days=7,
        ),
        # funnel tab (3)
        _t(
            "q-fun-1",
            "funnel",
            "注册 → 首次模拟面试 → 完成 (5 步)",
            "5 步漏斗：注册 → 登录 → 创建简历 → 预约面试 → 完成面试",
            "funnel.registered_to_completed",
            cohort="cohort-registered",
            days=14,
        ),
        _t(
            "q-fun-2",
            "funnel",
            "面试反馈闭环漏斗",
            "面试完成 → 收到反馈 → 查看反馈 → 应用反馈",
            "funnel.feedback_loop",
            cohort="cohort-active",
            days=14,
        ),
        _t(
            "q-fun-3",
            "funnel",
            "订阅漏斗",
            "免费用户 → 浏览付费功能 → 触发升级提示 → 完成订阅",
            "funnel.subscription",
            cohort="cohort-power",
            days=30,
        ),
        # retention tab (3)
        _t(
            "q-ret-1",
            "retention",
            "7 日 cohort 留存 (T+1 / T+7 / T+14)",
            "近 7 天新用户分别在 1 / 7 / 14 天后的回访率",
            "retention.d7_cohort",
            cohort="cohort-new",
            days=7,
        ),
        _t(
            "q-ret-2",
            "retention",
            "面试完成用户 30 日留存",
            "完成首次面试用户在 30 天内回到产品继续使用",
            "retention.interview_completed_30d",
            cohort="cohort-active",
            days=30,
        ),
        _t(
            "q-ret-3",
            "retention",
            "错误本 repeat-use 留存",
            "使用错误本功能的用户在 N 天内 repeat-use 占比",
            "retention.error_book_repeat",
            cohort="cohort-active",
            days=14,
        ),
        # adoption tab (3)
        _t(
            "q-adp-1",
            "adoption",
            "新功能 discovery / first use / repeat 三阶段分布",
            "近 14 天新功能 5 维度采用：发现 / 首次 / 重复 / 频次 / 下游结果",
            "adoption.feature_5metric",
            cohort="cohort-active",
            days=14,
        ),
        _t(
            "q-adp-2",
            "adoption",
            "AI 评分功能 adoption 趋势",
            "AI 评分功能在 30 天窗口的 5 维度变化",
            "adoption.ai_scoring",
            cohort="cohort-power",
            days=30,
        ),
        _t(
            "q-adp-3",
            "adoption",
            "错误本功能 discovery vs repeat 失衡分析",
            "discovery 高但 repeat 低，定位 UX 摩擦点",
            "adoption.error_book_imbalance",
            cohort="cohort-active",
            days=14,
        ),
        # journey tab (3)
        _t(
            "q-jou-1",
            "journey",
            "典型成功用户路径 (注册 → 面试 → 反馈 → 二次面试)",
            "成功用户在 30 天内的关键节点序列",
            "journey.success_path",
            cohort="cohort-power",
            days=30,
        ),
        _t(
            "q-jou-2",
            "journey",
            "流失用户路径 (注册 → 单次面试 → 30 日不回访)",
            "流失用户在 30 天内的最后 1-2 个动作",
            "journey.churn_path",
            cohort="cohort-new",
            days=30,
        ),
        _t(
            "q-jou-3",
            "journey",
            "错误本用户 journey",
            "从错误本触发到查看反馈的典型路径",
            "journey.error_book_path",
            cohort="cohort-active",
            days=14,
        ),
        # release tab (3)
        _t(
            "q-rel-1",
            "release",
            "v3.1 vs v3.0 关键指标对比",
            "近 14 天 v3.1 vs v3.0 在激活 / 漏斗 / 留存上的 delta",
            "release.v3_1_vs_v3_0",
            cohort="cohort-active",
            days=14,
        ),
        _t(
            "q-rel-2",
            "release",
            "prompt v3.2 上线后 AI 成功率变化",
            "prompt v3.2 发布前后 ai_success_rate 的 7 日均值",
            "release.prompt_v3_2",
            cohort="cohort-active",
            days=7,
        ),
        _t(
            "q-rel-3",
            "release",
            "rubric v4 切换后的评分稳定性",
            "rubric v4 上线前后评分方差变化",
            "release.rubric_v4",
            cohort="cohort-power",
            days=14,
        ),
        # experiment tab (3)
        _t(
            "q-exp-1",
            "experiment",
            "实验 EXP-2026-07 (新激活引导)",
            "新激活引导 A/B 测试的 conversion / retention delta",
            "experiment.exp_2026_07",
            cohort="cohort-registered",
            days=14,
        ),
        _t(
            "q-exp-2",
            "experiment",
            "实验 EXP-2026-08 (错误本卡片样式)",
            "错误本卡片样式 A/B 测试的 5 维度 adoption delta",
            "experiment.exp_2026_08",
            cohort="cohort-active",
            days=14,
        ),
        _t(
            "q-exp-3",
            "experiment",
            "实验 EXP-2026-09 (订阅页文案)",
            "订阅页文案 A/B 测试的 漏斗 + revenue delta",
            "experiment.exp_2026_09",
            cohort="cohort-power",
            days=30,
        ),
    ]


def list_question_templates() -> QuestionTemplateListResponse:
    """Return the curated question template list (FR-011)."""
    templates = seed_demo_question_templates()
    return QuestionTemplateListResponse(
        templates=templates,
        total=len(templates),
        freshness_at=_now_iso(),
    )


# ---------------------------------------------------------------------------
# Seed: cohorts (FR-013 + AC-13.1)
# ---------------------------------------------------------------------------


def seed_demo_cohorts() -> list[CohortSegment]:
    """Return the curated cohort list (4 cohorts)."""
    now = _now_iso()

    return [
        CohortSegment(
            id="cohort-registered",
            name="近 7 天注册用户",
            definition="created_at >= now - 7d 且 email_verified = true",
            population=1842,
            owner="@pm-oncall",
            last_computed_at=now,
            stale=False,
        ),
        CohortSegment(
            id="cohort-active",
            name="近 30 天活跃用户 (DAU)",
            definition="last_active_at >= now - 7d",
            population=5234,
            owner="@pm-oncall",
            last_computed_at=now,
            stale=False,
        ),
        CohortSegment(
            id="cohort-power",
            name="近 30 天 power user (>=10 sessions)",
            definition="session_count_30d >= 10",
            population=618,
            owner="@pm-oncall",
            last_computed_at=now,
            stale=False,
        ),
        CohortSegment(
            id="cohort-new",
            name="近 14 天新用户 (T+0)",
            definition="created_at >= now - 14d",
            population=3621,
            owner="@pm-oncall",
            last_computed_at=_earlier_iso(2),
            stale=True,  # EC-2: stale cohort surfaced
        ),
    ]


def list_cohorts() -> CohortListResponse:
    """Return the curated cohort list (FR-013)."""
    cohorts = seed_demo_cohorts()
    cohorts_sorted = sorted(cohorts, key=lambda c: c.name)
    return CohortListResponse(
        cohorts=cohorts_sorted,
        total=len(cohorts_sorted),
        freshness_at=_now_iso(),
    )


# ---------------------------------------------------------------------------
# Funnel (FR-012 + AC-12.1/12.2/12.3)
# ---------------------------------------------------------------------------


def get_funnel(
    template_id: str = "q-fun-1",
    cohort_id: str | None = None,
    period_start: str | None = None,
    period_end: str | None = None,
) -> FunnelResponse:
    """Return the funnel payload for a given template + cohort.

    [CROSS-TEAM-DEBT] Phase 2 batch 2 will compute real step counts
    from the funnel panel in pm_dashboard. For US2 we ship a static
    5-step funnel with hand-tuned numbers to validate the schema +
    UI surface.
    """
    # Static 5-step funnel for q-fun-1 (registered → completed).
    # Edge Cases EC-1: count=0 surfaces explicitly via step 5 count=0
    # only on the empty-funnel branch (not the default q-fun-1).
    if template_id == "funnel-empty":
        # EC-1 explicit zero funnel
        return FunnelResponse(
            funnel_id="funnel-empty",
            steps=[
                FunnelStep(
                    step_name="registered",
                    count=0,
                    step_conversion=None,
                    drop_off=None,
                ),
                FunnelStep(
                    step_name="login",
                    count=0,
                    step_conversion=0.0,
                    drop_off=0.0,
                ),
                FunnelStep(
                    step_name="create_resume",
                    count=0,
                    step_conversion=0.0,
                    drop_off=0.0,
                ),
                FunnelStep(
                    step_name="book_interview",
                    count=0,
                    step_conversion=0.0,
                    drop_off=0.0,
                ),
                FunnelStep(
                    step_name="complete_interview",
                    count=0,
                    step_conversion=0.0,
                    drop_off=0.0,
                ),
            ],
            entry_conversion=0.0,
            comparison_delta=FunnelComparisonDelta(
                comparison_period_label="前 7 天",
                step_conversion_delta=0.0,
            ),
            time_to_convert=TimeToConvertBand(
                p50_seconds=0.0,
                ci95_lower_seconds=0.0,
                ci95_upper_seconds=0.0,
                sample_size=0,
            ),
            cohort_id=cohort_id,
            cohort_population=0,
            last_computed_at=_now_iso(),
            freshness_at=_now_iso(),
        )

    # Default funnel: 5 steps with realistic numbers.
    return FunnelResponse(
        funnel_id=template_id,
        steps=[
            FunnelStep(
                step_name="registered",
                count=1842,
                step_conversion=None,
                drop_off=None,
            ),
            FunnelStep(
                step_name="login",
                count=1655,
                step_conversion=0.8985,
                drop_off=0.1015,
            ),
            FunnelStep(
                step_name="create_resume",
                count=1283,
                step_conversion=0.7752,
                drop_off=0.1233,
            ),
            FunnelStep(
                step_name="book_interview",
                count=782,
                step_conversion=0.6095,
                drop_off=0.1657,
            ),
            FunnelStep(
                step_name="complete_interview",
                count=528,
                step_conversion=0.6752,
                drop_off=0.3248,
            ),
        ],
        entry_conversion=0.2867,
        comparison_delta=FunnelComparisonDelta(
            comparison_period_label="前 7 天",
            step_conversion_delta=-0.0250,
        ),
        time_to_convert=TimeToConvertBand(
            p50_seconds=86400.0,  # 1 day median
            ci95_lower_seconds=72000.0,  # 20h
            ci95_upper_seconds=108000.0,  # 30h
            sample_size=528,
        ),
        cohort_id=cohort_id or "cohort-registered",
        cohort_population=1842,
        last_computed_at=_now_iso(),
        freshness_at=_now_iso(),
    )


# ---------------------------------------------------------------------------
# Feature adoption (FR-014 + AC-14.1/14.2/14.3)
# ---------------------------------------------------------------------------


def _five_metrics(
    discovery: float,
    first_use: float,
    repeat: float,
    freq: float,
    outcome: float,
    delta: float,
    sample: int,
    insufficient: bool = False,
) -> list[FeatureAdoptionMetric]:
    """Build the canonical 5-metric row (AC-14.1)."""
    return [
        FeatureAdoptionMetric(
            metric_name="discovery_users",
            current_value=discovery,
            unit="count",
            comparison_delta=delta,
            sample_size=sample,
            insufficient_data=insufficient,
        ),
        FeatureAdoptionMetric(
            metric_name="first_use_users",
            current_value=first_use,
            unit="count",
            comparison_delta=delta,
            sample_size=sample,
            insufficient_data=insufficient,
        ),
        FeatureAdoptionMetric(
            metric_name="repeat_users",
            current_value=repeat,
            unit="count",
            comparison_delta=delta,
            sample_size=sample,
            insufficient_data=insufficient,
        ),
        FeatureAdoptionMetric(
            metric_name="frequency_avg",
            current_value=freq,
            unit="per_user_per_week",
            comparison_delta=delta,
            sample_size=sample,
            insufficient_data=insufficient,
        ),
        FeatureAdoptionMetric(
            metric_name="downstream_success_rate",
            current_value=outcome,
            unit="rate",
            comparison_delta=delta,
            sample_size=sample,
            insufficient_data=insufficient,
        ),
    ]


def get_feature_adoption(cohort_id: str | None = None) -> FeatureAdoptionResponse:
    """Return the feature adoption grid (3 features × 5 metrics).

    [CROSS-TEAM-DEBT] Phase 2 batch 2 will compute these from the
    pm_dashboard adoption panel + ProductEvent stream. For US2 we
    ship a static 3-feature grid to validate the 5-metric schema.
    """
    now = _now_iso()
    rows = [
        FeatureAdoptionRow(
            feature_id="feat-ai-scoring",
            feature_name="AI 自动评分",
            metrics=_five_metrics(
                discovery=820.0,
                first_use=614.0,
                repeat=412.0,
                freq=2.3,
                outcome=0.842,
                delta=0.0450,
                sample=412,
            ),
            cohort_id=cohort_id or "cohort-active",
            cohort_population=5234,
            last_computed_at=now,
            freshness_at=now,
        ),
        FeatureAdoptionRow(
            feature_id="feat-error-book",
            feature_name="错误本",
            metrics=_five_metrics(
                discovery=1543.0,
                first_use=1127.0,
                repeat=807.0,
                freq=3.1,
                outcome=0.764,
                delta=0.0120,
                sample=807,
            ),
            cohort_id=cohort_id or "cohort-active",
            cohort_population=5234,
            last_computed_at=now,
            freshness_at=now,
        ),
        FeatureAdoptionRow(
            feature_id="feat-mock-interview-replay",
            feature_name="面试回放",
            metrics=_five_metrics(
                discovery=95.0,
                first_use=42.0,
                repeat=12.0,
                freq=0.6,
                outcome=0.681,
                delta=-0.0230,
                sample=12,
                insufficient=True,  # EC-3
            ),
            cohort_id=cohort_id or "cohort-active",
            cohort_population=5234,
            last_computed_at=now,
            freshness_at=now,
        ),
    ]
    return FeatureAdoptionResponse(
        features=rows,
        total=len(rows),
        freshness_at=now,
    )


# ---------------------------------------------------------------------------
# User privacy-safe lookup (FR-015 + FR-032 + AC-15.1/15.3)
# ---------------------------------------------------------------------------


def seed_demo_users() -> dict[str, UserPrivacySafe]:
    """Return the curated 3 privacy-safe user profiles.

    Each profile exposes ONLY the allow-listed 7 fields (email, role,
    journey_summary, incidents_count, quality_score, created_at,
    last_active_at). Visibility per field varies so the
    FR-031 least-privilege grid is observable.
    """
    now = _now_iso()

    return {
        "019ec1be-0000-7000-8000-000000000001": UserPrivacySafe(
            user_id="019ec1be-0000-7000-8000-000000000001",
            fields=[
                UserPrivacySafeField(
                    name="email",
                    visibility="masked",
                    value="demo***@intercraft.io",
                ),
                UserPrivacySafeField(
                    name="role",
                    visibility="full",
                    value="pm",
                ),
                UserPrivacySafeField(
                    name="journey_summary",
                    visibility="full",
                    value="注册 → 首次模拟面试 → 完成反馈 → 二次面试 (活跃)",
                ),
                UserPrivacySafeField(
                    name="incidents_count",
                    visibility="full",
                    value="2",
                ),
                UserPrivacySafeField(
                    name="quality_score",
                    visibility="full",
                    value="0.871",
                ),
                UserPrivacySafeField(
                    name="created_at",
                    visibility="full",
                    value="2026-05-12T09:21:00Z",
                ),
                UserPrivacySafeField(
                    name="last_active_at",
                    visibility="full",
                    value=now,
                ),
            ],
            cohort_population=5234,
            last_computed_at=now,
            freshness_at=now,
        ),
        "019ec1be-0000-7000-8000-000000000002": UserPrivacySafe(
            user_id="019ec1be-0000-7000-8000-000000000002",
            fields=[
                UserPrivacySafeField(
                    name="email",
                    visibility="masked",
                    value="user***@gmail.com",
                ),
                UserPrivacySafeField(
                    name="role",
                    visibility="full",
                    value="end_user",
                ),
                UserPrivacySafeField(
                    name="journey_summary",
                    visibility="masked",
                    value="注册 → 单次面试 → 30 日未回访 (流失风险)",
                ),
                UserPrivacySafeField(
                    name="incidents_count",
                    visibility="full",
                    value="0",
                ),
                UserPrivacySafeField(
                    name="quality_score",
                    visibility="full",
                    value="0.612",
                ),
                UserPrivacySafeField(
                    name="created_at",
                    visibility="full",
                    value="2026-06-22T14:08:00Z",
                ),
                UserPrivacySafeField(
                    name="last_active_at",
                    visibility="full",
                    value="2026-06-29T03:11:00Z",
                ),
            ],
            cohort_population=3621,
            last_computed_at=now,
            freshness_at=now,
        ),
        "019ec1be-0000-7000-8000-000000000003": UserPrivacySafe(
            user_id="019ec1be-0000-7000-8000-000000000003",
            fields=[
                UserPrivacySafeField(
                    name="email",
                    visibility="hidden",
                    value=None,
                ),
                UserPrivacySafeField(
                    name="role",
                    visibility="full",
                    value="end_user",
                ),
                UserPrivacySafeField(
                    name="journey_summary",
                    visibility="hidden",
                    value=None,
                ),
                UserPrivacySafeField(
                    name="incidents_count",
                    visibility="masked",
                    value="—",
                ),
                UserPrivacySafeField(
                    name="quality_score",
                    visibility="hidden",
                    value=None,
                ),
                UserPrivacySafeField(
                    name="created_at",
                    visibility="full",
                    value="2026-07-01T08:42:00Z",
                ),
                UserPrivacySafeField(
                    name="last_active_at",
                    visibility="full",
                    value="2026-07-03T19:30:00Z",
                ),
            ],
            cohort_population=3621,
            last_computed_at=now,
            freshness_at=now,
        ),
    }


def get_user_safe(user_id: str) -> UserPrivacySafe | None:
    """Return the privacy-safe profile for ``user_id`` or ``None``."""
    return seed_demo_users().get(user_id)


__all__ = [
    "get_feature_adoption",
    "get_funnel",
    "get_user_safe",
    "list_cohorts",
    "list_question_templates",
    "seed_demo_cohorts",
    "seed_demo_question_templates",
    "seed_demo_users",
]