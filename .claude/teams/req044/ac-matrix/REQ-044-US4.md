---
req_id: REQ-044-US4
status: locked
locked_at: 2026-07-04
locked_by: dev-implement
negotiation_rounds: 0
---

# Acceptance Matrix for REQ-044-US4 — Incidents & Badcases (FR-021~FR-023 业务层)

## SC Gaps

- 无。spec.md US4 (line 196-225) + SC-007 已声明 impact-first grouping + 3-minute drilldown;FR-021~FR-023 业务层字段 + 12 Edge Cases 中 incident / freshness / shared root cause / status-change 4 类已覆盖。
- 唯一缺口:spec US4 line 222-223 说 "low confidence anomaly → candidate label, separated from confirmed incidents" 已锁 EC-1。
- spec US4 line 213-217 "affected counts, affected cohorts, related AI tasks, related releases, related logs/traces, and recent comments" → FR-022 evidence_links 8 类 (product_metric / user_impact / ai_task / eval_case / log / trace / release / comment)。

## AC 矩阵

| AC-ID | 描述 | 验证方式 (命令/测试名/可观测指标) | 来源 (spec) |
|-------|------|-----------------------------------|-------------|
| AC-21.1 | 后端 `GET /api/v1/admin-console/incidents` 返回 incidents list,字段: id / severity (P0/P1/P2/P3) / status (open/investigating/resolved/postmortem) / owner / affected_feature_area / affected_journey_step / first_seen_at / last_seen_at / trend (rising/stable/declining) / title | `cd backend && uv run pytest tests/contract/test_044_incidents.py::test_list_incidents_has_all_fields -v` | FR-021 |
| AC-21.2 | incident 列表按 severity desc + last_seen_at desc 排序 | `cd backend && uv run pytest tests/contract/test_044_incidents.py::test_incidents_sorted_by_severity_then_last_seen -v` | FR-021 |
| AC-21.3 | 后端 `GET /api/v1/admin-console/incidents/{id}` 返回 single incident detail (含 common_root_cause + linked_incident_ids 字段, EC-2) | `cd backend && uv run pytest tests/contract/test_044_incidents.py::test_get_incident_detail_includes_common_root_cause -v` | FR-021 + EC-2 |
| AC-21.4 | workspace 顶部 filter bar 含 7 维度 (severity / status / owner / feature_area / journey / date range / trend) | `grep -c "filter-bar\|severity-filter\|status-filter\|owner-filter" src/admin/components/incidents/IncidentFilterBar.tsx` 期望 ≥ 4 | FR-021 |
| AC-21.5 | incident card 显示 severity color + trend arrow (↑/→/↓) + 8 字段 | `grep -c "trend-arrow\|TrendArrow\|severity-badge" src/admin/components/incidents/IncidentCard.tsx` 期望 ≥ 2 | FR-021 |
| AC-22.1 | 后端 `GET /api/v1/admin-console/incidents/{id}/evidence` 返回 evidence_links 数组,每条 type ∈ {product_metric, user_impact, ai_task, eval_case, log, trace, release, comment} + reference_id | `cd backend && uv run pytest tests/contract/test_044_incidents.py::test_evidence_links_cover_eight_types -v` | FR-022 |
| AC-22.2 | 后端 `POST /api/v1/admin-console/incidents/{id}/comments` 添加 comment (audit logged, requires INCIDENT_CHANGE capability) | `cd backend && uv run pytest tests/contract/test_044_incidents.py::test_add_comment_requires_incident_change -v` | FR-022 |
| AC-22.3 | 前端 incident drawer 顶部 tabs: Overview / Evidence (含 8 类链接) / Comments | `grep -c "tab-overview\|tab-evidence\|tab-comments" src/admin/components/incidents/IncidentDrawer.tsx` 期望 ≥ 3 | FR-022 |
| AC-22.4 | evidence link 点击跳转对应详情 (US5 log/trace 占位、US3 ai_task、US2 user、US6 release) | `grep -c "openEvidence\|onClick\|href" src/admin/components/incidents/EvidenceLinkList.tsx` 期望 ≥ 2 | FR-022 |
| AC-23.1 | 后端 `GET /api/v1/admin-console/badcases` 返回 badcases list,字段: id / eval_verdict / affected_feature_area / affected_user_id / privacy_class / classification / owner / status (open/reviewing/closed/escalated) / resolution / first_seen_at | `cd backend && uv run pytest tests/contract/test_044_incidents.py::test_list_badcases_has_all_fields -v` | FR-023 |
| AC-23.2 | badcase list 视觉与 incident 类似但额外显示 eval_verdict badge + privacy_class indicator | `grep -c "eval-verdict\|privacy-class\|PrivacyIndicator" src/admin/components/incidents/BadcaseList.tsx` 期望 ≥ 2 | FR-023 |
| AC-23.3 | badcase drawer 顶部 tabs: Overview / Privacy / AI Task / Comments | `grep -c "tab-overview\|tab-privacy\|tab-ai-task\|tab-comments" src/admin/components/incidents/BadcaseDrawer.tsx` 期望 ≥ 4 | FR-023 |
| AC-23.4 | badcase drawer "Escalate to Incident" 按钮 (requires BADCASE_CHANGE capability) — POST /badcases/{id}/escalate 返回新 incident id | `cd backend && uv run pytest tests/contract/test_044_incidents.py::test_escalate_badcase_to_incident -v` | FR-023 |
| SC-7.1 | Playwright: 从 Command Center decision signal 点 "investigate" → 自动跳 incident detail → drawer evidence tab 7 类 link 全部存在 + 至少 1 条可达 (logs/traces 占位) | `cd tests/e2e && npx playwright test 044-incidents.spec.ts --reporter=line` 期望 ≥ 1 spec | SC-007 |
| EC-1 | low confidence anomaly → 显式标 "candidate" 不被合并到 confirmed incidents (separate list / separate section) | `cd backend && uv run pytest tests/contract/test_044_incidents.py::test_candidate_incident_labeled -v` | Edge Cases line 323 |
| EC-2 | 共享技术 root cause 但不同 journey 的 incident → display "common root cause" 标签 + cross-link | `cd backend && uv run pytest tests/contract/test_044_incidents.py::test_common_root_cause_cross_link -v` | Edge Cases line 323 |
| EC-3 | 数据导入延迟导致 incident → freshness_at 显示 + "ingestion delayed" label | `cd backend && uv run pytest tests/contract/test_044_incidents.py::test_ingestion_delayed_label -v` | Edge Cases line 325 |
| EC-4 | 状态变更 (assign / resolve) → audit log 必含 actor / timestamp / reason / before_state / after_state | `cd backend && uv run pytest tests/contract/test_044_incidents.py::test_status_change_audit_trail -v` | spec US4 line 218-220 |

## 起草说明（写给 tester）

### 设计意图

- US4 范围 = FR-021~FR-023 业务层 + SC-007 3-minute drilldown + Edge Cases 4 类 (candidate / shared root cause / delayed ingestion / status-change audit)。
- 后端模块路径:`backend/app/modules/admin_console/incidents/` (独立子目录,沿 US1 decision_signals + US2 product_analytics + US3 ai_operations 模式)。
- 数据源 = `seed_demo_incidents` + `seed_demo_badcases` 静态 seed,严格沿 US1/2/3 pattern。**禁止** silent empty fallback — 零 incident 时返回 `total=0` + `freshness_at="unknown"` (FR-028 valid_zero)。
- 真实 incident / badcase 持久化 = `[CROSS-TEAM-DEBT]` Phase 2 batch 4:US4 仅交付 workspace surface + 类型契约 + seed 数据,真实 incident 表在 governance US6 审计 + 真实 badcase join 接 REQ-026 badcases 表。
- 复用 baseline (heavy reuse,不动):
  - `backend/app/modules/admin_console/decision_signals/` — US1 seed pattern + 7 类 EvidenceLink kind
  - `backend/app/modules/admin_console/product_analytics/` — US2 seed pattern + service/api shape
  - `backend/app/modules/admin_console/ai_operations/` — US3 seed pattern + quality issue link 8 字段
  - `backend/app/modules/admin_console/audit.py` — 4 writers (US1 扩 7 类) US4 继续扩 incident_change / incident_comment / badcase_change / badcase_escalate 4 类
  - `backend/app/modules/admin_console/auth.py` — 5 role grants (US3 已扩 5 token) US4 继续扩 INCIDENT_VIEW / BADCASE_VIEW / INCIDENT_CHANGE / BADCASE_CHANGE 4 token
  - `backend/app/modules/badcases/` — REQ-026 已有 badcases 表 (READ ONLY,在 service 中遍历数据但不修改 schema)
  - `src/admin/pages/IncidentsBadcases.tsx` — 当前 placeholder,US4 全量升级
  - `src/types/admin-console.ts:17` — WorkspaceId `'incidents-badcases'` 已声明
  - 7 个独立 endpoint (list / get / evidence / comment / status / badcases list / badcase get / badcase escalate),每个 endpoint 独立 service 函数 + 独立 seed 函数。

### 已覆盖的边界

- EC-1 low confidence anomaly → `severity="info"` + `confidence="candidate"` + frontend label "candidate" 单独 section 不与 confirmed 合并
- EC-2 shared root cause → `common_root_cause` + `linked_incident_ids` 字段 + frontend cross-link button
- EC-3 ingestion delayed → `freshness_at` + `ingestion_delayed=true` 字段 + frontend label "ingestion delayed"
- EC-4 status change audit → `audit_trail` 字段 (actor / timestamp / reason / before_state / after_state) + 后端 `audit.log_incident_change` 必写
- FR-022 evidence 8 类 (product_metric / user_impact / ai_task / eval_case / log / trace / release / comment) 必覆盖
- FR-023 badcase escalate → POST /badcases/{id}/escalate 返回 `{incident_id: "inc-..."}` + 必带 BADCASE_CHANGE capability check
- SC-007 3-minute drilldown → evidence tab 8 类 link 全部可达 (US5 log/trace 占位路由, US3 ai_task 路由, US2 user 路由, US6 release 占位)

### 未覆盖的边界（已知风险 / [CROSS-TEAM-DEBT]）

- 真实 incident 持久化表 → seed 静态 incident + badcase rows,Phase 2 batch 4 接 `incidents` 表 + governance US6 审计
- 真实 badcase join REQ-026 → seed 静态 badcase_id 引用现有 badcases 行,Phase 2 batch 4 接 `badcases` 表 (READ ONLY)
- 真实 audit log 持久化 → US1 已用 in-memory `_AUDIT_LOG` (US4 沿用),Phase 2 batch 4 + governance US6 接 DB-backed audit_log
- 真实 SC-007 3-min drilldown → 验证 evidence tab 7+1 类 link 路由可达,不验证实际跳转时间 (Playwright INFRA-BLOCKED 标记可接受)
- badcase escalate 的真实评审流 → seed 返回 mock incident_id,Phase 2 batch 4 接 review_queue + assignment workflow

### 铁律复审

- 铁律 A: seed_demo_incidents + seed_demo_badcases 模式严格沿 US1/2/3;无 silent empty fallback (零 incident → total=0 + freshness_at="unknown")
- 铁律 C: 不动 src/admin/components/log/ 7 + decision-signals/ 5 + product-analytics/ 5 + users/ 1 + ai-operations/ 10 文件
- 铁律 D: 前端 Incident / Badcase / EvidenceLink / Comment / AuditTrail 字段 = 后端 Pydantic 字段;加 [CROSS-TEAM-DEBT] 标"真实 incident 表在 Phase 2 batch 4 + governance US6 审计"
- 铁律 E: grep 字面精确 (AC-21.4/21.5/22.3/22.4/23.2/23.3)
- 跨团队: 仅新建 backend/app/modules/admin_console/incidents/ 子目录;只读 + 复用 (不修改) agents/errors/interviews/resumes/jobs/ability/ability_profile/ability_diagnose/auth/sessions/eval/badcases/telemetry_contracts/pm_dashboard 内部实现
