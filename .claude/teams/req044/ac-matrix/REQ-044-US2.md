---
req_id: REQ-044-US2
status: locked
locked_at: 2026-07-04
locked_by: dev-implement
negotiation_rounds: 0
---

# Acceptance Matrix for REQ-044-US2 — Product Analytics Workspace (FR-011~FR-015)

## SC Gaps

- 无。spec.md US2 (line 133-163) + SC-003/004/005 已声明,12 Edge Cases 涵盖 FR-011~FR-015 全场景。
- 唯一缺口：spec 未显式列出 "5 question templates" 的最低数量,但 SC-005 要求 5 种分析视图各 ≥ 1 template → 隐含至少 5 templates per 7 tab = 35 total。本 AC 矩阵锁定"每 tab ≥ 3 templates"以保证 UX 密度。

## AC 矩阵

| AC-ID     | 描述                                                                                              | 验证方式（命令 / 测试名 / 可观测指标）                                                                                                                                                       | 来源 (spec)         |
| --------- | ------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------- |
| AC-11.1   | workspace 顶部 7 question tabs (activation/funnel/retention/adoption/journey/release/exp)         | `grep -c "activation\|funnel\|retention\|adoption\|journey\|release\|experiment" src/admin/components/product-analytics/QuestionTabBar.tsx` 期望 ≥ 7                                          | FR-011              |
| AC-11.2   | 每 tab 渲染 ≥ 3 templates (total ≥ 21 templates in seed)                                          | `cd backend && uv run pytest tests/contract/test_044_product_analytics.py::test_seed_has_min_21_templates -v`                                                                                | FR-011              |
| AC-11.3   | tab 切换不重载 page (in-page state, no full navigation)                                            | `grep -n "useState\|activeTab\|selectedTab" src/admin/pages/ProductAnalytics.tsx` 期望 ≥ 3 (客户端 state 而非 URL routing)                                                                  | FR-011              |
| AC-12.1   | funnel template 渲染 5 步骤 + 每步 count + conversion % + drop-off %                             | `cd backend && uv run pytest tests/contract/test_044_product_analytics.py::test_funnel_has_5_steps_with_all_required_fields -v`                                                              | FR-012              |
| AC-12.2   | entry conversion + comparison_period delta (% vs prev period)                                     | `cd backend && uv run pytest tests/contract/test_044_product_analytics.py::test_funnel_has_entry_conversion_and_comparison_delta -v`                                                       | FR-012              |
| AC-12.3   | time-to-convert 显示中位数 P50 + 95% 置信区间                                                     | `cd backend && uv run pytest tests/contract/test_044_product_analytics.py::test_funnel_has_time_to_convert_p50_with_ci -v`                                                                  | FR-012              |
| AC-13.1   | 后端 `GET /api/v1/admin-console/product-analytics/cohorts` 返回 cohorts (id/name/definition/population/owner/last_computed_at) | `cd backend && uv run pytest tests/contract/test_044_product_analytics.py::test_cohorts_endpoint_returns_required_fields -v`                                                                  | FR-013              |
| AC-13.2   | 前端 CohortPicker 应用 cohort 后所有图表共享同一 segment definition                                | `grep -c "selectedCohortId\|cohort_id\|cohortId" src/admin/pages/ProductAnalytics.tsx` 期望 ≥ 3 (workspace + chart + drawer 共享)                                                            | FR-013              |
| AC-13.3   | 每个图表面板显示 cohort 标签 + population count + last_computed_at timestamp                       | `grep -c "population\|last_computed_at\|lastComputedAt" src/admin/components/product-analytics/FunnelChart.tsx` 期望 ≥ 3                                                                  | FR-013              |
| AC-14.1   | adoption template 显示 5 metric: discovery_users / first_use_users / repeat_users / frequency_avg / downstream_success_rate | `cd backend && uv run pytest tests/contract/test_044_product_analytics.py::test_feature_adoption_has_5_metrics -v`                                                                          | FR-014              |
| AC-14.2   | 每 feature 显示 5 metric 当前值 + comparison_period delta                                          | `cd backend && uv run pytest tests/contract/test_044_product_analytics.py::test_feature_adoption_has_comparison_delta -v`                                                                   | FR-014              |
| AC-14.3   | 5 metric 分离展示 (不合并成单一 adoption score)                                                    | `grep -c "discovery_users\|first_use_users\|repeat_users\|frequency_avg\|downstream_success_rate" src/admin/components/product-analytics/FeatureAdoptionGrid.tsx` 期望 ≥ 5 (5 个独立字段渲染) | FR-014              |
| AC-15.1   | 后端 `GET /api/v1/admin-console/users/{user_id}` 返回 privacy-safe profile (email + role + journey summary + incidents count + quality score),禁止 raw_resume / raw_interview_answer / raw_prompt | `cd backend && uv run pytest tests/contract/test_044_product_analytics.py::test_user_safe_profile_strips_sensitive_fields -v`                                                              | FR-015              |
| AC-15.2   | 前端 UsersAccounts.tsx 含 user search input + user detail drawer                                   | `grep -c "search\|drawer\|Search" src/admin/pages/UsersAccounts.tsx` 期望 ≥ 3                                                                                                              | FR-015              |
| AC-15.3   | user detail drawer 显示 privacy-safe 字段 + 每个字段标"权限级别" (full / masked / hidden)         | `grep -c "visibility\|full\|masked\|hidden" src/admin/components/users/UserDetailDrawer.tsx` 期望 ≥ 4                                                                                       | FR-015              |
| AC-15.4   | `grep -F "raw_resume\|raw_prompt\|raw_model_output" src/admin/pages/UsersAccounts.tsx` 0 命中     | `grep -cF "raw_resume\|raw_prompt\|raw_model_output" src/admin/pages/UsersAccounts.tsx` 期望 == 0                                                                                          | FR-032 + FR-015     |
| AC-SC-3.1 | Playwright: PM 在 Product Analytics workspace 单页完成 activation/retention/adoption/quality 4 问 | `cd tests/e2e && npx playwright test 044-product-analytics.spec.ts --reporter=line` 期望 ≥ 1 spec 通过                                                                                      | SC-003              |
| AC-SC-4.1 | 每个 metric tooltip 含 7 字段 (definition/owner/source/period/freshness/completeness/quality_flag)  | `grep -c "definition\|owner\|source\|freshness\|completeness\|quality_flag\|period" src/admin/components/product-analytics/MetricTooltip.tsx` 期望 ≥ 7                                         | SC-004              |
| AC-SC-5.1 | workspace 内 5 种分析视图 (funnel/cohort/retention/adoption/release-compare) 各 ≥ 1 template       | `cd backend && uv run pytest tests/contract/test_044_product_analytics.py::test_seed_covers_five_analysis_views -v`                                                                          | SC-005              |
| EC-1      | 零 funnel data → 显式 "0 users entered" 不被静默通过                                              | `grep "0 users entered\|zero funnel\|valid zero" src/admin/components/product-analytics/FunnelChart.tsx` 期望 ≥ 1                                                                          | Edge Cases line 317 |
| EC-2      | cohort definition 改变 → 图表显示 "stale cohort" 警告                                              | `grep "stale cohort\|staleCohort\|stale" src/admin/components/product-analytics/CohortPicker.tsx` 期望 ≥ 1                                                                                  | Edge Cases line 321 |
| EC-3      | feature adoption 计算时段不足 → "Insufficient data" badge                                          | `grep "Insufficient data\|insufficient\|insufficientData" src/admin/components/product-analytics/FeatureAdoptionGrid.tsx` 期望 ≥ 1                                                          | Edge Cases line 322 |

## 起草说明（写给 tester）

### 设计意图

- US2 范围 = FR-011~FR-015 + SC-003/004/005,纯 workspace 内 PM 自助分析。
- 后端模块路径：`backend/app/modules/admin_console/product_analytics/` (独立子目录,沿 US1 decision_signals 模式)。
- 数据源 = `seed_demo_*` 静态 seed,严格沿 US1 pattern (decision_signals/service.py:101 seed_demo_signals)。**禁止** silent empty fallback — 零数据时返回 valid_zero 标记 (FR-028 + Edge Cases)。
- 真实 metric 计算 = `[CROSS-TEAM-DEBT]` Phase 2 batch 2:US2 仅交付 workspace surface + privacy-safe 类型契约 + seed 数据,真实 funnel/cohort 聚合逻辑后续 batch 接 pm_dashboard 6 panels。
- privacy-safe 强制:UserPrivacySafe schema **明确 exclude** `raw_resume` / `raw_interview_answer` / `raw_prompt` / `raw_model_output`,前端 UsersAccounts 不得引用这些字段名 (AC-15.4 grep 字面精确)。
- 5 种分析视图模板:funnel (3 templates) / cohort (3 templates) / retention (3 templates) / adoption (3 templates) / journey (3 templates) / release (3 templates) / experiment (3 templates) = 21 total。每 tab ≥ 3 满足 AC-11.2。
- FR-032 隐私守卫:UserPrivacySafe 必须 exclude `resume_content` / `interview_answers` / `prompts` / `model_outputs` / `secrets` / `tokens` / `passwords` / `credentials`,只保留 email/role/journey_summary/incidents_count/quality_score + visibility_label per field (full/masked/hidden)。

### 已覆盖的边界

- EC-1 零 funnel data → schema `count == 0` + UI 文案 "0 users entered" 显式 (FR-028 valid_zero)
- EC-2 cohort definition 改变 → CohortPicker 显示 stale 警告 (definition_hash mismatch)
- EC-3 feature adoption 时段不足 → "Insufficient data" badge (sample_size < threshold)
- 字段权限分级 → 每字段标 full/masked/hidden 3 档 (FR-031 least-privilege)

### 未覆盖的边界（已知风险 / [CROSS-TEAM-DEBT]）

- 真实 funnel step conversion 计算 → seed 静态值,Phase 2 batch 2 接 pm_dashboard funnel panel
- cohort definition 的 SQL 生成 → seed 静态 definition_hash,Phase 2 batch 2 接 telemetry_contracts cohort table
- 用户 incident count / quality score 实时查询 → seed 静态值,Phase 2 batch 2 接 incidents 模块
- 7 question tabs 中 release / experiment 比较视图的 version 维度 → seed 静态 prompt_fingerprint/rubric_version,Phase 2 batch 2 接 AI Operations workspace

### 铁律复审

- 铁律 A: seed_demo_* 模式严格沿 US1;无 silent empty fallback
- 铁律 C: 不动 src/admin/components/log/ 7 文件
- 铁律 D: 前端类型字段 = 后端 Pydantic 字段;加 [CROSS-TEAM-DEBT] tag
- 铁律 E: grep 字面精确 (AC-15.4)
- 跨团队: 仅新建 backend/app/modules/admin_console/product_analytics/ 子目录;不动 agents/errors/interviews/resumes/jobs/ability/ability_profile/ability_diagnose/auth/sessions/eval/badcases/telemetry_contracts