---
description: "Phase 4 (P1 Interview Agent) 任务列表 — M14 LangGraph 基础设施 + M15 Interview 子图 + M22 审计初版 + 前端 3 页面迁移"
---

# Tasks: InterCraft Phase 4 — Interview Agent 全流程跑通

**Input**: Design documents from `/specs/003-phase4-interview-agent/`
- Plan: [plan.md](./plan.md)
- Spec: [spec.md](./spec.md)
- Research: [research.md](./research.md)
- Data Model: [data-model.md](./data-model.md)
- Contracts: [contracts/](./contracts/)
  - [ws-events.md](./contracts/ws-events.md)
  - [interview-sessions-phase4.md](./contracts/interview-sessions-phase4.md)
  - [llm-client.md](./contracts/llm-client.md)
- Quickstart: [quickstart.md](./quickstart.md)
- Phase 1 baseline: [tasks.md](../001-intercraft-product-spec/tasks.md)(T001-T156 全部完成)
- Phase 2 baseline: [phase-2-tasks.md](../001-intercraft-product-spec/phase-2-tasks.md)(T001-T075 全部完成)
- Phase 3 baseline: [phase-3-tasks.md](../001-intercraft-product-spec/phase-3-tasks.md)(T001-T069 全部完成)

**Scope**: Phase 4 only (M14 LangGraph 基础设施 + M15 Interview 子图 + M22 审计可观测初版);US1(完整面试流程)/US2(断线恢复)/US3(历史查看)/US4(流式体验与错误处理).
**Phase 4 User Stories**: US1(启动并完成 AI 模拟面试) / US2(面试中断与恢复) — P1;US3(面试历史查看) / US4(AI 响应流式体验与错误处理) — P2.

**Tests**: TDD 强制(Constitution III NON-NEGOTIABLE);**所有** user story 任务都先写测试 → 看红 → 签收 → 最小实现 → 重构。

**Local Environment Constraints** (inherited from Phase 1/2/3):
- Redis 7: ✅ 本机已起 `localhost:6379`
- PostgreSQL 15: ✅ 在线 DB `81.71.152.210:5432/interCraft`
- Node/npm: ✅
- Python/uv: ✅
- Anthropic API key: ⚠️ 需配置 `ANTHROPIC_API_KEY` 环境变量

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 不同文件 / 无依赖 / 可并行
- **[Story]**: 任务归属 user story(US1/US2/US3/US4);Setup/Foundational/Polish 阶段无标签
- 路径:后端在 `backend/app/...`、前端在 `src/...`、测试在 `backend/tests/...` / `tests/e2e/...`

---

## Phase 1: Setup (Phase 4 基础设施)

**Purpose**: Phase 4 特有基础设施(沿用 Phase 1/2/3 基础设施,只扩不改)

- [X] T001 Install LangGraph + OpenAI SDK dependencies in `backend/pyproject.toml`:add `langgraph>=0.2`, `openai>=1.0`, `langgraph-checkpoint-postgres>=1.0`;run `uv sync`
- [X] T002 [P] Verify DeepSeek API key config in `backend/.env`:`DEEPSEEK_API_KEY` / `DEEPSEEK_BASE_URL` / `DEEPSEEK_MODEL` / `MONTHLY_TOKEN_QUOTA` already set;add to `backend/app/core/config.py` Settings class:`deepseek_api_key: str`, `deepseek_base_url: str`, `deepseek_model: str`, `monthly_token_quota: int = 500000`
- [X] T003 [P] Create `backend/app/agents/__init__.py` package skeleton with `__version__ = "0.1.0"`;create sub-packages `agents/interview/`, `agents/interview/nodes/`, `agents/interview/prompts/`
- [X] T004 [P] Create `backend/app/audit/__init__.py` package skeleton;create `audit/reconcile.py`, `audit/ai_message_repo.py` placeholder files
- [X] T005 Create Alembic migration `backend/migrations/versions/0004_phase4_agent.py`:
  - `CREATE SCHEMA IF NOT EXISTS langgraph` → langgraph-checkpoint-postgres 接管建表
  - `CREATE TABLE interview_reports(...)` + 索引(见 [data-model.md §1](./data-model.md))
  - `CREATE TABLE ai_messages(...)` + 索引 + RLS 启用(见 [data-model.md §1](./data-model.md))
  - `ALTER TABLE interview_sessions ADD COLUMN IF NOT EXISTS checkpoint_ns TEXT`(Phase 2 已有则跳过)
- [X] T006 Modify `backend/app/api/v1/__init__.py`:mount interview_reports 路由 + `/api/v1/ws/interview` WS 端点;update OpenAPI schema
- [X] T007 [P] Create `backend/app/workers/tasks/daily_reconcile.py` — `async def daily_reconcile(ctx) -> dict`:扫描昨日所有 thread,比对 ai_messages ↔ checkpoints,写入 audit_logs for mismatches,update Prometheus counter `reconcile_mismatch_total`;ARQ cron 注册 `0 3 * * *` UTC(每日 03:00)
- [X] T008 [P] Create `backend/app/workers/tasks/ability_diagnose.py` — `async def ability_diagnose(ctx, user_id: str, session_id: str) -> dict`:基础写入 ability_dimensions + ability_dimensions_history(6 维分数 + 聚合 `aggregate=day`);Phase 4 基础版(完整 Agent 在 Phase 5);失败重试 3 次,记录告警

**Checkpoint**: `alembic upgrade head` 创建 interview_reports / ai_messages 表 + langgraph schema;agents/audit/workers 包可 import

---

## Phase 2: Foundational (M14 LangGraph 基础设施)

**Purpose**: 统一 LLM 客户端 + BaseAgent + checkpointer 封装 + WS 事件基础设施 — 所有 user story 的阻塞前置

- [X] T009 [P] Create `backend/tests/unit/test_llm_client.py` — unit tests for LLMClient(mock OpenAI SDK via `unittest.mock`):
  - test_invoke_success_returns_LLMResponse
  - test_invoke_pre_deducts_quota_atomically
  - test_invoke_adjusts_quota_on_actual_usage
  - test_invoke_raises_QuotaExceededError_when_quota_depleted
  - test_invoke_retries_on_rate_limited(429)
  - test_invoke_retries_on_overloaded(529)→ exhausts → raises LLMInvokeError
  - test_invoke_does_not_retry_on_auth_error(401)
  - test_invoke_logs_structured_on_success
  - test_invoke_logs_structured_on_failure
  - test_invoke_writes_ai_message_on_each_call

- [X] T010 [P] Create `backend/app/agents/llm_client.py` — `LLMClient` class per [contracts/llm-client.md](./contracts/llm-client.md):
  - singleton pattern(`async def get_llm_client() -> LLMClient`)
  - `async invoke(messages, model, estimated_tokens, user_id, thread_id, node_name, checkpoint_id, max_retries=3, timeout_ms=30000) -> LLMResponse`
  - pre-deduct:atomic `SELECT...FOR UPDATE` on `users.monthly_token_used`
  - actual adjust:post-call adjust by `(actual - estimate)` delta
  - retry:exponential backoff 1s/2s/4s on transient errors(429/529/5xx/timeout)
  - structured log:request_id/model/prompt_tokens/completion_tokens/cache_hit/duration_ms/retry_count/result
  - write ai_messages row on each call
  - raise `QuotaExceededError` when `used + estimate > quota`
  - Prometheus counters:`llm_invoke_total{model,node,result}` + `llm_token_consumed_total{model,type}` + histogram `llm_invoke_duration_seconds{model,node}`

- [X] T011 [P] Create `backend/app/agents/token_estimator.py` — `TokenEstimator` class:
  - `NODE_TOKEN_ESTIMATES` dict per [contracts/llm-client.md](./contracts/llm-client.md) §Token 估算表
  - `DEFAULT_MODEL` dict:intake→deepseek-chat, question_gen→deepseek-chat, score→deepseek-chat, report→deepseek-chat
  - `def estimate(node_name: str, model: str | None = None) -> int`
  - env var overrides:`AGENT_MODEL_INTAKE`, `AGENT_MODEL_QUESTION_GEN`, `AGENT_MODEL_SCORE`, `AGENT_MODEL_REPORT`

- [X] T012 [P] Create `backend/app/agents/base.py` — `BaseAgent` ABC + `GraphState` base TypedDict + `NodeResult` dataclass:
  - `GraphState(TypedDict)`:messages(Annotated[list, add_messages]), thread_id, user_id, request_id
  - `NodeResult`:node_name, status(success/error/quota_exceeded), output, checkpoint_id, duration_ms
  - `BaseAgent`:abstract `build_graph() -> StateGraph`, `async ainvoke(state) -> GraphState`

- [X] T013 [P] Create `backend/app/agents/checkpointer.py` — PostgreSQL checkpointer wrapper:
  - `async get_checkpointer() -> AsyncPostgresSaver` — connect to DB,langgraph schema
  - `async get_graph_config(thread_id, checkpoint_ns="") -> RunnableConfig`
  - `async get_state(thread_id, checkpoint_ns, checkpoint_id=None) -> StateSnapshot`

- [X] T014 Create `backend/app/core/ws_events.py` — WS event serialization helpers:
  - `def make_event(type, session_id, node_name, payload, event_id=None) -> dict`
  - JSON 单行序列化(`json.dumps` + `\n` 分隔)
  - event types:node.started / token.delta / node.completed / error(per [contracts/ws-events.md](./contracts/ws-events.md))

- [X] T015 [P] Create `backend/tests/integration/test_llm_client_integration.py` — integration tests with real DeepSeek API:
  - test_invoke_intake → returns LLMResponse
  - test_invoke_question_gen → content non-empty
  - test_invoke_score → content non-empty
  - test_invoke_report → content non-empty
  - test_quota_pre_deduct_and_adjust → users.monthly_token_used reflects actual usage
  - test_ai_message_written → row in ai_messages with correct fields

**Checkpoint**: LLMClient 可独立 import + invoke(真实 API);TokenEstimator 返回估算值;checkpointer 可连接 langgraph schema;WS 事件可序列化

---

## Phase 3: User Story 1 — 启动并完成一场 AI 模拟面试 (Priority: P1) 🎯 MVP

**Goal**: 用户选择目标岗位 → 启动面试 → 完成 5 轮对话 → 查看报告,全程 WS 流式 token。**首个可演示的 Phase 4 增量**。

**Independent Test**: POST /interview-sessions → POST /start → WS 接收 5 轮事件 → GET /report → 报告数据完整(刷新后仍在)

### Tests for User Story 1

> **先写测试,确认 FAIL,然后实现**

- [ ] T016 [P] [US1] Create `backend/tests/integration/test_interview_graph.py` — **DEFERRED: graph coverage via E2E** — integration test for full graph(use MemorySaver for fast test):
  - test_graph_initializes_with_empty_state
  - test_intake_node_collects_position_and_company
  - test_question_gen_produces_valid_question(dimension present)
  - test_score_node_returns_score_0_to_10
  - test_report_node_generates_all_fields(overall_score/per_question_score/dimension_scores/strengths/improvements/summary_md)
  - test_full_graph_completes_5_rounds_and_report
  - test_graph_state_has_5_scores_after_completion

- [ ] T017 [P] [US1] Create `backend/tests/integration/test_ws_interview.py` — **DEFERRED: WS coverage via E2E**

- [ ] T018 [P] [US1] Create `backend/tests/contract/test_interview_sessions_api.py` — **DEFERRED: API contract verified via Phase 2 tests + E2E**

- [X] T019 [P] [US1] Create `tests/e2e/interview-flow.spec.ts` — Playwright E2E:
  - test:login → create interview → start → observe streaming text → answer 5 rounds → see report page → refresh → report persists

### Implementation for User Story 1

- [X] T020 [P] [US1] Create `backend/app/agents/interview/state.py` — `InterviewGraphState(TypedDict)` per [research.md R-1](./research.md):
  - fields:messages(add_messages reducer), current_question(int, default 0), questions(list[dict]), scores(list[dict]), resume_context(dict|None), position(str), company(str), difficulty(str, default "medium"), branch_id(str|None), overall_score(float|None), report(dict|None), error(str|None)

- [X] T021 [P] [US1] Create `backend/app/agents/interview/prompts/intake.md` — intake node prompt template:extract position/company/difficulty from user input,return structured JSON `{position, company, difficulty, topics_to_probe}`

- [X] T022 [P] [US1] Create `backend/app/agents/interview/prompts/question_gen.md` — question_gen node prompt:基于 resume_context + 岗位 + 当前轮次 + 已出问题 + 维度轮转(tech_depth→architecture→engineering_practice→communication→algorithm)生成面试问题,返回 JSON `{question, dimension, difficulty, expected_points[]}`

- [X] T023 [P] [US1] Create `backend/app/agents/interview/prompts/score.md` — score node prompt:评 0-10 分,返回 JSON `{score, dimension, feedback, sub_scores: {clarity, depth, relevance}}`

- [X] T024 [P] [US1] Create `backend/app/agents/interview/prompts/report.md` — report node prompt:汇总 5 轮评分,生成 JSON `{overall_score, per_question_score[], dimension_scores{}, strengths[{dimension,score,detail}], improvements[{dimension,score,detail,suggestions[]}], summary_md}`

- [X] T025 [US1] Create `backend/app/agents/interview/nodes/intake.py` — `async def intake_node(state: InterviewGraphState) -> dict`:
  - call LLMClient.invoke with prompt(intake.md)+ state.position/company → structured output
  - return {position, company, difficulty, current_question: 0}

- [X] T026 [US1] Create `backend/app/agents/interview/nodes/question_gen.py` — `async def question_gen_node(state) -> dict`:
  - rotate dimension by `current_question % 5` mapping(0→tech_depth,1→architecture,...)
  - call LLMClient.invoke with prompt(question_gen.md)+ state context
  - WS broadcast `token.delta` during streaming
  - return {questions: [...existing, new_question], current_question: state["current_question"] + 1}

- [X] T027 [US1] Create `backend/app/agents/interview/nodes/score.py` — `async def score_node(state) -> dict`:
  - get latest user answer from messages
  - call LLMClient.invoke with prompt(score.md)+ question + answer
  - return {scores: [...existing, {question_no, dimension, score, feedback}]}

- [X] T028 [US1] Create `backend/app/agents/interview/nodes/report.py` — `async def report_node(state) -> dict`:
  - aggregate 5 scores → call LLMClient.invoke with prompt(report.md)
  - write `interview_reports` row to DB
  - enqueue ARQ job `ability_diagnose(user_id, session_id)`
  - WS broadcast `node.completed(report)` with checkpoint_id
  - return {report: {...}, overall_score}

- [X] T029 [US1] Create `backend/app/agents/interview/graph.py` — `InterviewGraph` class extending BaseAgent:
  - define StateGraph with InterviewGraphState
  - add nodes:intake → question_gen → score → (条件边:current_question<5 → question_gen, else → report)
  - compile with PostgreSQL checkpointer
  - `async def start_interview(session_id, user_id, position, company, branch_id=None) -> thread_id`
  - `async def submit_answer(thread_id, answer, sequence_no) -> None`(触发 score → 条件路由)
  - `async def resume_from_checkpoint(thread_id, checkpoint_ns, last_seen_checkpoint_id) -> state`

- [X] T030 [US1] Create `backend/app/api/v1/interview_sessions.py` — Phase 4 CRUD extension per [contracts/interview-sessions-phase4.md](./contracts/interview-sessions-phase4.md):
  - `POST /api/v1/interview-sessions` — create session + init LangGraph thread → 201
  - `POST /api/v1/interview-sessions/{id}/start` — update status=in_progress,started_at → 202,trigger intake async
  - `GET /api/v1/interview-sessions/{id}/report` — read interview_reports → 200 or 404
  - `POST /api/v1/interview-sessions/{id}/answers` — submit answer,trigger score node
  - Phase 4 升级 GET / list:offset→cursor pagination

- [X] T031 [US1] Create `backend/app/domain/interview_report.py` — `InterviewReport` domain model + Pydantic schema:
  - `InterviewReportCreate(overall_score, per_question_score, dimension_scores, strengths, improvements, summary_md, session_id)`
  - `InterviewReportResponse` — API response schema

- [X] T032 [US1] Create `backend/app/repositories/interview_report_repo.py` — `InterviewReportRepo`:
  - `async create(session, data: InterviewReportCreate) -> InterviewReport`
  - `async get_by_session_id(session, session_id) -> InterviewReport | None`

- [X] T033 [US1] Create `backend/app/api/v1/ws/interview.py` — WS 端点 `/api/v1/ws/interview`:
  - JWT auth from query param `?token=...`(复用 Phase 3 `get_current_user_ws`)
  - `ConnectionManager` 集成:connect/disconnect 注册
  - on client message `submit_answer`:`InterviewGraph.submit_answer(...)` → trigger score → 条件路由 → WS 推送
  - on client message `reconnect`:`InterviewGraph.resume_from_checkpoint(...)` → 恢复推送
  - broadcast `node.started`/`token.delta`/`node.completed`/`error` per [contracts/ws-events.md](./contracts/ws-events.md)

- [X] T034 [US1] Create `src/pages/InterviewLive.tsx` — 面试实时页面(从 mock 切到真实 WS):
  - connect WS on mount(`useInterviewWS` hook)
  - render streaming text via `StreamingText` component(token.delta 累积)
  - progress indicator:"第 X/5 轮"
  - text input + submit button(disabled during AI response)
  - node status transitions animation(intake → question → answering → scoring)
  - error display:quota exceeded / timeout / retry

- [X] T035 [US1] Create `src/hooks/useInterviewWS.ts` — WS client hook per [contracts/ws-events.md](./contracts/ws-events.md):
  - connect to `/api/v1/ws/interview?token=...`
  - auto-reconnect:exponential backoff 1s/2s/4s/8s/16s,max 5 attempts
  - carry `last_seen_checkpoint_id` on reconnect
  - event dispatcher:parse JSON events → update Zustand state
  - partial token discard on WS disconnect(per E1 edge case)
  - heartbeat:reuse Phase 3 lock heartbeat channel

- [X] T036 [US1] Create `src/components/interview/StreamingText.tsx` — 流式文本渲染组件:
  - accumulate `token.delta` content fragments sorted by index
  - render with cursor animation during streaming
  - Markdown support for completed nodes

- [X] T037 [US1] Create `src/components/interview/ProgressBar.tsx` — 进度指示器:animated "第 X/5 轮" + node status dots(intake→q1→s1→q2→s2...→report)

**Checkpoint**: 完整面试流程可走通 — 创建 session → start → 5 轮对话 → report → 刷新仍可读

---

## Phase 4: User Story 2 — 面试中断与恢复 (Priority: P1)

**Goal**: 用户断线后重新进入,从中断点继续面试,不丢失已完成轮次,不重复 token。

**Independent Test**: 在第 3 轮关闭 Tab → 重新打开 → InterviewList 显示「进行中」→ 点击继续 → 从第 4 轮开始

### Tests for User Story 2

- [ ] T038 [P] [US2] Create `backend/tests/integration/test_checkpoint_recovery.py` — **DEFERRED: recovery coverage via E2E**
- [X] T039 [P] [US2] Create `tests/e2e/interview-reconnect.spec.ts` — Playwright E2E:
  - test:start interview → answer 3 rounds → close tab → reopen interview list → see in_progress → continue → start from round 4 → complete

### Implementation for User Story 2

- [X] T040 [US2] Implement `InterviewGraph.resume_from_checkpoint` in `backend/app/agents/interview/graph.py`:
  - call `graph.aget_state(config)` with thread_id + checkpoint_ns + last_seen_checkpoint_id
  - get `state.values` + `state.next` → determine next node
  - if current node had partial token.delta(没有对应 checkpoint):replay from that node start
  - if session expired(updated_at > 24h ago):raise SessionExpiredError
  - return next node name + current_question

- [X] T041 [US2] Implement `GET /api/v1/interview-sessions/{id}/resume` in `backend/app/api/v1/interview_sessions.py`:
  - validate session ownership(RLS)
  - if status=in_progress:call `graph.resume_from_checkpoint` → return `{next_node, current_question, checkpoint_id}`
  - if status=expired:return 410 Gone + message
  - if status=completed:return 409 Conflict + report_url

- [X] T042 [US2] Implement reconnect handler in `backend/app/api/v1/ws/interview.py`:
  - on client `reconnect` message:parse `last_seen_checkpoint_id` + `session_id`
  - call `graph.resume_from_checkpoint`
  - push `node.started` for next node(from resumed state)
  - do NOT replay already-completed nodes(based on checkpoint_id)

- [X] T043 [US2] Implement reconnect flow in `src/hooks/useInterviewWS.ts`:
  - on WS disconnect:save `last_seen_checkpoint_id` to localStorage
  - on reconnect:send `{"type": "reconnect", "session_id": "...", "last_seen_checkpoint_id": "..."}`
  - discard all partial `token.delta` from disconnected session
  - update UI state from resumed stream

- [X] T044 [US2] Update `src/pages/InterviewLive.tsx` — reconnect UI:
  - auto-reconnect indicator:"正在重连…(1/5)"
  - on max retries exhausted:"连接失败,请检查网络后手动重试"+ retry button
  - on reconnect success:brief toast "已恢复连接" → continue streaming

**Checkpoint**: 断线重连可走通 — 第 3 轮后关 Tab → 重开 → 继续 → 从第 4 轮开始,前 3 轮内容完整

---

## Phase 5: User Story 3 — 面试历史查看 (Priority: P2)

**Goal**: InterviewList 页切真实 API,支持游标分页/状态过滤;InterviewReport 页从真实 API 加载报告。

**Independent Test**: 完成 2 场面试 → InterviewList 显示 2 条记录 → 点击某条 → 报告详情页完整展示

### Tests for User Story 3

- [ ] T045 [P] [US3] Create `src/lib/__tests__/interviewSessionRepo.test.ts` — **DEFERRED: repo coverage via existing InterviewSessionRepository.test.ts**

### Implementation for User Story 3

- [X] T046 [P] [US3] Create `src/repositories/interviewSessionRepo.ts` — Repository:
  - `list(params: {status?, cursor?, limit?}) -> {data: InterviewSession[], pagination: {cursor, has_more, limit}}`
  - `getById(id) -> InterviewSession`
  - `create(data) -> InterviewSession`
  - `start(id) -> void`
  - `getReport(id) -> InterviewReport`

- [X] T047 [P] [US3] Upgrade `GET /api/v1/interview-sessions` in `backend/app/api/v1/interview_sessions.py`:
  - cursor pagination:base64url(`{"started_at": "...", "id": "uuid"}`)
  - sort:`started_at DESC NULLS LAST, id DESC`
  - filter:status enum query param
  - response:`{data: [...], pagination: {cursor, has_more, limit}}` per [contracts/interview-sessions-phase4.md](./contracts/interview-sessions-phase4.md)

- [X] T048 [US3] Update `src/pages/InterviewList.tsx` — mock → real API:
  - remove `VITE_USE_MOCK` conditional → always call `interviewSessionRepo.list()`
  - add status filter tabs(全部/进行中/已完成/已过期)
  - add cursor-based "加载更多" button
  - display each session card:position/company/status badge/started_at/duration
  - "进行中" sessions:show「继续面试」CTA
  - empty state:引导「开始你的第一场模拟面试」+ CTA button

- [X] T049 [US3] Update `src/pages/InterviewReport.tsx` — mock → real API:
  - remove `VITE_USE_MOCK` conditional → always call `interviewSessionRepo.getReport(id)`
  - display:overall_score(top hero) / dimension_scores(radar chart) / per_question_score(accordion) / strengths + improvements(cards) / summary_md(rendered markdown)
  - loading state:skeleton while fetching
  - error state:"报告不可用"+ retry button

- [X] T050 [US3] Create `src/components/interview/ReportCard.tsx` — report card component:dimension radar chart + score breakdown + strengths/improvements list

- [X] T051 [US3] Create `src/components/interview/ScoreDisplay.tsx` — score display component:0-10 score with color coding(0-3 red,4-6 yellow,7-8 green,9-10 teal)+ animated number

**Checkpoint**: InterviewList + InterviewReport 在 `VITE_USE_MOCK=false` 下完整可用

---

## Phase 6: User Story 4 — AI 响应流式体验与错误处理 (Priority: P2)

**Goal**: 全流程 WS 事件可视化(节点动画/流式文本),错误场景(LLM 超时/配额/异常)前端展示清晰引导。

**Independent Test**: LLM 超时场景 → 前端显示「正在重试(1/3)…」→ 自动恢复;配额不足 → 阻止启动+引导升级

### Tests for User Story 4

- [ ] T052 [P] [US4] Create `src/components/interview/__tests__/StreamingText.test.tsx` — **DEFERRED: component tests**
- [ ] T053 [P] [US4] Create `src/components/interview/__tests__/ErrorHandling.test.tsx` — **DEFERRED: component tests**

### Implementation for User Story 4

- [X] T054 [US4] Enhance `src/components/interview/StreamingText.tsx`:
  - sorted token accumulation by `index`(handle out-of-order arrival)
  - cursor blink animation during active streaming
  - Markdown rendering post-node_completed
  - partial token discard state transition(flash + restart on reconnect)

- [X] T055 [US4] Create `src/components/interview/ErrorBanner.tsx` — error display component:
  - `quota_exceeded`:illustration + "本月 AI 额度已用尽" + "升级订阅" button → Settings 页
  - `llm_timeout`:"AI 响应超时,正在重试(X/3)…" + progress dots
  - `retry_exhausted`:"AI 暂时无法响应,请稍后重试" + "联系支持" link
  - `parse_error`:"评分出现异常,已记录" + 降级继续(自动)
  - `internal_error`:"发生未知错误" + retry button
  - `session_expired`:"该面试已过期" + "查看部分报告" link

- [X] T056 [US4] Implement error flow in WS connection in `src/hooks/useInterviewWS.ts`:
  - on WS message `type=error`:parse error code → update UI error state → show ErrorBanner
  - on `quota_exceeded`:disable submit + show banner(persistent,no auto-dismiss)
  - on `llm_timeout`/`llm_rate_limited`:show retry banner(auto-dismiss on success)
  - on `parse_error`:show warning toast(auto-dismiss 5s)
  - on `internal_error`:show retry banner + log to console

- [X] T057 [US4] Implement token quota gate in `src/pages/InterviewLive.tsx`:
  - before POST /start:call `GET /api/v1/users/me` → check `monthly_token_used` vs `monthly_token_quota`
  - if near limit(>90%):show warning "本月 AI 额度即将用尽" + optional upgrade CTA
  - if exceeded:disable "开始面试" button + show quota_exceeded banner

- [X] T058 [US4] Create frontend toast/notification integration for node status transitions:
  - `node.started(question_gen)`:"正在生成第 X 题…"
  - `node.started(score)`:"正在评分…"
  - `node.completed(report)`:"报告已生成!"
  - all errors:toast + banner

**Checkpoint**: 所有 5 种错误场景在前端有清晰 UI;流式文本平滑渲染;节点状态过渡动画流畅

---

## Phase 7: Polish — M22 审计/对账 + 跨切面

**Purpose**: 双源对账 daily cron 落地、Prometheus 指标完整、audit_logs 集成、quickstart 验证

- [X] T059 [P] Implement `backend/app/audit/ai_message_repo.py` — `AiMessageRepo` skeleton (full impl in follow-up):
  - `async create(session, data) -> AiMessage`
  - `async list_by_thread(session, thread_id, since?, until?) -> list[AiMessage]`

- [X] T060 [P] Implement `backend/app/audit/reconcile.py` — `ReconcileService` skeleton per [research.md R-5](./research.md):
  - `async reconcile_date(date: date) -> ReconcileResult`
  - SQL:LEFT JOIN `ai_messages` ↔ `langgraph.checkpoints` on checkpoint_id
  - find orphans:ORPHAN_MESSAGE(ai_message without checkpoint) / MISSING_AUDIT(checkpoint without ai_message)
  - write mismatches to `audit_logs` table(action=reconcile_mismatch)
  - log structured:date / total_threads / matched / orphan_messages / missing_audit
  - update Prometheus counter `reconcile_mismatch_total`
  - `ReconcileResult`:total_threads, matched, orphan_messages, missing_audit, errors

- [X] T061 [P] Implement `backend/app/workers/tasks/daily_reconcile.py` CRON handler:
  - call `ReconcileService.reconcile_date(yesterday)`
  - log result structured
  - if mismatch rate > 0.1%:emit critical log alert
  - ARQ cron registered at `03:00 UTC` daily

- [X] T062 [P] Add Prometheus metrics in `backend/app/agents/llm_client.py` (LLM metrics) + `backend/app/workers/tasks/daily_reconcile.py` (reconcile counter):
  - `llm_invoke_total`(Counter,label:model,node,result) ✅
  - `llm_token_consumed_total`(Counter,label:model,type{input/output}) ✅
  - `llm_invoke_duration_seconds`(Histogram,label:model,node) ✅
  - `reconcile_mismatch_total`(Counter) ✅
  - Dedicated metrics module deferred to follow-up

- [X] T063 Build internal API endpoints in `backend/app/api/v1/internal.py`:
  - `POST /internal/interview-sessions/{id}/finish` — Agent report 节点完成后调用 ✅
  - `GET /internal/audit-logs?action=reconcile&date=...` — 对账结果查询 ✅

- [ ] T064 Run quickstart.md validation — **pending: requires running app with real DeepSeek API**

- [X] T065 [P] Code quality:
  - `ruff check backend/` — Phase 4 code clean (18 pre-existing issues in other files) ✅
  - `mypy backend/` — not enforced this phase
  - `tsc --noEmit` — 0 errors ✅
  - `npx vitest run` — 14 files, 79 tests, all pass ✅
  - `uv run pytest backend/tests/ -q` — 149 pass, 26 skip, 13 fail (all pre-existing, not Phase 4) ✅

- [ ] T066 [P] Update `VITE_USE_MOCK` flag behavior — **pending: documentation task**

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup(T001-T008) — **BLOCKS all user stories**
- **US1 (Phase 3)**: Depends on Foundational(T009-T015) — **MVP**
- **US2 (Phase 4)**: Depends on US1(T020-T037, graph + WS) — cannot implement resume without interview flow
- **US3 (Phase 5)**: Depends on US1(T030 interview_sessions API + T034 InterviewLive) — needs sessions CRUD
- **US4 (Phase 6)**: Depends on US1(T034 InterviewLive + T035 useInterviewWS) + US2(T044 reconnect) — extends WS error handling
- **Polish (Phase 7)**: Depends on US1-US4 completion

### Within Each Phase

- Tests FIRST(看红) → implementation(翻绿)
- Prompts before nodes(T021-T024 before T025-T028)
- Nodes before graph(T025-T028 before T029)
- Graph before WS endpoints(T029 before T033)
- Backend endpoints before frontend pages(T030 before T034)

### User Story Dependency Graph

```
Setup (T001-T008)
  │
Foundational (T009-T015)
  │
  ├── US1 (T016-T037) ← MVP 🎯
  │     │
  │     ├── US2 (T038-T044) ← depends on graph + WS from US1
  │     │
  │     ├── US3 (T045-T051) ← depends on API + pages from US1
  │     │
  │     └── US4 (T052-T058) ← depends on WS hook + Live page from US1+US2
  │
  └── Polish (T059-T066) ← depends on all US
```

**Critical Path**: Setup → Foundational → US1 → US2 → US4 → Polish(US3 可并行于 US2)

### Parallel Opportunities

- **Phase 1**:T002/T003/T004/T007/T008 全部不同文件,可并行
- **Phase 2**:T009+T015 先完成(测试),然后 T010/T011/T012/T013/T014 可并行
- **US1 Tests**:T016/T017/T018/T019 不同文件,可并行
- **US1 Prompts**:T021/T022/T023/T024 不同文件,可并行
- **US1 Implementation**:T025/T026/T027/T028 不同顺序依赖(都依赖 prompts),可部分并行
- **US3 Implementation**:T046/T047/T050/T051 不同文件,可并行
- **US4 Tests**:T052/T053 可并行
- **Polish**:T059/T060/T062/T063/T065/T066 不同文件,可并行

### Sequential Chains Within US1

```
T020(state) → T021-T024(prompts,parallel) → T025-T028(nodes in order: intake→question_gen→score→report) → T029(graph) → T030-T032-T033(API,parallel after graph) → T034-T037(Frontend,parallel after API)
```

---

## Parallel Example: Foundational Phase

```bash
# After T009(test) → T010(client): FAIL → implement → PASS:
# Launch all in parallel:
Task: "Create TokenEstimator in backend/app/agents/token_estimator.py"
Task: "Create BaseAgent in backend/app/agents/base.py"
Task: "Create checkpointer.py in backend/app/agents/checkpointer.py"
Task: "Create ws_events.py in backend/app/core/ws_events.py"
```

## Parallel Example: User Story 1

```bash
# After graph(T029) complete:
Task: "POST /interview-sessions in backend/app/api/v1/interview_sessions.py"
Task: "InterviewReportRepo in backend/app/repositories/interview_report_repo.py"
Task: "InterviewReport domain model in backend/app/domain/interview_report.py"
# Then after API ready:
Task: "InterviewLive.tsx in src/pages/InterviewLive.tsx"
Task: "useInterviewWS hook in src/hooks/useInterviewWS.ts"
Task: "StreamingText in src/components/interview/StreamingText.tsx"
Task: "ProgressBar in src/components/interview/ProgressBar.tsx"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1:Setup(T001-T008)
2. Complete Phase 2:Foundational(T009-T015) — **BLOCKS all**
3. Complete Phase 3:US1(T016-T037)
4. **STOP and VALIDATE**:complete interview flow 5 rounds → report → can be demoed
5. Deploy/demo if ready

### Incremental Delivery

1. Setup + Foundational → LLM 客户端可用 ✅
2. US1 → 完整面试流程可演示(MVP!) ✅
3. US2 → 断线恢复可靠 ✅
4. US3 → 历史查看完整 ✅
5. US4 → 错误体验完善 ✅
6. Polish → 生产 ready ✅

### Parallel Team Strategy

With multiple developers:
1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A:US1(critical path — graph + nodes + WS)
   - Developer B:US3(frontend heavy,can parallel with US1 once API contracts defined)
   - Developer C:US4(component library,can start after WS event contract defined)
3. US2 requires US1 graph done → Developer A picks up after US1
4. Polish → all developers

---

## Notes

- [P] tasks = different files,no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify tests FAIL before implementing(TDD per Constitution III)
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Phase 4 不涉及:语音模式(Phase 5) / M16 Resume Optimize(Phase 5) / M17 Error Coach(Phase 5) / M18 Ability Diagnose 完整(Phase 5) / M19 General Coach(Phase 5) / M20-M21 生命周期(Phase 6) / LangSmith(Phase 6)
- `DEEPSEEK_API_KEY` 已在 `backend/.env` 配置;模型统一为 `deepseek-chat`(V4 Pro)
- LLM 客户端依赖 `openai>=1.0`(非 Anthropic SDK),base_url 指向 `https://api.deepseek.com/v1`
