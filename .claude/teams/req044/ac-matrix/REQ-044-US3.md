---
req_id: REQ-044-US3
status: locked
locked_at: 2026-07-04
locked_by: dev-implement
negotiation_rounds: 0
---

# Acceptance Matrix for REQ-044-US3 — AI Operations Workspace (FR-016~FR-020)

## SC Gaps

- 无。spec.md US3 (line 165-194) + SC-006/009 已声明 6 类视图(1 success / 1 failed / 1 high-cost / 1 version / 1 eval / 1 badcase),12 Edge Cases 涵盖 FR-016~FR-020 全场景。
- 唯一缺口:spec US3 line 191-193 说 "cost increases while quality does not improve → flag the tradeoff and links to the relevant model, prompt, feature area, and affected cohort",已锁 AC-19.1/19.2/19.3。
- FR-017 维度 (feature_area / model / prompt/rubric/version / release / environment / cohort) 中 "environment" 与 REQ-033 已 ship 的 DashboardFilter.environment 字段对齐 (pm_dashboard/schemas.py)。

## AC 矩阵

| AC-ID | 描述 | 验证方式 (命令/测试名/可观测指标) | 来源 (spec) |
|-------|------|-----------------------------------|-------------|
| AC-16.1 | workspace 顶部 4 KPI tiles (total_volume / success_rate / p95_latency / total_cost) | `cd backend && uv run pytest tests/contract/test_044_ai_operations.py::test_kpis_have_four_tiles -v` | FR-016 |
| AC-16.2 | AI task volume by feature_area (resume_optimize / mock_interview / error_coach / resume_render) bar chart | `cd backend && uv run pytest tests/contract/test_044_ai_operations.py::test_volume_by_feature_has_four_areas -v` | FR-016 |
| AC-16.3 | failure categories 饼图 (timeout / token_limit / parse_error / eval_failed / api_5xx) | `cd backend && uv run pytest tests/contract/test_044_ai_operations.py::test_failure_categories_has_five_classes -v` | FR-016 |
| AC-16.4 | latency bands p50/p95/p99 line chart (per feature_area) | `cd backend && uv run pytest tests/contract/test_044_ai_operations.py::test_latency_bands_has_p50_p95_p99 -v` | FR-016 |
| AC-16.5 | token usage stacked bar (input vs output) per feature_area | `cd backend && uv run pytest tests/contract/test_044_ai_operations.py::test_token_usage_has_input_vs_output -v` | FR-016 |
| AC-16.6 | estimated cost summary card (total + per feature_area breakdown) | `cd backend && uv run pytest tests/contract/test_044_ai_operations.py::test_cost_summary_has_total_and_breakdown -v` | FR-016 |
| AC-17.1 | version selector dropdown (combobox) 4 维度: prompt_fingerprint / rubric_version / model / app_version | `cd backend && uv run pytest tests/contract/test_044_ai_operations.py::test_version_selector_has_four_dimensions -v` | FR-017 |
| AC-17.2 | feature_area multi-select (4 areas: resume_optimize / mock_interview / error_coach / resume_render) | `cd backend && uv run pytest tests/contract/test_044_ai_operations.py::test_feature_area_selector_has_four_areas -v` | FR-017 |
| AC-17.3 | cohort selector (复用 US2 CohortPicker) | `grep -c "cohort-picker\|CohortPicker" src/admin/pages/AIOperations.tsx` 期望 ≥ 1 | FR-017 |
| AC-17.4 | 切换 version 时所有图表 refresh + 显示 "Comparing X vs Y" 标签 | `grep -c "Comparing\|comparing\|version" src/admin/pages/AIOperations.tsx` 期望 ≥ 2 | FR-017 |
| AC-17.5 | comparison baseline label 在每个图表面板顶部 | `grep -c "comparison\|baseline\|Compared" src/admin/components/ai-operations/*.tsx` 期望 ≥ 3 (每个面板) | FR-017 |
| AC-18.1 | 后端 `GET /api/v1/admin-console/ai-operations/quality-issues` 返回 AI quality issue list,每条 link: eval_verdict + badcase_id + affected_feature_area + affected_journey_step + owner + status + recommended_action | `cd backend && uv run pytest tests/contract/test_044_ai_operations.py::test_quality_issues_have_eight_link_fields -v` | FR-018 |
| AC-18.2 | 前端 quality issue drawer 显示全部 8 link 字段 | `cd backend && uv run pytest tests/contract/test_044_ai_operations.py::test_quality_issues_eight_field_names_in_schema -v` | FR-018 |
| AC-18.3 | drawer "View badcase" 按钮跳转 badcase 详情 (US4 链接占位) | `grep -c "View badcase\|view-badcase\|badcase-detail" src/admin/components/ai-operations/QualityIssueDrawer.tsx` 期望 ≥ 1 | FR-018 |
| AC-19.1 | 后端计算 cost_per_quality_delta;若 quality_delta < 0 → flag "Cost up, quality down" | `cd backend && uv run pytest tests/contract/test_044_ai_operations.py::test_cost_quality_flag_when_quality_down -v` | FR-019 |
| AC-19.2 | workspace 顶部 alert banner "Cost up X%, quality down Y%" 红色 + linked model + prompt + feature_area + cohort | `cd backend && uv run pytest tests/contract/test_044_ai_operations.py::test_cost_quality_flag_has_severity_and_linked -v` | FR-019 |
| AC-19.3 | alert click → 跳转 quality issue drawer | `grep -c "cost-quality-alert\|onClick\|openQualityIssue" src/admin/components/ai-operations/CostQualityAlert.tsx` 期望 ≥ 1 | FR-019 |
| AC-20.1 | workspace Eval/Badcase summary card: total eval runs + pass rate + open badcases count | `cd backend && uv run pytest tests/contract/test_044_ai_operations.py::test_eval_badcase_summary_has_required_fields -v` | FR-020 |
| AC-20.2 | "Recent Badcases" 列表显示 5 条最新 badcases (id + feature_area + eval_verdict + status) | `cd backend && uv run pytest tests/contract/test_044_ai_operations.py::test_recent_badcases_list_has_five_entries -v` | FR-020 |
| AC-20.3 | "View in Logs" 按钮点击跳到 logs-and-traces workspace (US5 占位路由) | `grep -c "View in Logs\|view-in-logs\|/admin-console/logs-and-traces" src/admin/components/ai-operations/EvalBadcaseSummary.tsx` 期望 ≥ 1 | FR-020 |
| SC-6.1 | Playwright: workspace 显示 6 类视图 (success/failed/high-cost/version/eval/badcase) 各 ≥ 1 case | `cd tests/e2e && npx playwright test 044-ai-operations.spec.ts --reporter=line` 期望 ≥ 1 spec | SC-006 |
| EC-1 | 零 AI task 数据 → 显式 "0 AI tasks" 不被静默通过 + freshness_at = "unknown" | `cd backend && uv run pytest tests/contract/test_044_ai_operations.py::test_zero_ai_tasks_surfaces_explicit_zero -v` | Edge Cases line 317 |
| EC-2 | version 数据缺失 (旧 record 无 prompt_fingerprint) → 显示 "version unknown" 不静默归 baseline | `cd backend && uv run pytest tests/contract/test_044_ai_operations.py::test_version_unknown_handled -v` | Edge Cases line 322 |
| EC-3 | 成本估算因 token 价格表陈旧 → flag "cost estimate outdated, last reconciled <date>" | `cd backend && uv run pytest tests/contract/test_044_ai_operations.py::test_cost_outdated_flag_when_token_table_stale -v` | Edge Cases line 318 |

## 起草说明（写给 tester）

### 设计意图

- US3 范围 = FR-016~FR-020 + SC-006/009,纯 workspace 内 PM 监控 AI 质量/成本/版本。
- 后端模块路径:`backend/app/modules/admin_console/ai_operations/` (独立子目录,沿 US1 decision_signals + US2 product_analytics 模式)。
- 数据源 = `seed_demo_*` 静态 seed (AI tasks + eval runs + badcases + cost/quality 标志),严格沿 US1/US2 pattern。**禁止** silent empty fallback — 零任务时返回 valid_zero + freshness_at = "unknown" (FR-028 + Edge Case line 322)。
- 真实 metric 计算 = `[CROSS-TEAM-DEBT]` Phase 2 batch 3:US3 仅交付 workspace surface + 类型契约 + seed 数据,真实 AI task aggregation / eval / badcase linkage 接 pm_dashboard 6 panels + REQ-026 eval + REQ-033 badcases 表。
- 复用 baseline (heavy reuse,不动):
  - `backend/app/modules/pm_dashboard/api.py:435` — 已 ship `/metrics/ai-operations` + `/metrics/version-experiment` endpoints (US3 不重新实现这些,只复用作为 data 通道)
  - `backend/app/modules/pm_dashboard/service.py:487` — `get_ai_operations` + `get_version_experiment` 计算函数
  - `backend/app/modules/telemetry_contracts/metrics.py` — MetricDefinition (含 dimensions)
  - `backend/app/modules/telemetry_contracts/costs.py` — `estimate_cost` (US3 cost summary 复用)
  - `backend/app/modules/admin_console/decision_signals/` — US1 seed pattern (FR-008)
  - `backend/app/modules/admin_console/product_analytics/` — US2 seed pattern + service/api shape
  - `backend/app/modules/badcases/` — REQ-026 agent 评测层 badcases 表 (READ ONLY,在 service 中遍历数据但不修改 schema)
  - `backend/app/eval/` — REQ-026 eval 结果 (READ ONLY)
  - `src/admin/pages/AIOperations.tsx` — 当前 placeholder,US3 全量升级
  - `src/types/admin-console.ts:17` — WorkspaceId `'ai-operations'` 已声明
- 9 个独立 endpoint (kpis / volume-by-feature / failure-categories / latency-bands / token-usage / cost-summary / quality-issues / cost-quality-flag / eval-badcase-summary),每个 endpoint 独立 service 函数 + 独立 seed 函数。

### 已覆盖的边界

- EC-1 零 AI task data → 返回 `call_count=0` + `freshness_at="unknown"` + UI 显示 "0 AI tasks" 横幅 (FR-028 valid_zero)
- EC-2 version 数据缺失 → `prompt_fingerprint="version unknown"` 不静默归为 baseline,显示 explicit sentinel
- EC-3 成本估算陈旧 → `CostQualityFlag.last_reconciled_at` 字段 + UI alert "cost estimate outdated" (硬编码 14d reconciliation cycle)
- FR-019 成本增加但质量下降 → `severity=critical` 红色 banner + linked model/prompt/feature_area/cohort 4 维
- FR-018 quality issue link 8 字段全显:eval_verdict + badcase_id + affected_feature_area + affected_journey_step + owner + status + recommended_action + feature_area_dimension

### 未覆盖的边界（已知风险 / [CROSS-TEAM-DEBT]）

- 真实 AI task aggregation pipeline → seed 静态 call_count/success_count/cost 等值,Phase 2 batch 3 接 pm_dashboard `ai-operations` panel
- 真实 cost_quality_delta 计算 → seed 静态 deltaPct,Phase 2 batch 3 用 telemetry_contracts/costs.py 的 estimate_cost 跑回归
- 真实 eval run / badcase 查询 → seed 静态 5 条 recent badcases,Phase 2 batch 3 接 backend/app/eval/ + badcases 表 join
- 真实 PM 视角"成本-质量脱钩"thresholds → seed 静态 +10%/-5%,Phase 2 batch 3 接 telemetry_contracts/metrics.py 的 QualityFlags
- AI quality issue drawer 的 "View badcase" 按钮目标路由为占位,US4 实现真实 badcase 详情页

### 铁律复审

- 铁律 A: seed_demo_ai_tasks / seed_demo_eval_runs / seed_demo_badcases 模式严格沿 US1/US2;无 silent empty fallback
- 铁律 C: 不动 src/admin/components/log/ 7 文件 + 不动 src/admin/components/product-analytics/ 11 文件 + 不动 src/admin/components/decision-signals/ 5 文件 + 不动 src/admin/components/users/ 1 文件
- 铁律 D: 前端 AIQualityIssue / VersionComparison / CostQualityFlag / EvalBadcaseSummary 字段 = 后端 Pydantic 字段;加 [CROSS-TEAM-DEBT] tag 标注"真实 AI task aggregation 在 Phase 2 batch 3 接 pm_dashboard"
- 铁律 E: grep 字面精确 (AC-17.3/17.4/17.5/18.3/19.3/20.3)
- 跨团队: 仅新建 backend/app/modules/admin_console/ai_operations/ 子目录;只读 + 复用 (不修改) agents/errors/interviews/resumes/jobs/ability/ability_profile/ability_diagnose/auth/sessions/eval/badcases/telemetry_contracts/pm_dashboard 内部实现
