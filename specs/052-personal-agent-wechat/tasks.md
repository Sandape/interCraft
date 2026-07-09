# Tasks: Personal Agent + WeChat Channel

**Input**: Design documents from `/specs/052-personal-agent-wechat/`

**Prerequisites**: plan.md (✅), spec.md (✅), research.md (✅), data-model.md (✅), contracts/ (✅), quickstart.md (✅)

**Tests**: TDD per Constitution Principle III — test tasks precede implementation tasks. Tests are MANDATORY (non-negotiable).

**Organization**: Tasks grouped by user story for independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Backend module**: `backend/app/modules/agent/` (business logic), `backend/app/channels/` (iLink protocol)
- **Frontend pages**: `frontend/src/pages/`, `frontend/src/components/agent/`
- **Backend tests**: `backend/tests/unit/`, `backend/tests/integration/`
- **E2E tests**: `tests/e2e/agent-wechat/`
- **Migrations**: `backend/migrations/versions/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Database migration and project scaffolding — prerequisites for all phases

- [x] T001 Create Alembic migration `0023_agent_tables.py` for 6 new tables (`agents`, `wechat_credentials`, `wechat_bindings`, `agent_messages`, `agent_preferences`, `agent_status_history`) with all columns, indexes, and RLS policies per `data-model.md`
- [ ] T002 [P] Run migration and verify all 6 tables exist in PostgreSQL with correct schemas via `mcp__postgres__query`
- [ ] T003 [P] Create `backend/app/modules/agent/__init__.py` with module docstring and `backend/app/modules/agent/README.md`
- [ ] T004 [P] Create `backend/app/channels/__init__.py` with module docstring
- [ ] T005 [P] Create `backend/app/modules/agent/models.py` with all 6 SQLAlchemy ORM models (Agent, WeChatCredential, WeChatBinding, AgentMessage, AgentPreference, AgentStatusHistory) per `data-model.md`
- [ ] T006 [P] Install dependencies: `uv add httpx[http2] pycryptodome` and verify import in Python REPL

**Checkpoint**: Database schema ready, models defined — foundation for all subsequent phases

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: ILinkClient and core schemas that ALL user stories depend on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

### Tests for Foundational

- [ ] T007 [P] Unit test for `ILinkClient` HTTP methods (mock iLink API) in `backend/tests/unit/test_ilink_client.py` — test `get_bot_qrcode()`, `get_qrcode_status()`, `wait_for_login()`, `getupdates()`, `send_text()`, `make_headers()`
- [ ] T008 [P] Unit test for `split_text()` utility in `backend/tests/unit/test_ilink_utils.py` — test short text (no split), long text (multi-segment), Markdown code fence preservation, emoji boundary, URL boundary

### Implementation for Foundational

- [ ] T009 [P] Implement `backend/app/channels/ilink_utils.py` — `make_headers()` (AuthorizationType + X-WECHAT-UIN + Bearer), `aes_ecb_decrypt()` (3 key formats), `split_text()` (500-char chunks, Markdown fence-aware)
- [ ] T010 Implement `backend/app/channels/ilink_client.py` — `ILinkClient` class: `start()/stop()` (httpx.AsyncClient lifecycle), `_get()/_post()` (common helpers), `get_bot_qrcode()`, `get_qrcode_status()`, `wait_for_login()` (1.5s polling, 300s timeout), `getupdates()` (35s long-hold), `send_text()`, `sendmessage()`. Reference: CoPaw `D:\Project\CoPaw\src\copaw\app\channels\weixin\client.py`
- [ ] T011 [P] Implement `backend/app/modules/agent/schemas.py` — all Pydantic schemas per `contracts/agent-api.yaml`: `QrcodeResponse`, `QrcodeStatusResponse`, `BindingStatusResponse`, `AgentStatusResponse`, `AgentPreferencesResponse`, `PatchPreferencesRequest`, `SendMessageRequest`, `AgentAdminItem`, `AgentAdminListResponse`
- [ ] T012 [P] Implement `backend/app/modules/agent/repository.py` — `AgentRepository`, `WeChatCredentialRepository`, `WeChatBindingRepository`, `AgentMessageRepository`, `AgentPreferenceRepository`, `AgentStatusHistoryRepository`. Each with async SQLAlchemy methods (create/get/update/list) and RLS enforcement
- [ ] T013 Register agent API router in `backend/app/api/v1/__init__.py` — mount `agent.router` at `/api/v1/agent`

**Checkpoint**: ILinkClient ready, models + schemas + repositories defined — user story implementation can now begin

---

## Phase 3: User Story 1 — 扫码绑定微信 (Priority: P1) 🎯 MVP

**Goal**: User visits Agent settings page, scans QR code with WeChat, binding completes, agent activates

**Independent Test**: `GET /api/v1/agent/wechat/qrcode` → scan QR (mock) → poll status → `confirmed` → `GET /api/v1/agent/wechat/binding` returns `{bound: true, agent_status: "active"}`

### Tests for User Story 1

- [ ] T014 [P] [US1] Integration test for QR code binding flow in `backend/tests/integration/test_agent_api.py` — test `GET /qrcode` (returns direct `qrcode_url` + renderable `qrcode_image_url` + qrcode_token), `GET /qrcode/status` (waiting→scanned→confirmed→expired states), user_id binding verification, 403 on mismatched user_id
- [ ] T015 [P] [US1] Unit test for `AgentService.activate_on_bind()` in `backend/tests/unit/test_agent_service.py` — test agent creation on user registration, status transition dormant→active, duplicate wechat_uin rejection

### Implementation for User Story 1

- [ ] T016 [US1] Implement `backend/app/modules/agent/service.py` — `AgentService`: `auto_create_on_user_registration()` (called from existing user registration flow), `activate_on_bind(user_id, wechat_uin, bot_token)`, `deactivate_on_unbind(user_id)`, `get_agent_status(user_id)`. Agent auto-created in dormant state when user registers
- [ ] T017 [US1] Implement QR code binding endpoints in `backend/app/modules/agent/api.py`: `GET /api/v1/agent/wechat/qrcode` (authenticated, bind user_id to qrcode, return direct `qrcode_url` + renderable `qrcode_image_url` + qrcode_token), `GET /api/v1/agent/wechat/qrcode/status?qrcode_token=` (authenticated, verify user_id match, poll iLink status), `GET /api/v1/agent/wechat/binding` (return bound status + wechat_nickname), `DELETE /api/v1/agent/wechat/binding` (unbind, revoke credentials)
- [ ] T018 [US1] Implement `GET /api/v1/agent/status` endpoint — return agent status, wechat_bound flag, display_name, last_heartbeat_at, message counts
- [ ] T019 [US1] Add RLS policy for `agents`, `wechat_credentials`, `wechat_bindings` tables — `ALTER TABLE ... ENABLE ROW LEVEL SECURITY; CREATE POLICY ... USING (user_id = current_setting('app.user_id')::uuid)`
- [ ] T020 [P] [US1] Create frontend `frontend/src/repositories/AgentRepository.ts` — API client functions: `fetchQrcode()`, `pollQrcodeStatus()`, `fetchBindingStatus()`, `unbindWechat()`, `fetchAgentStatus()`
- [ ] T021 [P] [US1] Create frontend `frontend/src/hooks/queries/useAgent.ts` — React Query hooks: `useQrcode()`, `useQrcodeStatus(qrcodeToken)`, `useBindingStatus()`, `useAgentStatus()`, `useUnbindMutation()`
- [ ] T022 [US1] Create frontend `frontend/src/components/agent/QRBindCard.tsx` — QR code display (base64→img), polling status indicator (waiting→scanned→confirmed→expired), countdown timer (300s), refresh button on expired, success state showing wechat_nickname + avatar
- [ ] T023 [US1] Create frontend `frontend/src/pages/AgentSettings.tsx` — new page at `/agent`: QRBindCard (unbound state) / AgentStatusCard (bound state), sidebar navigation entry "Agent 助手"

**Checkpoint**: User can bind WeChat via QR code — agent activates. MVP ready!

---

## Phase 4: User Story 2 — Agent 发送消息到微信 (Priority: P1)

**Goal**: System can send text messages to user's WeChat via Agent, with long text auto-split

**Independent Test**: CLI `send-test-message <user_id> "Hello"` → user receives message in WeChat within 10s → verify in DB `agent_messages.status='sent'`

### Tests for User Story 2

- [ ] T024 [P] [US2] Unit test for message send flow in `backend/tests/unit/test_agent_messaging.py` — test INSERT pending → Redis LPUSH → send_text success → UPDATE sent; test send failure → retry 3x → status='failed'; test long message split (2000 chars → 4 segments)
- [ ] T025 [P] [US2] Integration test for message send API in `backend/tests/integration/test_agent_api.py` — test `POST /internal/send-message` returns 202, verify DB status 'pending'→'sent', verify content split into correct segments

### Implementation for User Story 2

- [ ] T026 [US2] Implement outbound message send pipeline in `backend/app/channels/message_handler.py` — `send_message(user_id, content, priority)`: (1) INSERT `agent_messages` with `status='pending'` (2) LPUSH to Redis `wechat:send_queue:{user_id}` (3) pop from Redis and call `ILinkClient.send_text()` (4) UPDATE `agent_messages.status='sent'` on success, `status='failed'` on failure after 3 retries
- [ ] T027 [US2] Implement `POST /api/v1/agent/internal/send-message` endpoint — accepts `{user_id, content, priority}`, returns 202 `{message_id, status: 'queued', segment_count}`
- [ ] T028 [US2] Implement message segment tracking — outbound messages > 500 chars split via `split_text()`, each segment INSERTed as separate `agent_messages` row with `segments_total` + `segment_index`, client_id groups them
- [ ] T029 [US2] Implement PG→Redis queue rebuild — on startup or Redis flush, scan `agent_messages WHERE status='pending' AND created_at > NOW() - INTERVAL '24 hours'` and re-populate Redis queues
- [ ] T030 [US2] Implement CLI command `send-test-message` in `backend/app/modules/agent/cli.py` — `python -m app.modules.agent.cli send-test-message <user_id> <text>`

**Checkpoint**: Agent can send messages to WeChat. System→User communication channel established.

---

## Phase 5: User Story 3 — 接收用户微信消息 (Priority: P1)

**Goal**: Agent receives user's WeChat messages via iLink long-poll, persists to DB with dedup

**Independent Test**: User sends text in WeChat → within 60s, message appears in `agent_messages` with `direction='inbound'`

### Tests for User Story 3

- [ ] T031 [P] [US3] Unit test for inbound message parsing in `backend/tests/unit/test_message_handler.py` — test text message (type=1) parsing, image message (type=2) with CDN download mock, voice message (type=3) ASR text extraction, dedup via context_token, message_type filtering (only type=1 processed)
- [ ] T032 [P] [US3] Unit test for `ILinkConnectionPool` in `backend/tests/unit/test_ilink_pool.py` — test pool startup (loads active creds from DB), add (spawns poll task), remove (cancels task), isolate (user A crash ≠ user B affected), cursor persistence to DB on each poll

### Implementation for User Story 3

- [ ] T033 [US3] Implement `backend/app/channels/message_handler.py` inbound parser — `parse_inbound_message(msg: dict) → ParsedMessage`: extract `from_user_id`, `context_token`, `item_list`; parse text (type=1), image (type=2, download CDN + AES decrypt), voice (type=3, extract ASR text); handle `message_type != 1` skip
- [ ] T034 [US3] Implement Redis-backed dedup in `backend/app/channels/message_handler.py` — `is_duplicate(user_id, context_token)` using Redis SET `wechat:dedup:{user_id}:{context_token}` with TTL 1h; fallback to `f"{from_user_id}_{msg_id}"` if context_token empty
- [ ] T035 [US3] Implement inbound message persistence — INSERT into `agent_messages` with `direction='inbound'`, `status='received'`, `wechat_msg_id`, `context_token`, `received_at=NOW()`
- [ ] T036 [US3] Implement `ILinkConnectionPool` in `backend/app/channels/ilink_pool.py` — `startup()`: load all `wechat_credentials WHERE status='active'`, spawn per-user `asyncio.Task` for `_poll_loop()`; `add(user_id)`: spawn new Task for just-bound user; `remove(user_id)`: cancel Task, clean up breaker; `_poll_loop(user_id, client)`: continuous getupdates()→parse→persist loop with exponential backoff (5s→10s→20s→30s→60s cap)
- [ ] T037 [US3] Implement credential persistence in pool — update `wechat_credentials.cursor` and `wechat_credentials.last_polled_at` after each successful `getupdates()` response; update `wechat_credentials.context_token` after each inbound message; update `agents.last_heartbeat_at`
- [ ] T038 [US3] Wire pool lifecycle to FastAPI startup/shutdown events — `@app.on_event("startup")`: `await connection_pool.startup()`; `@app.on_event("shutdown")`: `await connection_pool.shutdown()`; bind after QR confirm: `await connection_pool.add(user_id)`; unbind: `await connection_pool.remove(user_id)`

**Checkpoint**: Bidirectional WeChat communication established. Send + Receive both functional.

---

## Phase 6: User Story 4 — Agent 在线状态与生命周期 (Priority: P2)

**Goal**: Agent status tracking (active/degraded/dormant), auto-recovery, admin monitoring panel

**Independent Test**: Bind→status=active; kill iLink→status=degraded after 2min; restart→status=active; admin panel shows all agents

### Tests for User Story 4

- [ ] T039 [P] [US4] Unit test for `CircuitBreaker` in `backend/tests/unit/test_circuit_breaker.py` — test state transitions (closed→open after 10 failures/5min), half-open probe after timeout, reset on success, per-user isolation
- [ ] T040 [P] [US4] Integration test for agent lifecycle in `backend/tests/integration/test_agent_lifecycle.py` — test status transitions dormant→active→degraded→active (recovery), status history entries, dormant→active on rebind after token expiry

### Implementation for User Story 4

- [ ] T041 [P] [US4] Implement `backend/app/channels/circuit_breaker.py` — `CircuitBreaker` class: `state` (closed/open/half_open), `failure_count`, `last_failure_time`, `open_until`; `record_success()`, `record_failure()`, `allow_request() → bool`. Config: max_failures=10, window_sec=300, half_open_after_sec=300
- [ ] T042 [US4] Integrate CircuitBreaker into `ILinkConnectionPool._poll_loop()` — on poll failure: `breaker.record_failure()` → if open: set `agents.status='degraded'`, insert `agent_status_history`, send 站内通知 → sleep until half_open; on poll success: `breaker.record_success()` → if was degraded: set `agents.status='active'`, insert `agent_status_history`
- [ ] T043 [US4] Implement agent status history tracking — every status transition inserts into `agent_status_history` with `old_status`, `new_status`, `reason`, `changed_at`
- [ ] T044 [US4] Implement `backend/app/workers/tasks/agent_health_check.py` — ARQ cron task (every 30s): scan `agents WHERE status='active' AND last_heartbeat_at < NOW() - INTERVAL '5 minutes'` → set status='degraded'; scan `wechat_credentials WHERE status='active'` cross-check with pool tasks → re-spawn missing tasks
- [ ] T045 [US4] Implement admin agent monitoring endpoints in `backend/app/modules/agent/api.py`: `GET /api/v1/agent/admin/agents?status=&page=&size=` (admin-only), `POST /api/v1/agent/admin/send-test-message` (admin sends test message to any user)
- [ ] T046 [P] [US4] Create frontend `frontend/src/components/agent/AgentStatusCard.tsx` — display agent status (colored badge: green=active, yellow=degraded, gray=dormant), last heartbeat time, message counts

**Checkpoint**: Agent lifecycle fully managed with auto-recovery and admin visibility.

---

## Phase 7: User Story 5 — Agent 全量数据访问权限 (Priority: P2)

**Goal**: Agent can read all user data via RLS-enforced AgentContext, zero data leakage between users

**Independent Test**: AgentContext reads jobs/abilities/reports → verify data matches direct user query → verify cannot read other user's data

### Tests for User Story 5

- [ ] T047 [P] [US5] Integration test for AgentContext RLS isolation in `backend/tests/integration/test_agent_context.py` — test each of 9 modules returns only own user's data; test cross-user access returns empty/403; test RLS policy enforcement

### Implementation for User Story 5

- [ ] T048 [US5] Implement `backend/app/modules/agent/context.py` — `AgentContext` class: wraps `db_session` with `SET app.user_id = <user_id>` for each read; methods: `get_jobs()`, `get_interview_sessions()`, `get_interview_reports()`, `get_ability_dimensions()`, `get_ability_profile()`, `get_error_questions()`, `get_resume_branches()`, `get_tasks()`, `get_activities()`. All methods read-only, RLS-enforced
- [ ] T049 [US5] Verify existing RLS policies cover all 9 modules — audit each table's RLS policy; if any module lacks RLS, add policy before AgentContext read method is implemented

**Checkpoint**: Agent has secure, read-only access to all user data across all modules.

---

## Phase 8: User Story 6 — Agent 配置与偏好 (Priority: P3)

**Goal**: User can set display name, quiet hours, and notification mode; Agent respects these preferences

**Independent Test**: Set quiet_hours covering current time → trigger message → verify delayed until quiet_hours_end

### Tests for User Story 6

- [ ] T050 [P] [US6] Unit test for quiet hours logic in `backend/tests/unit/test_agent_preferences.py` — test message delayed during quiet hours, sent immediately after, hourly digest aggregation, display name in message signature

### Implementation for User Story 6

- [ ] T051 [US6] Implement `GET /api/v1/agent/preferences` and `PATCH /api/v1/agent/preferences` endpoints in `backend/app/modules/agent/api.py`
- [ ] T052 [US6] Implement quiet hours delay logic — before sending outbound message, check `agent_preferences.quiet_hours_start/end`; if current time in range, delay message (keep status='pending') until quiet_hours_end; on send, prepend "消息产生于 {original_time}" if delayed
- [ ] T053 [US6] Implement hourly digest aggregation — if `notification_mode='hourly_digest'`: collect messages into Redis `wechat:digest:{user_id}:{hour}` list; at HH:00, merge all into single summary message and send
- [ ] T054 [P] [US6] Create frontend `frontend/src/components/agent/AgentPreferencesForm.tsx` — display_name text input, quiet_hours time pickers (start/end), notification_mode radio buttons (realtime/hourly_digest), save button with toast confirmation
- [ ] T055 [US6] Integrate preferences form into `frontend/src/pages/AgentSettings.tsx` — add preferences section below QR/binding card

**Checkpoint**: User has full control over Agent behavior preferences.

---

## Phase 9: E2E Tests (Priority: P3)

**Purpose**: Playwright E2E tests covering core user journeys with mock iLink API

- [ ] T056 [P] E2E test for QR binding flow in `tests/e2e/agent-wechat/agent-binding.spec.ts` — navigate to /agent, click bind, verify QR displayed, mock iLink confirmed response, verify binding status card shown, test unbind flow
- [ ] T057 [P] E2E test for agent messaging in `tests/e2e/agent-wechat/agent-messaging.spec.ts` — send test message via admin panel, verify toast confirmation, verify message logged in agent_messages table via API, verify segment count for long message
- [ ] T058 [P] E2E test for agent lifecycle in `tests/e2e/agent-wechat/agent-lifecycle.spec.ts` — verify status transitions on admin panel, verify degraded→active recovery, verify status history entries
- [ ] T059 [P] E2E test for agent preferences in `tests/e2e/agent-wechat/agent-preferences.spec.ts` — set display name, set quiet hours, change notification mode, verify persistence after page refresh

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: Final validation, documentation, and quality checks

- [ ] T060 [P] Run quickstart.md VS-1 through VS-8 validation scenarios — verify all 8 scenarios pass
- [ ] T061 [P] Verify all FR-001 through FR-025 are covered by at least one task — produce coverage matrix
- [ ] T062 Verify RLS policies on all 6 new tables — `mcp__postgres__query` to confirm policies exist and enforce user_id isolation
- [ ] T063 Run full backend test suite — `uv run pytest backend/tests/ -x --tb=short` — all tests must pass
- [ ] T064 Run frontend typecheck — `cd frontend && npm run typecheck` — zero errors
- [ ] T065 [P] Performance validation — load test with 1000 simulated long-poll connections, verify CPU ≤ 50%, memory ≤ 1GB, 72h no memory leak
- [ ] T066 Update `backend/app/modules/agent/README.md` with module documentation per Constitution Principle I
- [ ] T067 CLI smoke test — `python -m app.modules.agent.cli agent-status <test_user_id>`, `python -m app.modules.agent.cli list-bindings`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 (models, migration) — **BLOCKS all user stories**
- **US1 (Phase 3)**: Depends on Phase 2 — QR binding is the entry point
- **US2 (Phase 4)**: Depends on Phase 2 + US1 (needs binding to have bot_token for send)
- **US3 (Phase 5)**: Depends on Phase 2 + US1 (needs binding to start long-poll) — **can parallel with US2**
- **US4 (Phase 6)**: Depends on US3 (needs pool to exist for circuit breaker)
- **US5 (Phase 7)**: Depends on Phase 2 only — **can parallel with US1/2/3**
- **US6 (Phase 8)**: Depends on US2 (needs send pipeline for quiet hours delay)
- **E2E (Phase 9)**: Depends on US1-US6 completion
- **Polish (Phase 10)**: Depends on all phases

### User Story Dependency Graph

```
Phase 1 (Setup)
    ↓
Phase 2 (Foundational) ← BLOCKS ALL
    ↓
    ├── US1 (QR Binding) ← Entry point
    │       ↓
    │       ├── US2 (Send) ← Needs bot_token from bind
    │       │       ↓
    │       │       └── US6 (Preferences) ← Needs send pipeline
    │       │
    │       └── US3 (Receive) ← Needs bot_token from bind
    │               ↓
    │               └── US4 (Lifecycle) ← Needs pool to exist
    │
    └── US5 (Data Access) ← Independent! Only needs Phase 2
```

### Parallel Opportunities

**Within Phase 1**: T002 ∥ T003 ∥ T004 ∥ T005 ∥ T006
**Within Phase 2**: T007 ∥ T008; T009 ∥ T011 ∥ T012
**Within Phase 3**: T014 ∥ T015; T020 ∥ T021
**Between US2 and US3**: After US1 completes, US2 and US3 can proceed in PARALLEL
**US5**: Completely independent of US1-US4 — can run in parallel with any phase after Phase 2

---

## Parallel Example: US2 + US3 (After US1 Complete)

```bash
# Developer A: US2 — Message Send
Task: "T024 [P] [US2] Unit test for message send flow"
Task: "T025 [P] [US2] Integration test for message send API"
Task: "T026 [US2] Implement outbound message send pipeline"
Task: "T027 [US2] Implement POST /internal/send-message"
...

# Developer B: US3 — Message Receive
Task: "T031 [P] [US3] Unit test for inbound message parsing"
Task: "T032 [P] [US3] Unit test for ILinkConnectionPool"
Task: "T033 [US3] Implement inbound message parser"
Task: "T034 [US3] Implement Redis-backed dedup"
...
```

---

## Implementation Strategy

### MVP First (US1 Only)

1. Complete Phase 1: Setup (T001-T006)
2. Complete Phase 2: Foundational (T007-T013)
3. Complete Phase 3: US1 QR Binding (T014-T023)
4. **STOP and VALIDATE**: Test QR bind flow end-to-end with mock iLink API
5. Deploy/demo: Users can bind WeChat — foundation for REQ-053/054

### Minimum Viable WeChat Channel (US1+US2+US3)

1. MVP + Phase 4 (US2 Send) + Phase 5 (US3 Receive)
2. Bidirectional WeChat communication established
3. REQ-053 (Interview Intelligence) can start using send capability
4. REQ-054 (Conversational Agent) can start using receive + send

### Full Feature

1. All phases 1-10
2. Complete agent lifecycle management + preferences + E2E tests
3. Production-ready for 1000 concurrent users

### Parallel Team Strategy

With 2 developers after Phase 2:
- **Developer A**: US1 → US2 → US6 (binding → send → preferences chain)
- **Developer B**: US3 → US4 (receive → lifecycle chain)
- **US5**: Either developer can pick up anytime (independent)

---

## Notes

- [P] tasks = different files, no dependencies — can execute in parallel
- [Story] label maps task to specific user story for traceability
- Each user story is independently completable and testable
- Tests are MANDATORY per Constitution Principle III (Test-First, non-negotiable)
- Write tests FIRST, ensure they FAIL, then implement
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Verify with `mcp__postgres__query` after any DB schema changes (per memory: 落库验收)
- iLink API calls are mocked in all tests — never require real WeChat connection in CI
