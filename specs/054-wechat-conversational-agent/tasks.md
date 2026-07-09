# Tasks: WeChat Conversational Agent

**Input**: Design documents from `/specs/054-wechat-conversational-agent/`

**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/

**Tests**: Included per Constitution Principle III (Test-First), plan Testing section, and SC-009 (E2E for US1/US2/US4).

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Backend**: `backend/app/`, `backend/tests/`
- **E2E**: `tests/e2e/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Scaffold conversation package and test directories per plan.md

- [x] T001 Create conversation package skeleton under `backend/app/modules/agent/conversation/` with `__init__.py`, `orchestrator.py`, `intent_parser.py`, `context_store.py`, `confirmations.py`, `job_matcher.py`, `time_parser.py`, `reply_formatter.py`, `metrics.py`
- [x] T002 [P] Create tools package skeleton: `backend/app/modules/agent/conversation/tools/__init__.py`, `create_job.py`, `update_status.py`, `update_fields.py`, `query_jobs.py`, `query_reports.py`, `query_ability.py`
- [x] T003 [P] Create interview adapter skeleton: `backend/app/modules/agent/conversation/interview/__init__.py`, `adapter.py`, `mutex.py`
- [x] T004 [P] Create unit test package dirs: `backend/tests/unit/agent/conversation/__init__.py` and `backend/tests/unit/agent/conversation/tools/__init__.py`
- [x] T005 [P] Create integration test stubs: `backend/tests/integration/agent/test_conversation_jobs.py`, `backend/tests/integration/agent/test_conversation_interview.py`
- [x] T006 [P] Create Playwright E2E directory and stubs: `tests/e2e/wechat-conversation/create-job.spec.ts`, `update-status.spec.ts`, `mock-interview.spec.ts`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared conversation runtime that MUST exist before any user story tools

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

### Tests for Foundation

- [x] T007 [P] Write failing unit tests for Redis `ConversationContext` load/save/TTL refresh in `backend/tests/unit/agent/conversation/test_context_store.py`
- [x] T008 [P] Write failing unit tests for confirm/cancel lexicon and `awaiting_confirmation` gating in `backend/tests/unit/agent/conversation/test_confirmations.py`
- [x] T009 [P] Write failing unit tests for intent JSON parse + confidence&lt;0.6 + LLM retry-once degrade in `backend/tests/unit/agent/conversation/test_intent_parser.py` (mock `LLMClient`)
- [x] T010 [P] Write failing unit tests for reply length/segment helpers in `backend/tests/unit/agent/conversation/test_reply_formatter.py`

### Implementation for Foundation

- [x] T011 Implement `ConversationContext` Redis store (key `wechat:conversation:{user_id}`, TTL 24h, refresh on touch, redis-unavailable error path) in `backend/app/modules/agent/conversation/context_store.py`
- [x] T012 [P] Implement confirm/cancel word lists + pending_action helpers in `backend/app/modules/agent/conversation/confirmations.py` per FR-017 and `contracts/tools.yaml`
- [x] T013 [P] Implement WeChat reply formatter (≤500 chars guidance, multi-segment via existing split helpers) in `backend/app/modules/agent/conversation/reply_formatter.py`
- [x] T014 [P] Implement Prometheus metrics stubs for FR-019 in `backend/app/modules/agent/conversation/metrics.py` (`conversation_turns_total`, `intent_confidence_histogram`, `tool_call_success_rate`, `interview_via_wechat_total`, `conversation_duration_seconds`)
- [x] T015 Implement `IntentParser` (DeepSeek via `LLMClient`, schema from `contracts/intents.yaml`, retry 1×, no keyword write fallback) in `backend/app/modules/agent/conversation/intent_parser.py`
- [x] T016 Implement `ConversationOrchestrator` state machine skeleton (`idle` / `awaiting_confirmation` / `in_interview`) with structured logging per FR-020 (no raw message body) in `backend/app/modules/agent/conversation/orchestrator.py`
- [x] T017 Wire inbound path: `AgentService.process_inbound_reply` / `backend/app/agents/personal.py` delegates to `ConversationOrchestrator.handle`; keep thin fallback reply on hard failure
- [x] T018 Add per-user inbound serialization (asyncio lock or Redis lock) in `backend/app/channels/ilink_pool.py` or orchestrator entry so messages for one user process FIFO
- [x] T019 Add CLI `parse-intent` command with `--json` in `backend/app/modules/agent/cli.py` per `contracts/cli.md`
- [x] T020 Add CLI `simulate-chat <user_id>` REPL (bypass iLink, print replies) in `backend/app/modules/agent/cli.py` per `contracts/cli.md`

**Checkpoint**: Foundation ready — intent parse + context + confirm gate + CLI work; user story tools can begin

---

## Phase 3: User Story 1 — 通过微信新增岗位 (Priority: P1) 🎯 MVP

**Goal**: 用户用自然语言新增求职岗位；缺字段追问；确认后调用 `JobService.create`；取消不写库

**Independent Test**: `simulate-chat` 或 mock 入站发送「帮我记一个字节跳动的AI应用开发工程师岗位」→ 确认卡片 →「确认」→ DB 出现 job；未确认前无写入

### Tests for US1

- [x] T021 [P] [US1] Write failing unit tests for `create_job` prepare/execute (missing position ask, confirmation required) in `backend/tests/unit/agent/conversation/tools/test_create_job.py`
- [x] T022 [P] [US1] Write failing integration test: orchestrator create_job confirm flow persists job in `backend/tests/integration/agent/test_conversation_jobs.py`
- [x] T023 [P] [US1] Write failing Playwright E2E for US1 in `tests/e2e/wechat-conversation/create-job.spec.ts` (mock WeChat inbound → assert job via API/DB)

### Implementation for US1

- [x] T024 [US1] Implement `create_job` tool prepare/execute calling `JobService` in `backend/app/modules/agent/conversation/tools/create_job.py` per FR-005 and `contracts/tools.yaml`
- [x] T025 [US1] Route `create_job` intent in `backend/app/modules/agent/conversation/orchestrator.py`: slot-filling → confirmation card → execute on confirm / cancel clears pending
- [x] T026 [US1] Add create-success / create-failure WeChat copy in `backend/app/modules/agent/conversation/reply_formatter.py` (match US1 acceptance scenarios)
- [x] T027 [US1] Emit `conversation_turns_total{intent=create_job}` and tool success metrics from create path in `backend/app/modules/agent/conversation/metrics.py`

**Checkpoint**: US1 MVP — WeChat/CLI 可完成新增岗位全流程

---

## Phase 4: User Story 2 — 通过微信修改岗位状态 (Priority: P1)

**Goal**: 模糊匹配岗位、合法状态推进、面试时间（Asia/Shanghai）、确认后 `update_status`；另支持改地点/JD/备注；拒绝删除/Offer

**Independent Test**: 「字节进一面了，下周一 14:00 面试」→ 确认卡绝对时间 → 确认 → `interview_1` + `interview_time`；非法回退被拒；「删掉岗位」引导 Web

### Tests for US2

- [x] T028 [P] [US2] Write failing unit tests for Asia/Shanghai relative time parsing in `backend/tests/unit/agent/conversation/test_time_parser.py`
- [x] T029 [P] [US2] Write failing unit tests for job fuzzy matcher priority + multi-candidate list in `backend/tests/unit/agent/conversation/test_job_matcher.py`
- [x] T030 [P] [US2] Write failing unit tests for `update_status` / `update_fields` prepare (illegal transition, missing interview_time, reject delete/offer) in `backend/tests/unit/agent/conversation/tools/test_update_status.py` and `test_update_fields.py`
- [x] T031 [P] [US2] Extend integration tests for status advance + field patch in `backend/tests/integration/agent/test_conversation_jobs.py`
- [x] T032 [P] [US2] Write failing Playwright E2E for US2 in `tests/e2e/wechat-conversation/update-status.spec.ts`

### Implementation for US2

- [x] T033 [P] [US2] Implement `time_parser.py` (fixed `Asia/Shanghai`, 今天/明天/下周一, absolute confirm display) in `backend/app/modules/agent/conversation/time_parser.py` per FR-006b
- [x] T034 [P] [US2] Implement `job_matcher.py` (exact company+position → company contains → position contains → recent; max 5) in `backend/app/modules/agent/conversation/job_matcher.py` per FR-007
- [x] T035 [US2] Implement `update_status` tool via `JobService.update_status` + `JOB_TRANSITIONS` in `backend/app/modules/agent/conversation/tools/update_status.py` per FR-006
- [x] T036 [US2] Implement `update_fields` tool (only `base_location`/`jd_url`/`notes_md`; delete/Offer → Web guide) in `backend/app/modules/agent/conversation/tools/update_fields.py` per FR-006a
- [x] T037 [US2] Wire `update_status` / `update_job_fields` intents + ambiguous job selection prompts in `backend/app/modules/agent/conversation/orchestrator.py`
- [x] T038 [US2] Add failed/passed confirmation copy (optional failure note; Offer reminder → Web) in `backend/app/modules/agent/conversation/reply_formatter.py`

**Checkpoint**: US1+US2 写路径完整（create / status / allowed fields）

---

## Phase 5: User Story 3 — 通过微信查询求职状态 (Priority: P2)

**Goal**: 查询概览、按阶段列表、单岗详情、近 7 天面试；API 失败重试 1 次后友好错误

**Independent Test**: 「我的求职进展」→ 状态分布摘要；「有哪些岗位在面试阶段」→ 列表

### Tests for US3

- [x] T039 [P] [US3] Write failing unit tests for `query_jobs` aggregation/format (≤300 chars) in `backend/tests/unit/agent/conversation/tools/test_query_jobs.py`
- [x] T040 [P] [US3] Write failing integration test for query_jobs happy + API failure path in `backend/tests/integration/agent/test_conversation_jobs.py`

### Implementation for US3

- [x] T041 [US3] Implement `query_jobs` tool (list + status histogram + detail/filter helpers) in `backend/app/modules/agent/conversation/tools/query_jobs.py` per FR-013
- [x] T042 [US3] Wire `query_jobs` intent (概览 / 面试阶段 / 公司详情 / 近 7 天面试) in `backend/app/modules/agent/conversation/orchestrator.py`
- [x] T043 [US3] Add query failure retry-once + busy copy in `backend/app/modules/agent/conversation/tools/query_jobs.py` / `reply_formatter.py`

**Checkpoint**: 只读求职查询可独立验收

---

## Phase 6: User Story 4 — 微信文字模拟面试 (Priority: P2)

**Goal**: 启动/暂停/继续/结束文字模拟面试；全局互斥；跨渠道续面；复用 `submit_answer` + checkpoint；评分文案 ≤500 字

**Independent Test**: 「开始模拟面试」→ 5 轮作答 → 摘要报告；Web `in_progress` 时微信禁止新建；Web 第 2 轮后微信「继续面试」出第 3 题

### Tests for US4

- [x] T044 [P] [US4] Write failing unit tests for interview mutex (pending/in_progress blocks start) in `backend/tests/unit/agent/conversation/interview/test_mutex.py`
- [x] T045 [P] [US4] Write failing unit tests for adapter pause/continue/end (&lt;3 → expired, ≥3 → partial report) in `backend/tests/unit/agent/conversation/interview/test_adapter.py`
- [x] T046 [P] [US4] Write failing integration tests for WeChat interview round + cross-channel continue in `backend/tests/integration/agent/test_conversation_interview.py`
- [x] T047 [P] [US4] Write failing Playwright E2E for US4 in `tests/e2e/wechat-conversation/mock-interview.spec.ts`

### Implementation for US4

- [x] T048 [US4] Implement global interview mutex helper in `backend/app/modules/agent/conversation/interview/mutex.py` per FR-009a
- [x] T049 [US4] Implement WeChat interview adapter (`start`/`submit_answer`/`pause`/`continue`/`end`, score&gt;30s「评分中…」, format ≤500 chars) in `backend/app/modules/agent/conversation/interview/adapter.py` per FR-009–FR-012 and research.md
- [x] T050 [US4] Ensure `expired` write path exists for end_interview &lt;3 rounds (extend `backend/app/modules/interviews/service.py` if missing)
- [x] T051 [US4] Wire `start_interview` / `continue_interview` / `pause_interview` / `end_interview` + `in_interview` answer default in `backend/app/modules/agent/conversation/orchestrator.py` per FR-011a
- [x] T052 [US4] Increment `interview_via_wechat_total` on completed/expired in `backend/app/modules/agent/conversation/metrics.py`

**Checkpoint**: 微信模拟面试与 Web 共享 session/checkpoint，互斥与续面可测

---

## Phase 7: User Story 5 — 微信查看面试报告与能力画像 (Priority: P3)

**Goal**: 最近报告摘要、报告列表（最多 5）、六维能力画像文字版；无数据时引导开面

**Independent Test**: 「上次面试报告」→ 摘要；「能力画像」→ 六维得分；无报告时引导「开始模拟面试」

### Tests for US5

- [x] T053 [P] [US5] Write failing unit tests for `query_reports` / `query_ability` formatting in `backend/tests/unit/agent/conversation/tools/test_query_reports.py` and `test_query_ability.py`

### Implementation for US5

- [x] T054 [P] [US5] Implement `query_reports` tool (≤5 items, ≤400 chars summary, Web guide) in `backend/app/modules/agent/conversation/tools/query_reports.py` per FR-014
- [x] T055 [P] [US5] Implement `query_ability` tool (6 dimensions + trend arrows; empty → guide interview) in `backend/app/modules/agent/conversation/tools/query_ability.py` per FR-015
- [x] T056 [US5] Wire `query_reports` / `query_ability` intents in `backend/app/modules/agent/conversation/orchestrator.py`

**Checkpoint**: 报告与画像只读查询可用

---

## Phase 8: User Story 6 — 对话纠错与帮助 (Priority: P3)

**Goal**: help 列表、unknown 引导、连续三次无法理解升级文案、复合意图顺序执行、低置信度选项、删除/Offer 拒绝文案

**Independent Test**: 「帮助」→ 四类能力+示例；模糊消息 → 选项；复合「加岗位+查进展」→ 先确认创建再查询

### Tests for US6

- [x] T057 [P] [US6] Write failing unit tests for help/unknown/unknown_streak/compound intent sequencing in `backend/tests/unit/agent/conversation/test_orchestrator_meta.py`
- [x] T058 [P] [US6] Write failing unit test that LLM double-failure never writes jobs in `backend/tests/unit/agent/conversation/test_intent_parser.py`

### Implementation for US6

- [x] T059 [US6] Implement `help` intent structured multi-segment reply in `backend/app/modules/agent/conversation/orchestrator.py` / `reply_formatter.py` per FR-018
- [x] T060 [US6] Implement `unknown` handling + `unknown_streak` escalation (3rd failure copy) using `ConversationContext` in `backend/app/modules/agent/conversation/orchestrator.py`
- [x] T061 [US6] Implement confidence&lt;0.6 alternative picker (user selects → execute without re-parse) in `backend/app/modules/agent/conversation/orchestrator.py` per FR-003
- [x] T062 [US6] Implement compound intent sequential execution (confirm writes before next) in `backend/app/modules/agent/conversation/orchestrator.py` per FR-004
- [x] T063 [US6] Map delete/archive/Offer intents to Web-guide replies (no tool execute) in `backend/app/modules/agent/conversation/intent_parser.py` / `orchestrator.py`

**Checkpoint**: 兜底体验与安全拒绝路径完整

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: 可观测性收尾、可选审计列、quickstart 验收、文档

- [ ] T064 [P] Optional Alembic migration adding nullable `intent` / `confidence` / `metadata` JSONB on `agent_messages` under `backend/migrations/versions/` (non-blocking; skip if deferred)
- [x] T065 [P] Add module README for conversation package in `backend/app/modules/agent/conversation/README.md` (public API, CLI examples, Redis key)
- [x] T066 Verify FR-019 metrics exported and FR-020 logs omit raw message bodies across orchestrator paths
- [x] T067 Run and check off `specs/054-wechat-conversational-agent/quickstart.md` VS-1…VS-8; fix gaps
- [x] T068 [P] Document token quota note for `node_name=intent_parse` in `backend/app/modules/agent/conversation/README.md` or ops note under `docs/`
- [ ] T069 Ensure E2E specs US1/US2/US4 pass under `npm run e2e -- tests/e2e/wechat-conversation` (SC-009)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies
- **Foundational (Phase 2)**: Depends on Setup — **BLOCKS** all user stories
- **US1 (Phase 3)**: After Foundational — MVP
- **US2 (Phase 4)**: After Foundational；可与 US1 并行（不同工具文件），但共享 orchestrator 时建议 US1 先合入确认流
- **US3 (Phase 5)**: After Foundational；建议在 US1 后（可复用 job 列表数据）
- **US4 (Phase 6)**: After Foundational；与 US1/US2 工具文件无强依赖，可并行
- **US5 (Phase 7)**: After Foundational；与 US4 弱相关（报告数据）但可独立 mock
- **US6 (Phase 8)**: After Foundational；最好在 US1–US5 意图路由就位后完善
- **Polish (Phase 9)**: After desired stories complete

### User Story Dependencies

| Story | Depends on | Independently testable? |
|-------|------------|-------------------------|
| US1 | Phase 2 | Yes — create_job only |
| US2 | Phase 2 (+ matcher/time) | Yes — status/fields with seeded jobs |
| US3 | Phase 2 | Yes — query with seeded jobs |
| US4 | Phase 2 | Yes — interview APIs + mock LLM score |
| US5 | Phase 2 | Yes — seeded reports/profile |
| US6 | Phase 2 | Yes — meta paths；复合意图需 US1+US3 更完整 |

### Parallel Opportunities

- T002–T006 (setup stubs) in parallel
- T007–T010 (foundation tests) in parallel
- T012–T014 (confirmations/formatter/metrics) in parallel after T011 starts
- T028–T032 (US2 tests) in parallel
- T033–T034 (time_parser / job_matcher) in parallel
- T053–T055 (US5 tools) in parallel
- After Phase 2: US3 / US4 / US5 can proceed on separate files while US1/US2 stabilize orchestrator

---

## Parallel Example: User Story 2

```bash
# Tests in parallel:
Task: "time_parser tests in backend/tests/unit/agent/conversation/test_time_parser.py"
Task: "job_matcher tests in backend/tests/unit/agent/conversation/test_job_matcher.py"
Task: "update_status/fields tool tests under tools/"

# Implementations in parallel after tests fail:
Task: "time_parser.py"
Task: "job_matcher.py"
```

---

## Parallel Example: User Story 4

```bash
Task: "mutex tests + mutex.py"
Task: "adapter tests + adapter.py"
Task: "E2E mock-interview.spec.ts skeleton assertions"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL)
3. Complete Phase 3: US1
4. **STOP and VALIDATE**: `parse-intent` + `simulate-chat` create_job + E2E create-job
5. Demo MVP

### Incremental Delivery

1. Setup + Foundational → runtime ready
2. US1 → MVP 新增岗位
3. US2 → 状态/元数据写入
4. US3 → 查询
5. US4 → 微信模拟面试
6. US5 → 报告/画像
7. US6 → 帮助与纠错
8. Polish → quickstart + SC-009 E2E 全绿

### Parallel Team Strategy

1. Team finishes Phase 1–2 together
2. Dev A: US1 → US2；Dev B: US4；Dev C: US3+US5；再汇合 US6 + Polish

---

## Notes

- [P] = different files, no incomplete-task dependency
- [Story] labels map to spec user stories US1–US6
- Write tools MUST go through confirmation (`awaiting_confirmation`) — SC-005
- Interview uses shared LangGraph checkpoint — do not fork a WeChat-only scoring graph
- Relative times: always `Asia/Shanghai`
- Commit after each task or logical group; stop at checkpoints to validate independently
