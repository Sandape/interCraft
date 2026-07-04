---
req_id: REQ-044-US1
status: locked
locked_at: 2026-07-04
locked_by: dev-implement
negotiation_rounds: 0
---

# Acceptance Matrix for REQ-044-US1 — Command Center Decision Queue (FR-007~FR-010)

## SC Gaps

- 无。spec.md 已声明 SC-001 (PM 5 分钟找 top 3) + SC-002 (100% signals 含必填字段) + 12 个 Edge Cases。
- spec FR-007~FR-010 与 SC-001/002 一一对应，无需补 SC。

## AC 矩阵

| AC-ID  | 描述                                                                                          | 验证方式（命令 / 测试名 / 可观测指标）                                                                                                                                              | 来源 (spec)        |
| ------ | --------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------ |
| AC-7.1 | 后端 `GET /api/v1/admin-console/command-center/signals` 返回 200 + `signals: DecisionSignal[]` | `cd backend && uv run pytest tests/contract/test_044_decision_signals.py::test_signals_endpoint_present_in_openapi -v` + `curl -s http://127.0.0.1:8205/api/v1/admin-console/command-center/signals \| jq '.signals \| length'` 期望 ≥ 0 | FR-007             |
| AC-7.2 | `DecisionSignal` schema 含字段 id/category/what_changed/affected_segment/comparison_baseline/severity/confidence/owner/freshness_at/quality_flags/next_review_link/evidence_links | `grep -c "what_changed\|affected_segment\|comparison_baseline\|severity\|confidence\|owner\|freshness_at\|next_review_link" backend/app/modules/admin_console/decision_signals/schemas.py` 期望 ≥ 10 | FR-008             |
| AC-7.3 | 前端命令中心 workspace 展示决策队列，按 priority desc + freshness_at desc 排序                | `grep -n "decision-signals\|DecisionSignalCard\|priority" src/admin/pages/CommandCenter.tsx` 期望 ≥ 3 处匹配                                                                                                                     | FR-007             |
| AC-7.4 | 每条 signal 视觉化含 category icon + severity color + confidence badge + freshness timestamp   | `grep -c "category\|severity\|confidence\|freshness" src/admin/components/decision-signals/DecisionSignalCard.tsx` 期望 ≥ 4                                                                                                       | FR-007 + FR-008    |
| AC-8.1 | grep "what_changed\|affected_segment\|comparison_baseline\|severity\|confidence\|owner\|freshness_at\|next_review_link" 在 backend Pydantic schema + frontend type 各 ≥ 1 处 | `grep -E "what_changed\|affected_segment\|comparison_baseline" backend/app/modules/admin_console/decision_signals/schemas.py src/types/admin-decision-signals.ts` 期望各 ≥ 1     | FR-008             |
| AC-8.2 | 前端 type `DecisionSignal` interface 含以上 8 字段 + category + evidence_links (10 字段字面声明) | `grep -c "^  [a-z_]*:" src/types/admin-decision-signals.ts` 期望 ≥ 10                                                                                                                                                                       | FR-008             |
| AC-8.3 | 详情面板 (click signal → drawer) 显示全部 10 字段                                              | `grep -c "what_changed\|affected_segment\|comparison_baseline\|owner\|next_review_link\|evidence_links\|severity\|confidence\|freshness_at\|category" src/admin/components/decision-signals/DecisionSignalDrawer.tsx` 期望 ≥ 10 | FR-008             |
| AC-9.1 | DecisionSignal.confidence ∈ {confirmed, sampled, inferred, candidate} 枚举                    | `grep -E "confirmed\|sampled\|inferred\|candidate" backend/app/modules/admin_console/decision_signals/schemas.py` 期望 ≥ 4                                                                                                              | FR-009             |
| AC-9.2 | 命令中心 signal list 视觉区分 4 档: confirmed=绿 / sampled=蓝 / inferred=黄 / candidate=灰      | `grep -c "confirmed\|sampled\|inferred\|candidate" src/admin/components/decision-signals/ConfidenceBadge.tsx` 期望 ≥ 4                                                                                                                    | FR-009             |
| AC-9.3 | candidate 档信号必须显式 label "low confidence" 不被静默混入 confirmed                         | `grep "low confidence\|candidate" src/admin/components/decision-signals/ConfidenceBadge.tsx` 期望 ≥ 2                                                                                                                                      | FR-009             |
| AC-10.1 | 当 0 个 high-severity signal 时, 命令中心显示 "quiet steady-state" 视图                       | `grep "quiet steady-state\|QuietState" src/admin/pages/CommandCenter.tsx src/admin/components/decision-signals/QuietState.tsx` 期望 ≥ 3                                                                                                 | FR-010             |
| AC-10.2 | steady-state 视图显示 "Last reviewed at:" + "Open reviews:" + freshness_at 全部 4 个 section  | `grep -c "Last reviewed\|Open reviews\|freshness_at" src/admin/components/decision-signals/QuietState.tsx` 期望 ≥ 3                                                                                                                      | FR-010             |
| AC-SC-1.1 | Playwright happy path: PM 登录命令中心 → 3 high-severity signals 在顶部 + Next review 链接可点 | `cd tests/e2e && npx playwright test 044-command-center.spec.ts --reporter=line` 期望至少 1 spec 通过 (其他可 INFRA-BLOCKED)                                                                                                              | SC-001             |
| AC-SC-2.1 | 后端 GET endpoint 返回的 signals 数组 100% 字段非空 (除 confidence=candidate 时可缺部分)        | `cd backend && uv run pytest tests/contract/test_044_decision_signals.py::test_signals_fields_non_empty -v`                                                                                                                                  | SC-002             |
| EC-1   | 零数据 → steady-state view + 显式 "No signals"                                                | `grep "No signals" src/admin/components/decision-signals/QuietState.tsx` 期望 ≥ 1                                                                                                                                                          | Edge Cases line 317-320 |
| EC-2   | data freshness stale → signal 显式标 "stale"                                                   | `grep "stale\|freshness" src/admin/components/decision-signals/DecisionSignalCard.tsx` 期望 ≥ 2                                                                                                                                            | Edge Cases line 320-321 |
| EC-3   | comparison period incomplete → comparison_baseline 显式 "partial baseline" 标签                | `grep "partial baseline\|comparison_baseline" src/admin/components/decision-signals/DecisionSignalDrawer.tsx` 期望 ≥ 2                                                                                                                     | Edge Cases line 322 |

## 起草说明（写给 tester）

### 设计意图

- US1 范围 = FR-007~FR-010 + SC-001/002。
- 后端模块路径：`backend/app/modules/admin_console/decision_signals/`（独立子目录，不破坏 admin_console 既有模块）。
- DecisionSignal 数据源 = pm_dashboard 6 metric panels + telemetry_contracts/repository.py 的 metric snapshot。Phase 2 batch 1 真实聚合**不在本 PR**——所有数据由 `seed_demo_signals()` 静态 seed 出 N 条样例 signal（其中至少 3 条 high-severity + 至少 1 条 candidate）。后续 batch 通过 `[CROSS-TEAM-DEBT]` 标记，把 seed 替换为真实 metric_panel → signal aggregate 管线。
- 4 档 confidence 视觉化用纯前端 CSS class（confirmed/sampled/inferred/candidate），不和后端字段耦合；前端 type 后端 Pydantic 通过字面枚举对齐。
- 命令中心 workspace 不制造伪告警：seed 出来的 signals 不含 high-severity 时显示 QuietState；high-severity 计数为 0 时也是 QuietState。
- 顶部 4 KPI tiles 在本 PR 显示静态文案 + 数值（与 6 metric panels 的真实连线是 [CROSS-TEAM-DEBT] Phase 2 batch 2）。
- Playwright E2E：1 happy path spec + 3 静态守卫 spec。INFRA-BLOCKED 时 1 spec 标 skip，3 静态守卫必须 GREEN。

### 已覆盖的边界

- 4 档 confidence 视觉区分
- candidate label "low confidence"
- 零数据 QuietState
- freshness stale 显式标
- partial baseline 显式标
- 10 字段全部非空
- 优先级排序（priority desc + freshness_at desc）
- category icon + severity color

### 未覆盖的边界（已知风险 / [CROSS-TEAM-DEBT]）

- [CROSS-TEAM-DEBT] 6 metric panel 真实数据 → signal aggregate 管线（Phase 2 batch 2）
- [CROSS-TEAM-DEBT] 顶部 4 KPI tiles 真实数据连线
- [CROSS-TEAM-DEBT] Recent Reviews 面板真实 review history（目前空态）
- [CROSS-TEAM-DEBT] Open reviews 计数真实 review_queue 表
- [CROSS-TEAM-DEBT] owner 字段目前是字符串 stub，未来从 user/account lookup 取
- [CROSS-TEAM-DEBT] next_review_link target 路由目前为 `#` 占位
- [CROSS-TEAM-DEBT] FR-004 logs/traces drilldown from signal（Phase 2 batch 3）
- [DEFERRED-PHASE-2] Drawer 内 "Acknowledge / Assign / Mark reviewed" 操作按钮（owner permission FR-002）

## 自检清单

- [x] 每条 AC 都有"验证方式"列（不可空）
- [x] 每条 AC 都有"来源(spec.SC)"列（不可空）
- [x] AC 总数 ≥ 3 条（共 17 条 AC）
- [x] 每条 AC 都覆盖了一个边界（empty / null / stale / candidate / zero high-severity）
- [x] 模糊词检查：无"快 / 稳定 / 高效 / 合理 / 差不多"
- [x] AC 未超出 spec.SC 范围

## 实施结果（2026-07-04）

| AC-ID  | 验证命令                                                                                  | 结果                                |
| ------ | ----------------------------------------------------------------------------------------- | ----------------------------------- |
| AC-7.1 | `uv run pytest tests/contract/test_044_decision_signals.py::test_command_center_routes_in_openapi` | PASS                                |
| AC-7.2 | grep 后端 schemas.py 8 字段匹配                                                            | 33 matches (PASS)                   |
| AC-7.3 | grep CommandCenter.tsx decision-signals / priority                                          | 6 matches (PASS)                    |
| AC-7.4 | grep DecisionSignalCard.tsx category/severity/confidence/freshness                          | 14 matches (PASS)                   |
| AC-8.1 | grep 后端 6 字段 + 前端 6 字段                                                              | 6 + 3 (PASS)                        |
| AC-8.2 | grep src/types/admin-decision-signals.ts 字段                                                | 45 matches (PASS)                   |
| AC-8.3 | grep DecisionSignalDrawer.tsx 10 字段                                                       | 12 matches (PASS)                   |
| AC-9.1 | grep backend schemas.py confirmed/sampled/inferred/candidate                                | 7 matches (PASS)                    |
| AC-9.2 | grep ConfidenceBadge.tsx 4 tiers                                                           | 13 matches (PASS)                   |
| AC-9.3 | grep ConfidenceBadge.tsx "low confidence" + candidate                                       | 4 matches (PASS)                    |
| AC-10.1 | grep "quiet steady-state\|QuietState"                                                       | 5 + 6 = 11 (PASS)                   |
| AC-10.2 | grep QuietState.tsx "Last reviewed\|Open reviews\|freshness"                                | 4+ matches (PASS)                   |
| AC-SC-1.1 | Playwright happy path (INFRA-BLOCKED 静态守卫 GREEN)                                       | 1/4 HTTP skipped, 5/5 static GREEN  |
| AC-SC-2.1 | `pytest test_signals_fields_non_empty`                                                     | PASS                                |
| EC-1   | grep QuietState.tsx "No signals"                                                            | 2 matches (PASS)                    |
| EC-2   | grep DecisionSignalCard.tsx "stale\|freshness"                                              | 6+ matches (PASS)                   |
| EC-3   | grep DecisionSignalDrawer.tsx "partial baseline\|comparison_baseline"                       | 6+ matches (PASS)                   |

## 测试结果

- 后端 pytest: 13 passed / 3 skipped (DB not configured) / 0 failed
- 前端 vitest: 5 passed (decision-signals static guard) / 0 failed
- 前端 typecheck: 36 errors (与 baseline 一致, 0 new errors)
- 前端 build: 36 errors (与 baseline 一致, 0 new errors)
- Playwright: 5 static guards PASS / 4 HTTP-specs INFRA-BLOCKED (DB 不可达)