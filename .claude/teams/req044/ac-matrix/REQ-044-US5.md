---
req_id: REQ-044-US5
status: locked
locked_at: 2026-07-04
locked_by: dev-implement
negotiation_rounds: 0
---

# Acceptance Matrix for REQ-044-US5 — Maintainer Drilldown (FR-023 tech layer / FR-024~FR-026)

## SC Gaps

- 无。spec.md US5 (line 227-255) 4 acceptance scenarios 已声明 "drilldown from signal to root cause" + "structured field filter" + "redacted sensitive" + "approved reveal + audit" — FR-024~FR-026 全覆盖 + Edge Cases line 327-331 三类 (logs no event / events no trace / reveal denied) 已映射到 EC-1/2/3。
- Edge Cases line 328-329 "Product events exist without trace coverage because a legacy path bypassed centralized instrumentation" → FR-025 coverage gap 显式提示,US5 显式 label 不归为 "no data"。

## AC 矩阵

| AC-ID | 描述 | 验证方式 (命令/测试名/可观测指标) | 来源 (spec) |
|-------|------|-----------------------------------|-------------|
| AC-24.1 | LogsAndTraces.tsx 顶部 search bar 接受 query param `?from=incident:{id}` / `?from=signal:{id}` / `?from=badcase:{id}`,自动加载该事件关联的 log/trace list | `grep -c "from=incident\|from=signal\|from=badcase\|drilldownFrom\|useSearchParams.*from" src/admin/pages/LogsAndTraces.tsx src/admin/components/log/DrilldownBanner.tsx` 期望 ≥ 4 | FR-024 |
| AC-24.2 | drilldown 后顶部 banner 显示 "Drilldown from <source_type>:<id>" + "back to source" 链接,链接 href 反向回到 source 详情 (incident / signal / badcase) | `grep -c "drilldown-from\|back-to-source\|backToSource\|DrilldownBanner" src/admin/components/log/DrilldownBanner.tsx` 期望 ≥ 3 | FR-024 |
| AC-24.3 | log/trace list 默认按 `correlation_id` 过滤;若 `from=incident` 且 incident 关联 `trace_id` → 自动选中 trace (打开 detail panel) | `grep -c "correlationId\|correlation_id\|selectTrace\|autoSelectTrace" src/admin/components/log/DrilldownBanner.tsx src/admin/pages/LogsAndTraces.tsx` 期望 ≥ 3 | FR-024 |
| AC-24.4 | drilldown URL 必须保持可分享 (clean query string format `?from=incident:inc-XXX`),被多人复制打开行为一致 | `grep -c "encodeURIComponent\|from.split\|formatDrilldownParam" src/admin/components/log/DrilldownBanner.tsx` 期望 ≥ 1 | FR-024 |
| AC-25.1 | LogsAndTraces.tsx 在 search 无结果时显式 "No correlated logs found" + "Possible reasons: trace coverage gap / instrumentation incomplete / legacy path bypassed OTel" | `grep -c "coverage-gap\|coverage_gap\|CoverageGap\|No correlated" src/admin/components/log/CoverageGapNotice.tsx` 期望 ≥ 3 | FR-025 |
| AC-25.2 | coverage gap 显式 label 不被静默归为 "no data" — 空状态必须含 data-testid="coverage-gap-notice" 区分普通 empty state | `grep -c "coverage-gap-notice\|coverage-gap-banner" src/admin/components/log/CoverageGapNotice.tsx src/admin/pages/LogsAndTraces.tsx` 期望 ≥ 2 | FR-025 |
| AC-25.3 | 后端 *(no-op;前端纯展示;US5 = frontend-workspace scope)* | `git diff --stat master..HEAD -- backend/` 期望 0 行改动 (跨团队硬约束) | FR-025 |
| AC-26.1 | LogDetailDrawer 显示 agent_run / node / tool_call / llm_call 4 类结构化字段 panel | `grep -c "AgentRunPanel\|NodeExecutionPanel\|ToolCallPanel\|LLMCallPanel\|agent-run-panel\|node-execution-panel\|tool-call-panel\|llm-call-panel" src/admin/components/log/LogDetailDrawer.tsx` 期望 ≥ 6 | FR-026 |
| AC-26.2 | 每个 node execution 含 timestamp / duration / status / retry_count / version_context (model + prompt_fingerprint + rubric_version + app_version) | `grep -c "retry_count\|retryCount\|promptFingerprint\|rubricVersion\|appVersion\|version_context" src/admin/components/log/NodeExecutionPanel.tsx` 期望 ≥ 5 | FR-026 |
| AC-26.3 | LLM call detail 显示 model / input_tokens / output_tokens / cache_hit / latency / cache_key fingerprint | `grep -c "input_tokens\|outputTokens\|cacheHit\|cacheKey\|cacheFingerprint" src/admin/components/log/LLMCallPanel.tsx` 期望 ≥ 4 | FR-026 + FR-027 |
| AC-26.4 | tool call 显示 tool_name + input_schema_ref + output_summary + error (if any) | `grep -c "toolName\|tool_name\|inputSchemaRef\|input_schema_ref\|outputSummary\|output_summary\|toolError" src/admin/components/log/ToolCallPanel.tsx` 期望 ≥ 4 | FR-026 |
| AC-26.5 | 敏感 payload (raw_prompt / raw_model_output) 默认 masked 显示 "permission: hidden";可点 "Request Reveal" 按钮 | `grep -c "permission: hidden\|permission-hidden\|raw_prompt\|rawPrompt\|raw_model_output\|rawModelOutput\|Request Reveal\|request-reveal" src/admin/components/log/LogDetailDrawer.tsx src/admin/components/log/LLMCallPanel.tsx` 期望 ≥ 4 | FR-026 |
| AC-26.6 | "Request Reveal" 按钮点击 → 跳 `/admin-console/governance?reveal=llm_call:{call_id}` 带 query param (US6 read) | `grep -c "governance?reveal=\|reveal=llm_call\|reveal=agent_run\|reveal=" src/admin/components/log/LogDetailDrawer.tsx src/admin/components/log/LLMCallPanel.tsx src/admin/components/log/NodeExecutionPanel.tsx src/admin/components/log/ToolCallPanel.tsx` 期望 ≥ 2 | FR-026 + FR-033 |
| EC-1 | 敏感 reveal request 拒后用户已开 trace drawer → drawer 关闭 + "access denied" 提示 (与 US6 EC-1 一致, 监听 `ic:reveal-denied` CustomEvent) | `grep -c "ic:reveal-denied\|reveal-denied\|access-denied\|accessDenied" src/admin/components/log/LogDetailDrawer.tsx` 期望 ≥ 2 | Edge Cases line 330-331 |
| EC-2 | 多个 incident 共享 trace → log detail drawer 显示 "Shared by: incident A, incident B" cross-link 列表 | `grep -c "SharedByIncidentList\|shared-by-incident\|sharedBy\|shared_by" src/admin/components/log/SharedByIncidentList.tsx src/admin/components/log/LogDetailDrawer.tsx` 期望 ≥ 2 | Edge Cases line 323 |
| EC-3 | legacy path 无 trace → coverage gap 提示 (FR-025);空 list 显示 CoverageGapNotice 而非通用 "no data" | `grep -c "CoverageGapNotice\|coverage-gap-notice" src/admin/pages/LogsAndTraces.tsx src/admin/components/log/CoverageGapNotice.tsx` 期望 ≥ 2 | Edge Cases line 328-329 |
| TS-1 | vitest: LogsAndTraces drilldown + coverage gap + 4 类 panel + masked payload unit tests pass | `cd src && npm run test -- --run src/admin/components/log/__tests__/logs-drilldown.test.tsx 2>&1` 期望 ≥ 8 tests pass | TS-1 |
| TS-2 | typecheck: 0 new error | `cd src && npm run typecheck 2>&1` 期望 0 new error | TS-2 |
| TS-3 | build: vite build success | `cd src && npm run build 2>&1` 期望 dist/ 产出 | TS-3 |
| TS-4 | Playwright E2E happy path: drilldown from incident → log list filtered → click log → detail drawer with 4 类 fields + masked payload + Request Reveal 跳 US6 | `cd tests/e2e && npx playwright test 044-logs-drilldown.spec.ts --reporter=line 2>&1` 期望 ≥ 1 spec (INFRA-BLOCKED acceptable) | SC-007 + E2E |

## 起草说明（写给 tester）

### 设计意图

- US5 范围 = FR-024 (drilldown from signal) + FR-025 (coverage gap) + FR-026 (safe tech detail for agent/node/tool/LLM) + 3 Edge Cases (reveal-denied / shared-by-incident / coverage-gap) + spec US5 line 252-255 (sensitive payload + approved reveal)。
- **scope: frontend-workspace**（不写后端）— 后端 ALREADY ship 的 LogCenter API + admin_console.audit + governance reveal_request endpoint 都已可用 (US1/US6)。US5 是纯前端消费 + 4 类结构化 panel + masked payload + reveal-跳转。
- Drilldown 入口：US4 EvidenceLinkList type=log|trace + US1 DecisionSignalDrawer evidence_links + US6 EC-1 → 都通过 `?from={source_type}:{id}` query param 跳到 LogsAndTraces workspace。
- 数据源 = mock fixtures (US1/US6 baseline 模式);FR-026 sensitive payload = mock 数据即含 raw_prompt / raw_model_output 字段,默认 masked 显示 "permission: hidden"。真实 OTel trace 查询 = [CROSS-TEAM-DEBT] Phase 2 batch 6 接 029 otel-langgraph-trace 模块。

### 已覆盖的边界

- EC-1 reveal-denied → `LogDetailDrawer` 监听 `window.addEventListener('ic:reveal-denied')` → 关闭 drawer + 显示 "access denied" 提示 banner。
- EC-2 shared by incident → `SharedByIncidentList` cross-link,LogDetailDrawer 顶部展示,点击跳回 incident detail。
- EC-3 coverage gap → `CoverageGapNotice` 显示 3 类原因 + data-testid 区分普通 empty state。
- FR-026 sensitive masking → 5 类敏感字段 (raw_prompt / raw_model_output / raw_input / raw_output / redaction_token) 全部 "permission: hidden" + "Request Reveal" 按钮。
- FR-024 drilldown URL → `?from=incident:inc-001` + `?from=signal:ds-001` + `?from=badcase:bc-001` 三种格式,query param 可复制粘贴。
- FR-027 LLM cache hint → LLMCallPanel 显示 cache_hit + cache_key fingerprint (复用 US3 ai_operations 已有 schema)。

### 未覆盖的边界（已知风险 / [CROSS-TEAM-DEBT]）

- 真实 OTel trace span 查询 → mock 数据即含 AgentRun / NodeExecution / ToolCall / LLMCall 字段,Phase 2 batch 6 接 `backend/app/observability/otel/` 真实 trace_id 关联 (029 otel-langgraph-trace 模块)。
- 真实 coverage gap 检测 → 前端 mock 决定是否显示 CoverageGapNotice;Phase 2 batch 6 接后端 `coverage_report` endpoint (US5 仅 frontend)。
- 真实 shared-by-incident 反查 → mock 数据即含 shared_by_incident_ids;Phase 2 batch 4 接真实 incidents JOIN trace 表。
- 真实 SENSITIVE_REVEAL capability check → mock 即视为已 grant;US6 governance 已 ship 后端 Pydantic Literal。
- US5 = frontend-workspace,后端 ALREADY ship 的 LogCenter API + governance endpoint 都已可用。

### 铁律复审

- 铁律 A: 不写后端 seed;前端 mock fixture (沿 US1/US6 pattern) + 即用即弃;新增查询逻辑时若失败 → throw NotImplementedError (US1 baseline)。
- 铁律 C: src/admin/components/log/ 7 + 新增 7 子组件 (DrilldownBanner / CoverageGapNotice / NodeExecutionPanel / ToolCallPanel / LLMCallPanel / SharedByIncidentList + LogDetailDrawer 改造) = US5 frontend 全部;FilterBar/TaskList/CommandPalette/Dialogs/ErrorAggregation/index.tsx 内部不动。
- 铁律 D: 前端 LogEvent / TraceSpan / AgentRun / NodeExecution / ToolCall / LLMCall 字段 = 后端 REQ-039 已有 schema + US6 governance schema;加 [CROSS-TEAM-DEBT] 标"真实 OTel trace 查询 Phase 2 batch 6 接 029 otel-langgraph-trace 模块"。
- 铁律 E: grep 字面精确 (AC-24.1/24.2/24.3/24.4/25.1/25.2/26.1/26.2/26.3/26.4/26.5/26.6/EC-1/EC-2/EC-3)。
- 跨团队: 仅新建 src/types/admin-logs.ts + src/api/admin-logs.ts + src/admin/components/log/{6 新文件} + 改造 LogsAndTraces.tsx + LogDetailDrawer.tsx + src/admin/components/log/__tests__/index.test.tsx;不触碰 src/admin/components/{decision-signals,product-analytics,users,ai-operations,incidents,governance} 任何已有文件;不触碰 backend/。