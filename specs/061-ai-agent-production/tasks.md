---

description: "Dependency-ordered implementation tasks for REQ-061"
---

# Tasks: 全域 AI / Agent 生产级升级

**Input**: Design documents from `/specs/061-ai-agent-production/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`

**Tests**: Required by the InterCraft Constitution. Every behavior slice defines a regression/invariant test that fails without the change or documented equivalent pre-change evidence. Bugs and R2/R3 deterministic behavior retain RED/GREEN commands and results; human approval applies only at risk-defined confirmation, merge, deviation, or release gates.

**Organization**: Tasks are grouped by user story. Phase order follows implementation dependencies; the original story priority remains shown in every phase heading. Each story checkpoint requires its applicable R3 security, recovery, privacy, evaluation, telemetry, and operational evidence. No checkpoint authorizes production cutover until the aggregate release gate is green and T183 closes the dependency deviation.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel after prior phase gates because it touches independent files and has no dependency on another incomplete task in the same group.
- **[Story]**: Maps directly to the numbered user story in `spec.md`.
- Every task names its implementation or evidence path.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish the two self-contained modules, generated contract surface, and evidence location without changing production behavior.

- [X] T001 Create the `ai_runtime` package, public exports, CLI entry shell, and module contract documentation in `backend/app/modules/ai_runtime/__init__.py`, `backend/app/modules/ai_runtime/cli.py`, and `backend/app/modules/ai_runtime/README.md`
- [X] T002 [P] Create the `ai_metering` package, public exports, CLI entry shell, and module contract documentation in `backend/app/modules/ai_metering/__init__.py`, `backend/app/modules/ai_metering/cli.py`, and `backend/app/modules/ai_metering/README.md`
- [X] T003 [P] Add deterministic OpenAPI-to-TypeScript generation for all three REQ-061 contracts in `scripts/generate-ai-contracts.mjs`, `src/types/generated/ai-runtime.ts`, `src/types/generated/ai-metering.ts`, and `src/types/generated/ai-operations.ts`
- [X] T004 Add contract-generation and fail-on-diff commands to `package.json` and the default quality workflow in `.github/workflows/ci.yml`
- [X] T005 [P] Create the initial capability/action registry fixture with owners, tiers, engine kinds, milestones, runbooks, and rollout status in `backend/tests/fixtures/ai_capability_registry.json`
- [X] T006 [P] Create the REQ-061 implementation evidence index and stable evidence naming rules in `docs/evidence/061-ai-agent-production/README.md`

**Checkpoint**: Both libraries import independently, expose documented CLI shells, and generated contract types are reproducible.

---

## Phase 2: Foundational Runtime and Ledger (Blocking Prerequisites)

**Purpose**: Deliver the shared causal identity, append-only facts, transaction boundaries, provider-attempt gateway, recovery primitives, projection outbox, and named admin authorization used by every story.

**⚠️ CRITICAL**: No user story implementation begins until this phase is green.

### Tests first

- [X] T007 [P] Add failing unit/property tests for the canonical 12-state task FSM, monotonic milestone progress, execution lineage, event sequencing, and failure policy table in `backend/tests/unit/test_061_ai_runtime_state_machine.py`
- [X] T008 [P] Add failing property tests for point postings, FIFO buckets, reservation limits, idempotency, negative-balance rejection, and conservation rebuilds in `backend/tests/unit/test_061_point_ledger_invariants.py`
- [X] T009 [P] Add failing unit tests for per-attempt usage, decimal cost, unknown-vs-zero semantics, rate/FX locking, adjustment, allocation conservation, and attribution categories in `backend/tests/unit/test_061_usage_cost_facts.py`
- [X] T010 [P] Add failing PostgreSQL integration tests for runtime/metering foreign keys, append-only enforcement, RLS owner isolation, pseudonymous ledger retention, one Alembic head, advisory-lock + migration-ledger exclusion under scheduler races, restartable backfill, mixed-binary expand compatibility and contract blocking while any old reader/checkpoint/payload remains in `backend/tests/integration/test_061_runtime_metering_migrations.py`
- [X] T011 [P] Add failing contract tests for durable event envelopes, projection idempotency, the non-exhaustive per-store lifecycle registry, provenance deletion fan-out/evidence, live checkpoint/interrupt/job version matrix fixtures, decoder/upcaster coverage, correlation identifiers and CLI exit/output semantics in `backend/tests/contract/test_061_event_projection_cli_contract.py`
- [X] T012 [P] Add failing authorization tests for support, AI operations, quality/Bad Case, cost, model-policy, restricted-content and audit export plus immutable authorization receipts; mutate actor/tenant/action/target/version/argument hash/tool-policy version/budget/expiry/idempotency/approval one field at a time and prove execution-time CAS rejects or requires reauthorization in `backend/tests/unit/test_061_ai_admin_capabilities.py` and `backend/tests/integration/test_061_authorization_receipts.py`

### Minimal foundational implementation

- [X] T013 Implement `AITask` with scoped idempotency key/request hash, `AIExecution`, `AIDispatchIntent`, immutable `AIAuthorizationReceipt`, fenced `AIExternalEffectIntent`, `AITaskEvent`, `AIStageAttempt`, `AIExternalAttempt`, `AIMilestone`, input/policy snapshots, capability versions, evidence snapshots/access, deletion deliveries, projection deliveries and operational projections in `backend/app/modules/ai_runtime/models.py`
- [X] T014 [P] Implement point accounts, buckets, quotes, reservations, ledger events/postings, grant config, and price table versions in `backend/app/modules/ai_metering/models.py`
- [X] T015 [P] Implement usage/cost events, adjustments, allocations, rate/FX versions, reconciliation runs, and issues in `backend/app/modules/ai_metering/usage_cost/models.py`
- [X] T016 Create the additive runtime/projection expand migration descending from `0057_060_agent_recovery_queue` with constraints, indexes, partitions, append-only guards and RLS; implement PostgreSQL advisory-lock/migration-ledger exclusion plus resumable idempotent backfill checkpoints in `backend/migrations/versions/0058_061_ai_runtime_foundation.py` and `backend/app/core/migration_runner.py`
- [X] T017 Create the additive point/cost ledger expand migration descending from T016 with posting balance constraints, idempotency indexes, retention-safe subjects, RLS, and tested backout/roll-forward evidence in `backend/migrations/versions/0059_061_ai_metering_foundation.py`
- [X] T018 Implement the canonical FSM, failure policy catalog, event append, optimistic versioning and transaction-safe repositories; every authoritative state/checkpoint/outbox/effect-intent transition and result adoption must CAS the current `claim_generation` in `backend/app/modules/ai_runtime/state_machine.py`, `backend/app/modules/ai_runtime/repository.py`, and `backend/app/modules/ai_runtime/service.py`
- [X] T019 Implement semantic point commands (`grant`, `reserve`, `settle`, `release`, `refund`, `compensate`, `reverse`) and atomic balance projections in `backend/app/modules/ai_metering/points/service.py` and `backend/app/modules/ai_metering/repository.py`
- [X] T020 [P] Implement attempt usage/cost recording, effective rate lookup, FX conversion, append-only confirmation/correction, shared allocation, and unknown-rate gating in `backend/app/modules/ai_metering/usage_cost/service.py` and `backend/app/modules/ai_metering/usage_cost/repository.py`
- [X] T021 Implement framework-neutral `ExecutionContext`/service factories, immutable authorization-receipt validation, fenced external-effect-intent issuance, attempt recording, retry/cost budgets, circuit breaker, fallback and structured-output boundary; wire them separately from FastAPI, ARQ, CLI and graph composition roots in `backend/app/modules/ai_runtime/provider_gateway/service.py`, `backend/app/modules/ai_runtime/authorization/service.py`, `backend/app/agents/llm_client.py`, `backend/app/main.py`, and `backend/app/workers/main.py`
- [X] T022 Implement transactional projection outbox plus a policy registry/deletion orchestrator covering every data-model lifecycle row, provenance fan-out, tombstone/expiry/provider/backup evidence and SLA alerts; deliver idempotent admin/OTel/LangSmith projections in `backend/app/modules/ai_runtime/projections/service.py`, `backend/app/modules/ai_runtime/privacy/service.py`, `backend/app/workers/tasks/ai_projection_delivery.py`, and `backend/app/workers/tasks/ai_data_deletion.py`
- [X] T023 Implement idempotent dispatch-intent delivery/reconciliation, claim renewal, expired-task scan, durable `retry_wait`, fenced external-effect send/adoption, unknown-effect reconciliation, dead-letter routing and bounded admission; add the live-version registry plus checkpoint/interrupt/job decoder-upcaster/quarantine paths in `backend/app/modules/ai_runtime/recovery/service.py`, `backend/app/modules/ai_runtime/compatibility.py`, `backend/app/workers/tasks/ai_task_dispatch.py`, and `backend/app/workers/tasks/ai_task_recovery.py`
- [X] T024 Implement named admin capabilities, field-level access decisions, restricted reveal requirements, and audit hooks in `backend/app/modules/auth/ai_capabilities.py` and `backend/app/modules/audit/service.py`
- [X] T025 Register runtime/metering routers, workers, root CLI groups, and generated schema exports in `backend/app/api/v1/__init__.py`, `backend/app/main.py`, `backend/app/workers/main.py`, and `backend/app/cli/__init__.py`

**Checkpoint**: Foundation tests pass; accepted facts survive Redis/OTel/LangSmith loss; ledger events conserve value; every external attempt can be recorded independently; no capability is cut over yet.

---

## Phase 3: User Story 1 — 理解并控制每个 AI 任务 (Priority: P1) 🎯 MVP

**Goal**: Give every AI action one stable task identity, truthful state/stage/milestone progress, cross-page recovery, user-safe failures, and server-derived actions.

**Independent Test**: Start a short conversation and a multi-stage task, refresh and re-authenticate, request cancellation, and verify task center/detail state and terminal truth without opening capability-specific diagnostics.

### Tests first

- [X] T026 [P] [US1] Add failing OpenAPI contract tests for quote, task list/detail/events, canonical enums, cursor pagination, problem details, and owner isolation in `backend/tests/contract/test_061_ai_runtime_user_api.py`
- [X] T027 [P] [US1] Add failing integration tests for two-second acceptance, concurrent duplicate start idempotency on `(tenant/user, capability, action, key)`, same-key/different-request-hash 409, contiguous events, monotonic milestones, refresh/re-login recovery and no orphan causal records in `backend/tests/integration/test_061_ai_task_lifecycle.py`
- [X] T028 [P] [US1] Add failing frontend tests for server-derived terminal/actions, status/stage rendering, progress, failure explanation, polling/SSE dedupe, and query keys in `src/components/ai/__tests__/AITaskPresentation.test.tsx`

### Implementation

- [X] T029 [US1] Implement quote validation and durable acceptance that atomically creates task/execution/reservation/events/dispatch intent within two seconds; API success must not depend on a Redis enqueue in `backend/app/modules/ai_runtime/acceptance.py` and `backend/app/modules/ai_runtime/api.py`
- [X] T030 [US1] Implement owner-scoped 90-day task list, task detail, ordered events, cursor pagination, stable problem responses, and server-derived actions in `backend/app/modules/ai_runtime/api.py` and `backend/app/modules/ai_runtime/schemas.py`
- [X] T031 [US1] Implement the versioned capability adapter registry and canonical acceptance envelope validator in `backend/app/modules/ai_runtime/adapters/registry.py` and `backend/app/modules/ai_runtime/adapters/contracts.py`
- [X] T032 [P] [US1] Implement generated runtime client wrappers, namespaced TanStack query keys, reconnect polling, and event sequence dedupe in `src/api/ai-runtime.ts` and `src/hooks/queries/useAITasks.ts`
- [X] T033 [P] [US1] Implement shared task status, stage, milestone, point summary, failure explanation, and action components in `src/components/ai/AITaskStatus.tsx`, `src/components/ai/AIMilestoneList.tsx`, and `src/components/ai/AIFailurePanel.tsx`
- [X] T034 [US1] Implement the global AI task center/detail routes and navigation entry in `src/pages/AITaskCenter.tsx`, `src/pages/AITaskDetail.tsx`, and `src/App.tsx`
- [X] T035 [US1] Add the real persistence Playwright acceptance for acceptance, refresh, re-login, filters, milestones, task links, and consistent terminal state in `tests/e2e/061-ai-task-center.spec.ts`

**Checkpoint**: US1 works with mock providers and seeded point fixtures; capability pages can return the canonical acceptance envelope without yet changing all domain workflows.

---

## Phase 4: User Story 2 — 复盘并安全重新执行任务 (Priority: P1)

**Goal**: Provide durable cancel/resume/retry/re-execution lineage and read-only evidence replay without duplicate side effects or charges.

**Independent Test**: Build a task with model retry, unknown tool result, partial delivery, and settlement; replay evidence with zero effects, then re-execute using current versions and compare immutable lineages.

### Tests first

- [X] T036 [P] [US2] Add failing contract tests for cancel, resume, system-failure retry, re-execution, idempotency headers, expected-version conflicts, and action eligibility in `backend/tests/contract/test_061_ai_task_control_api.py`
- [X] T037 [P] [US2] Add failing integration tests for queued/running cancel races, every live checkpoint/interrupt/job fixture resume, decoder/upcaster/quarantine outcomes, retry scheduling, lease loss after validation but before provider call, stale result-adoption rejection, unknown-effect reconciliation, 24-hour charge lineage and deterministic-failure quarantine in `backend/tests/integration/test_061_ai_task_control_recovery.py`
- [X] T038 [P] [US2] Add failing tests proving evidence replay creates zero provider/tool/domain-write/execution/point/cost records in `backend/tests/integration/test_061_evidence_replay_is_read_only.py`

### Implementation

- [X] T039 [US2] Implement durable cancel, resume, system-failure retry, component retry, and re-execution commands with expected-version and lineage rules in `backend/app/modules/ai_runtime/control.py`
- [X] T040 [US2] Complete safe-point cancellation, trusted checkpoint continuation, deterministic-failure quarantine, task-level retry budgets, and actual recovery enqueue behavior in `backend/app/modules/ai_runtime/recovery/service.py` and `backend/app/workers/tasks/ai_task_recovery.py`
- [X] T041 [US2] Implement event-only replay reconstruction, completeness reporting, original/latest input choice, and original/current behavior version choice in `backend/app/modules/ai_runtime/evidence_replay.py`
- [X] T042 [US2] Expose control and replay endpoints with 202/409 semantics and no mutating `replay` alias in `backend/app/modules/ai_runtime/api.py` and `backend/app/modules/ai_runtime/schemas.py`
- [X] T043 [P] [US2] Implement cancel/resume/retry/re-execute dialogs, point cap preview, version choice, and conflict refresh in `src/components/ai/AITaskActions.tsx` and `src/components/ai/AIReexecutionDialog.tsx`
- [X] T044 [P] [US2] Implement runtime inspection/recovery/replay CLI commands and JSON/exit-code contract in `backend/app/modules/ai_runtime/cli.py`
- [X] T045 [US2] Add Playwright coverage for cancellation races, resume, failure retry, re-execution lineage, and read-only replay counters in `tests/e2e/061-ai-task-control-replay.spec.ts`

**Checkpoint**: US2 proves task control and replay safety independently with mock providers and fault injection.

---

## Phase 5: User Story 8 — 获得并核对内测体验点数 (Priority: P1)

**Goal**: Deliver Pro “新用户体验”, configurable daily 2,000-point grants, expiring buckets, reservation/settlement/refund detail, and no payment UI.

**Independent Test**: Verify existing/new users, configuration changes, midnight expiry, cross-day reservations, and success/failure/retry/cancel/partial/duplicate task settlement line by line.

### Tests first

- [X] T046 [P] [US8] Add failing contract tests for point account, ledger, 24-month export, personal budget, Pro experience constants, and absence of RMB/payment fields in `backend/tests/contract/test_061_ai_points_user_api.py`
- [X] T047 [P] [US8] Add failing unit tests for config effective time, one grant per Shanghai business date, new-user immediate grant, FIFO expiry, cross-day reservation, expired-bucket compensation, and no retroactive resize in `backend/tests/unit/test_061_daily_experience_points.py`
- [X] T048 [P] [US8] Add failing integration tests for concurrent grant/expiry/reservation/settlement, duplicate submissions, partial milestone charging, zero-delivery release, and daily conservation in `backend/tests/integration/test_061_point_lifecycle.py`

### Implementation

- [X] T049 [US8] Implement versioned daily grant and point price-table configuration with the initial 2,000-point amount and locked milestone rates in `backend/app/modules/ai_metering/points/configuration.py` and `backend/app/modules/ai_metering/points/catalog.py`
- [X] T050 [US8] Implement new-user grant, Shanghai midnight grant/expiry, cross-day compensation, and idempotent scheduling in `backend/app/workers/tasks/ai_daily_point_grant.py` and `backend/app/workers/tasks/ai_point_expiry.py`
- [X] T051 [US8] Implement owner-scoped point account, ledger, export job, budget, and task deep-link APIs in `backend/app/modules/ai_metering/api.py` and `backend/app/modules/ai_metering/schemas.py`
- [X] T052 [US8] Implement beta entitlement projection (`Pro`, `新用户体验`, tiers, parallel limit 2, history 90 days, `is_paid=false`) in `backend/app/modules/account/beta_entitlement.py`
- [X] T053 [US8] Change account subscription reads to the beta entitlement/point projection while retaining legacy monthly-token comparison internally in `backend/app/modules/account/subscription.py` and `backend/app/modules/account/api.py`
- [X] T054 [P] [US8] Implement point account, ledger, export, and budget frontend clients/hooks from generated types in `src/api/ai-metering.ts` and `src/hooks/queries/useAIPoints.ts`
- [X] T055 [US8] Replace Free/Pro/Enterprise upgrade and monthly-token presentation with Pro experience, balances, buckets, expiry, reservations, and retryable error states in `src/components/settings/SubscriptionTab.tsx`
- [X] T056 [P] [US8] Replace topbar upgrade messaging with the Pro “新用户体验” badge and point summary in `src/components/layout/Topbar.tsx`
- [X] T057 [US8] Implement point ledger/detail/export and personal budget pages with task/milestone links and no RMB controls in `src/pages/AIPoints.tsx` and `src/components/ai/AIPointLedger.tsx`
- [X] T058 [US8] Add fake-clock Playwright acceptance for grants, config changes, expiry, settlement matrix, duplicate submission, Pro display, and no purchase/recharge UI in `tests/e2e/061-beta-points.spec.ts`

**Checkpoint**: US8 is a complete beta entitlement and point-accounting slice; old monthly tokens are not yet physically removed and no user is double charged.

---

## Phase 6: User Story 3 — 获得可信且可恢复的简历智能 (Priority: P1)

**Goal**: Connect resume intelligence and derive to canonical tasks, fact-safe milestones, version conflict protection, apply/undo, partial settlement, and recovery.

**Independent Test**: Complete derive → analyze → preview → apply → undo while injecting analysis failure and resume-version conflict.

### Tests first

- [X] T059 [P] [US3] Add failing adapter contract tests for resume intelligence/derive state mapping, acceptance envelope, input snapshots, three derive milestones, cancel/retry, result links and current/prior live checkpoint/job fixture decoding in `backend/tests/contract/test_061_resume_ai_adapters.py`
- [X] T060 [P] [US3] Add failing integration tests for anti-fabrication gates, preview/apply/undo versions, stale input conflict, partial settlement, system retry, N-1/live-version resume and no duplicate effect/charge in `backend/tests/integration/test_061_resume_ai_production_flow.py`
- [X] T061 [P] [US3] Add failing frontend tests for canonical task state, suggestions with source/risk/page impact, conflict handling, partial milestones, and undo in `src/modules/resume/ai/__tests__/production-task-flow.test.tsx`

### Implementation

- [X] T062 [P] [US3] Implement the resume intelligence capability adapter, input/version snapshot, analysis/suggestion milestones, quality gates, and result refs in `backend/app/modules/ai_runtime/adapters/resume_intelligence.py`
- [X] T063 [P] [US3] Implement the resume derive adapter with draft/job-analysis/suggestions milestones, component retry, cancellation, and partial settlement evidence in `backend/app/modules/ai_runtime/adapters/resume_derive.py`
- [X] T064 [US3] Persist suggestion preview/apply/undo evidence and enforce fact confirmation plus optimistic resume-version conflict in `backend/app/modules/resume_intelligence/service.py` and `backend/app/modules/versions/service.py`
- [X] T065 [US3] Return the canonical task acceptance envelope and runtime links from existing resume intelligence/derive start/status APIs in `backend/app/modules/resume_intelligence/api.py` and `backend/app/modules/resume_derive/api.py`
- [X] T066 [P] [US3] Integrate generated task controls and result/version semantics into the resume AI workspace in `src/modules/resume/ai/useAIWorkspaceController.ts` and `src/modules/resume/ai/api.ts`
- [X] T067 [P] [US3] Replace derive's local status strings/client timeout with canonical milestones, server actions, and task links in `src/modules/resume/derive/DeriveProgress.tsx` and `src/modules/resume/derive/api.ts`
- [X] T068 [US3] Add Playwright acceptance for derive, analysis, preview/apply/undo, partial result, refresh recovery, conflict, and point settlement in `tests/e2e/061-resume-ai-production.spec.ts`

**Checkpoint**: Resume intelligence and derive independently use runtime/metering truth without overwriting domain content.

---

## Phase 7: User Story 4 — 完整控制模拟面试生命周期 (Priority: P1)

**Goal**: Make interview start/pause/resume/end/reconnect truthful, score-first, checkpointed, degradable only by consent, and milestone-settled.

**Independent Test**: Run an interview with pause, network reconnect, active ending, plan degradation, and report failure; verify preserved scores, state, and points.

### Tests first

- [X] T069 [P] [US4] Add failing adapter/WebSocket contract tests for interview acceptance, canonical state/stage mapping, score-first events, pause deadlines, reconnect sequence, report milestones and current/prior live checkpoint/interrupt/job fixtures in `backend/tests/contract/test_061_interview_runtime_adapter.py`
- [X] T070 [P] [US4] Add failing integration tests for plan failure/consented degradation, per-round scoring, next-question retry, seven-day pause, reconnect, partial report, active end, settlement and N-1/live-version pause-resume in `backend/tests/integration/test_061_interview_production_lifecycle.py`
- [X] T071 [P] [US4] Add failing frontend tests for score-before-next-question, canonical pause/resume actions, reconnect dedupe, saved-round explanation, and report failure in `src/pages/__tests__/InterviewLive.production.test.tsx`

### Implementation

- [X] T072 [US4] Implement the interview adapter, input/policy snapshot, round-score/report milestones, pause checkpoint, active-end choices, and degradation authorization in `backend/app/modules/ai_runtime/adapters/interview.py`
- [X] T073 [US4] Integrate canonical execution context, cancellation, strict checkpoint serialization, declared state decoder/upcaster, current/prior live-version pause-resume and per-stage attempt recording into `backend/app/agents/graphs/interview.py` and `backend/app/modules/interviews/service.py`
- [X] T074 [US4] Extend interview HTTP/WebSocket schemas to return task/execution IDs, ordered event sequences, server actions, point summaries, and safe failure details in `backend/app/modules/interviews/api.py` and `backend/app/modules/interviews/schemas.py`
- [X] T075 [US4] Make score delivery, next-question generation, report assembly, and plan fallback independently retryable and evidence-gated in `backend/app/modules/interviews/service.py` and `backend/app/workers/tasks/interview_research.py`
- [X] T076 [P] [US4] Integrate canonical task IDs, score-first events, pause/resume controls, reconnect sequence, and point details into `src/hooks/useInterviewWS.ts` and `src/pages/InterviewLive.tsx`
- [X] T077 [P] [US4] Present partial/full report milestones, failure recovery, and task/point links in `src/pages/InterviewReport.tsx`
- [X] T078 [US4] Add Playwright acceptance for pause/reconnect/end/degrade/report failure, score preservation, task terminal state, and point settlement in `tests/e2e/061-interview-production.spec.ts`

**Checkpoint**: Interview is independently recoverable and chargeable by delivered score/report milestones.

---

## Phase 8: User Story 5 — 安全使用 Agent 与教练能力 (Priority: P1)

**Goal**: Make WeChat Agent and web coaches return persisted visible answers, require write confirmation, prove tool effects, and recover or fail truthfully.

**Independent Test**: Execute read, confirmed write, ambiguous intent, tool timeout, cancel, and resume flows across WeChat and web.

### Tests first

- [X] T079 [P] [US5] Add failing WeChat adapter tests for binding-scoped domain mapping, the full authorization-receipt bound-field matrix, receipt CAS consumption, fenced effect send/adoption, committed/unknown tool evidence, delivery independence and canonical lineage in `backend/tests/contract/test_061_wechat_agent_adapter.py`
- [X] T080 [P] [US5] Add failing coach contract/integration tests for persisted assistant body, conversation recovery/end, per-answer feedback, scored error rounds, cancellation, truthful failures and every declared live checkpoint/job version in `backend/tests/integration/test_061_coach_runtime_flows.py`
- [X] T081 [P] [US5] Add failing frontend tests that remove hard-coded Agent terminal/action arrays and render server actions plus persisted coach answers in `src/pages/__tests__/AgentCoachProduction.test.tsx`

### Implementation

- [X] T082 [US5] Implement the WeChat Agent adapter that maps channel-specific tasks/events/tools/delivery to the canonical task while retaining binding epoch, immutable authorization receipt, execution fence and effect-intent evidence in `backend/app/modules/ai_runtime/adapters/wechat_agent.py`
- [X] T083 [US5] Connect the existing Agent tool loop to shared execution context, receipt CAS, fenced durable effect intents, attempt/cost recording, cancellation and unknown-effect reconciliation; a stale lease may record an attempt but cannot adopt the tool result in `backend/app/modules/agent/runtime/orchestrator.py` and `backend/app/modules/agent/runtime/stores.py`
- [X] T084 [P] [US5] Implement the general coach adapter with strict serialization, declared live-version decoder/upcaster, persisted assistant bodies, conversation end, feedback and checkpoint references in `backend/app/modules/ai_runtime/adapters/general_coach.py` and `backend/app/agents/graphs/general_coach.py`
- [X] T085 [P] [US5] Implement the error coach adapter with strict serialization, declared live-version decoder/upcaster, per-round score/hint/correct-count milestones and resumable state in `backend/app/modules/ai_runtime/adapters/error_coach.py` and `backend/app/agents/graphs/error_coach.py`
- [X] T086 [US5] Return canonical acceptance/detail/control links from Agent dev ingress and coach APIs without exposing binding/provider internals in `backend/app/modules/agent/api.py` and `backend/app/api/v1/agents.py`
- [X] T087 [P] [US5] Render persisted assistant messages, recovery/end controls, point summaries, and per-answer feedback in `src/hooks/useGeneralCoach.ts` and `src/pages/GeneralCoach.tsx`
- [X] T088 [P] [US5] Integrate canonical task state, round milestones, cancel/resume, and terminal handling into `src/hooks/useErrorCoach.ts`
- [X] T089 [US5] Replace AgentSettings status/action inference with generated task DTOs, polling/event refresh, and server actions in `src/pages/AgentSettings.tsx` and `src/repositories/AgentRepository.ts`
- [X] T090 [US5] Add Playwright acceptance for read/write confirmation, ambiguous intent, timeout/unknown result, cancellation, recovery, visible coach replies, and no false success in `tests/e2e/061-agent-coach-production.spec.ts`

**Checkpoint**: Agent and coach capabilities are independently truthful, recoverable, auditable, and point-linked.

---

## Phase 9: User Story 6 — 理解画像与主动研究的来源和消耗 (Priority: P2)

**Goal**: Separate deterministic profile score from AI insight and make proactive research explicitly opt-in, quoted, sourced, cancellable, and failure-safe.

**Independent Test**: Complete an interview, enable research for a future role, then inject insight failure, research cancellation, and delivery failure.

### Tests first

- [ ] T091 [P] [US6] Add failing adapter tests for deterministic-profile vs AI-insight separation, research opt-in quote, source sufficiency, cancellation, and result milestones in `backend/tests/contract/test_061_profile_research_adapters.py`
- [ ] T092 [P] [US6] Add failing integration tests proving insight failure preserves verified score and research does not consume points before explicit opt-in/acceptance in `backend/tests/integration/test_061_profile_research_flow.py`
- [X] T093 [P] [US6] Add failing frontend tests for separate score/insight states, research job/tier/point preview, disable control, sources, and failed delivery in `src/pages/AbilityProfile/__tests__/AIInsightResearch.test.tsx`

### Implementation

- [X] T094 [P] [US6] Implement the ability-insight adapter and separate deterministic score updates from AI task/milestone evidence in `backend/app/modules/ai_runtime/adapters/ability_insight.py` and `backend/app/modules/ability_profile/service.py`
    - 2026-07-13 codex/064: DashboardResponse now has typed `verified_score_status` (`"ready"|"unavailable"`) and `AbilityInsightProjection` (`task_id`/`status`/`user_summary`/`available_actions`/`failure_category`) fields; service queries canonical AITask ordered by `accepted_at DESC, id DESC` with owner isolation; score 0 from interview/coach qualifies as ready.
- [X] T095 [P] [US6] Implement the proactive-research adapter with opt-in, job/input snapshot, quote, source sufficiency gate, cancellation, and report milestone in `backend/app/modules/ai_runtime/adapters/research.py`
- [ ] T096 [US6] Connect interview diagnosis and research workers to canonical acceptance, execution context, point settlement, and failure categories in `backend/app/workers/tasks/ability_diagnose.py` and `backend/app/workers/tasks/interview_research.py`
    - 2026-07-13 codex/064: Both workers are real registered files — `ability_diagnose.py` and `interview_research.py` — but **neither is fully connected** to the canonical lifecycle. Zero-point settlement, lifecycle integration, and fencing gaps remain for a follow-up governed Issue.
- [X] T097 [P] [US6] Render deterministic score and AI insight as independent states with task/retry links in `src/pages/AbilityProfile.tsx` and `src/pages/AbilityProfileDetail.tsx`
    - 2026-07-13 codex/064: Pages consume typed `DashboardResponse.ai_insight` (`task_id`/`user_summary`/`available_actions`/`failure_category`) and `verified_score_status` directly — no `any`, `@ts-ignore`, double assertions, or fabricated ready fallback.
- [X] T098 [P] [US6] Implement proactive research opt-in, quote/point preview, source display, cancellation, and result/task links in `src/components/interview/InterviewResearchControl.tsx`
- [ ] T099 [US6] Add Playwright acceptance for score preservation, insight failure/retry, research opt-in/cancel/failure, sources, and point outcomes in `tests/e2e/061-profile-research.spec.ts`

**Checkpoint**: US6 can be validated without other capability UIs beyond the shared task/point foundation.

---

## Phase 10: User Story 7 — 按服务档位使用合适模型 (Priority: P2)

**Goal**: Offer stable standard/quality tiers while versioning internal model routes, fallbacks, gates, cost ceilings, snapshots, and admin policy controls.

**Independent Test**: Run the same capability in both tiers, switch the internal stable policy, and verify price/quality commitments plus historical audit remain stable.

### Tests first

- [X] T100 [P] [US7] Add failing admin/user contract tests for capability catalog, tier-only user exposure, model policy list/create/release, decimal ceilings, rollback target, and role restrictions in `backend/tests/contract/test_061_model_policy_api.py`
- [X] T101 [P] [US7] Add failing unit tests for effective policy selection, execution-time locking, fallback quality authorization, unknown-rate blocking, safety-upgrade no surcharge, and resume/re-execution version rules in `backend/tests/unit/test_061_model_policy_selection.py`
- [X] T102 [P] [US7] Add failing integration tests for standard/quality quote stability across internal route switches and complete historical behavior snapshots in `backend/tests/integration/test_061_model_policy_history.py`
- [X] T103 [P] [US7] Add failing frontend tests ensuring users never see provider/model names while admins see candidate/stable/traffic/evidence/rollback fields in `src/components/ai/__tests__/AIServiceTierPolicy.test.tsx`

### Implementation

- [X] T104 [US7] Implement effective-dated model policy repository, status transitions, ownership, evaluation/rollback requirements, and non-overlapping stable ranges in `backend/app/modules/ai_runtime/provider_gateway/policy_repository.py` and `backend/app/modules/ai_runtime/provider_gateway/policy_service.py`
- [X] T105 [US7] Implement runtime tier-to-route selection, execution snapshot locking, quality-gated fallback, safety upgrade, and cost-ceiling admission in `backend/app/modules/ai_runtime/provider_gateway/router.py`
- [X] T106 [US7] Implement user capability catalog and admin model-policy endpoints from the OpenAPI contract in `backend/app/modules/ai_runtime/api.py` and `backend/app/modules/admin_console/ai_operations/api.py`
- [X] T107 [US7] Make quote/acceptance expose only tier, point cap, degradation authorization, and result limitations while preserving internal versions in `backend/app/modules/ai_runtime/schemas.py`
- [X] T108 [P] [US7] Implement reusable standard/quality selectors, degradation consent, and stable tier presentation in `src/components/ai/AIServiceTierSelector.tsx`
- [X] T109 [P] [US7] Implement model-policy list/detail/candidate/traffic/evidence/rollback UI for authorized admins in `src/admin/pages/ModelPolicies.tsx` and `src/admin/api/ai-model-policies.ts`
- [X] T110 [US7] Add Playwright acceptance for both tiers, hidden provider names, internal route switch, fallback authorization, cost ceiling gate, and historical version detail in `tests/e2e/061-model-policy-tiers.spec.ts`

**Checkpoint**: Model switching is a governed internal policy and never changes an accepted user's tier/point commitment silently.

---

## Phase 11: User Story 9 — 运营人员看到真实质量、成本和异常消耗 (Priority: P1)

**Goal**: Provide real joined stability/quality/latency/point/cost metrics, attempt-level cost drilldown, budgets, anomaly controls, and daily/invoice reconciliation.

**Independent Test**: Produce real success/failure/retry/refund/cache/late-cost/Bad Case facts and reconcile point conservation, attempt costs, corrections, and dashboard totals.

### Tests first

- [X] T111 [P] [US9] Add failing contract tests for metrics, point configs, cost rates, budgets, reconciliation, decimal money, data quality, and beta revenue zero in `backend/tests/contract/test_061_ai_operations_cost_api.py`
- [X] T112 [P] [US9] Add failing integration tests for attempt coverage, estimate→confirm→reconcile→reverse, late usage, FX correction, shared allocation, orphan cost, daily 0.5% threshold, and invoice matching in `backend/tests/integration/test_061_cost_reconciliation.py`
- [X] T113 [P] [US9] Add failing unit tests for 7-day P95×2 task cost, hourly 20% user consumption, repeated-failure threshold, 80/100% budgets, and protected query/cancel paths in `backend/tests/unit/test_061_abnormal_consumption.py`
- [X] T114 [P] [US9] Add failing frontend tests that require real data quality, unknown values, beta revenue zero, filters, and point→milestone→attempt→cost drilldown in `src/admin/pages/__tests__/AIOperations.production.test.tsx`

### Implementation

- [X] T115 [US9] Implement fact-driven operational aggregations by capability/tier/user/policy/release/grant config/date with freshness, coverage, and unknowns in `backend/app/modules/agent_observability/projections.py`
- [X] T116 [P] [US9] Implement daily point/attempt/rate/provider reconciliation, invoice correction, issue lifecycle, and projection rebuild checks in `backend/app/modules/ai_metering/reconciliation/service.py`
- [X] T117 [P] [US9] Implement site/capability/policy/config/user budgets and abnormal-consumption decisions that preserve query/cancel/appeal in `backend/app/modules/ai_metering/budgets.py` and `backend/app/modules/ai_metering/anomalies.py`
- [X] T118 [US9] Implement metrics, point-config, cost-rate, budget, reconciliation, anomaly, and task-cost drilldown admin endpoints in `backend/app/modules/admin_console/ai_operations/api.py` and `backend/app/modules/admin_console/ai_operations/schemas.py`
- [X] T119 [US9] Implement daily preliminary reconciliation, invoice import, budget evaluation, and anomaly alert workers in `backend/app/workers/tasks/ai_daily_reconciliation.py` and `backend/app/workers/tasks/ai_cost_guard.py`
- [X] T120 [P] [US9] Replace seeded AI Operations queries with generated real-data clients and stable filter/query state in `src/admin/hooks/queries/useAIOperations.ts` and `src/admin/api/ai-operations.ts`
- [X] T121 [US9] Rebuild the AI Operations page around stability, quality, latency, points, costs, unknowns, freshness, budgets, and abnormal consumption in `src/admin/pages/AIOperations.tsx`
- [X] T122 [P] [US9] Implement attempt/cost/rate/adjustment and point/milestone drilldown drawers in `src/admin/components/ai-operations/AICostDrilldown.tsx` and `src/admin/components/ai-operations/PointCostTimeline.tsx`
- [X] T123 [P] [US9] Implement metering grant/config/rate/ledger/reconcile/orphan CLI commands and JSON evidence output in `backend/app/modules/ai_metering/cli.py`
- [X] T124 [US9] Add real-persistence Playwright acceptance for joined metrics, filters, anomaly guards, drilldown, corrections, reconciliation, freshness, and zero seed/mock rows in `tests/e2e/061-ai-operations-cost.spec.ts`

**Checkpoint**: US9 provides real operational and cost truth without needing the full Bad Case management UI.

---

## Phase 12: User Story 10 — 将 Bad Case 转化为可验证改进 (Priority: P2)

**Goal**: Persist feedback-driven Bad Cases, impact scope, privacy authorization, typed review actions, regression promotion, closure evidence, fee treatment, and user notification.

**Independent Test**: Submit a factual-error feedback with authorized snapshot, deduplicate/classify/assign it, link fix/regression/eval/point treatment/notification, and enforce closure.

### Tests first

- [X] T125 [P] [US10] Add failing OpenAPI contract tests for Bad Case list/detail/timeline/impacts/actions, cursor filters, discriminated commands, version conflicts, terminal states, and data quality in `backend/tests/contract/test_061_badcase_management_api.py`
- [X] T126 [P] [US10] Add failing integration tests that reconcile current Badcase ORM/repository/migration fields and persist cases/actions across process restarts in `backend/tests/integration/test_061_badcase_persistence_alignment.py`
- [X] T127 [P] [US10] Add failing FSM tests for classify/assign/merge/note/escalate/point treatment/promote/unreproducible/close, P0/P1 SLA, closure evidence, terminal recurrence, and idempotency in `backend/tests/unit/test_061_badcase_review_workflow.py`
- [X] T128 [P] [US10] Add failing privacy tests for metadata-only feedback, independent merged-case authorizations, restricted snapshot access/export/revoke/delete, and immutable access audit in `backend/tests/integration/test_061_badcase_privacy.py`
- [X] T129 [P] [US10] Add failing frontend tests for list filters, detail tabs, confirmed/possible/excluded/unknown impacts, typed actions, closure gates, and unavailable data in `src/admin/pages/__tests__/IncidentsBadcases.production.test.tsx`

### Implementation

- [X] T130 [US10] Align Badcase/BadcaseReviewAction ORM and repository with the actual migration, then add optimistic version and closure evidence fields in `backend/app/modules/telemetry_contracts/models.py`, `backend/app/modules/badcases/models.py`, and `backend/app/modules/badcases/repository.py`
- [X] T131 [US10] Add persistent impact links, content authorizations, closure evidence, indexes, append-only actions, and RLS in `backend/migrations/versions/0060_061_badcase_management.py` and `backend/app/modules/badcases/impact.py`
- [X] T132 [US10] Implement typed review commands, merge preservation, impact confidence history, SLA/owner rules, terminal recurrence links, and transactional closure gates in `backend/app/modules/badcases/service.py`
- [X] T133 [US10] Implement automatic Bad Case intake from negative feedback, deterministic quality/safety failures, abnormal point handling, incidents, and manual inspection in `backend/app/modules/badcases/intake.py`
- [X] T134 [US10] Implement the canonical admin Bad Case list/detail/timeline/impact/action facade with named capabilities and compatibility links to legacy APIs in `backend/app/modules/admin_console/incidents/api.py` and `backend/app/modules/admin_console/incidents/schemas.py`
- [X] T135 [P] [US10] Extend encrypted content snapshot authorization, destination policy, 30-day expiry, revoke/delete, and reveal audit in `backend/app/modules/badcases/evidence.py`
- [X] T136 [P] [US10] Extend Bad Case CLI list/get/timeline/impacts/action commands and closure error evidence in `backend/app/modules/badcases/cli.py`
- [X] T137 [US10] Replace seeded/in-memory Bad Case list/drawer/actions with generated persistent APIs and typed commands in `src/admin/pages/IncidentsBadcases.tsx`, `src/admin/components/incidents/BadcaseList.tsx`, and `src/admin/components/incidents/BadcaseDrawer.tsx`
- [X] T138 [US10] Add Playwright acceptance for feedback intake, merge with independent consent, impacts, typed actions, restart persistence, closure gate, regression promotion, point treatment, and notification in `tests/e2e/061-badcase-closure.spec.ts`

**Checkpoint**: Every Bad Case has durable scope/actions and cannot close without verifiable improvement and affected-user handling.

---

## Phase 13: User Story 11 — 通过评测与灰度安全迭代 (Priority: P1)

**Goal**: Cover every capability with versioned offline/online evaluation, calibrated judges, release gates, cohort gray stages, automatic stop, rollback, and audited override.

**Independent Test**: Send a cheaper but lower-quality candidate through offline gate, 1% gray, stop condition, and rollback while preserving evidence.

### Tests first

- [X] T139 [P] [US11] Add failing dataset registry tests enforcing ≥30 active cases per capability and ≥50 for write/fact/charging capabilities across normal/boundary/failure/privacy/adversarial classes in `backend/tests/eval/test_061_eval_dataset_coverage.py`
- [X] T140 [P] [US11] Add failing evaluator calibration tests for 100 monthly stratified human examples, ≥85% agreement, zero P0/P1 misses, and report-only fallback in `backend/tests/eval/test_061_evaluator_calibration.py`
- [X] T141 [P] [US11] Add failing release integration tests for offline gates, 1→5→20→50→100 cohorts, sticky lineage, minimum observations, stop thresholds, rollback, and dual-approval override in `backend/tests/integration/test_061_ai_gray_release.py`
- [X] T142 [P] [US11] Add failing frontend tests for candidate/stable comparison, gate evidence, cohort status, stop reason, rollback target, and override audit in `src/admin/pages/__tests__/AIReleaseGovernance.test.tsx`

### Implementation

- [X] T143 [US11] Expand the eval capability registry and node dispatch beyond interview to all registered REQ-061 actions in `backend/app/eval/runner.py` and `backend/app/eval/capability_registry.py`
- [X] T144 [P] [US11] Add versioned golden/eval fixtures for resume, interview, Agent tools, coaches, profile insight, research, failure recovery, point safety, and privacy in `specs/061-ai-agent-production/eval-cases/`
- [X] T145 [P] [US11] Implement risk-based online sampling (5% ordinary, 20% high-risk, 100% P0/P1/negative/anomalous) and durable evaluation links in `backend/app/eval/online_sampler.py`
- [X] T146 [US11] Implement versioned evaluator/judge execution, calibration storage, report-only/blocking eligibility, and human comparison in `backend/app/eval/judge.py` and `backend/app/eval/calibration.py`
- [X] T147 [US11] Implement release batches, sticky cohorts, gate evaluation, observation windows, automatic stop/rollback, and audited override in `backend/app/modules/ai_runtime/provider_gateway/release_service.py`
- [X] T148 [US11] Expose release/evaluation comparison and transition endpoints through the admin operations API in `backend/app/modules/admin_console/ai_operations/api.py`
- [X] T149 [US11] Implement scheduled online evaluation, calibration reminders, gray-stage evaluation, and rollback workers in `backend/app/workers/tasks/ai_evaluation.py` and `backend/app/workers/tasks/ai_release_guard.py`
- [X] T150 [P] [US11] Implement candidate/stable comparison, gate, cohort, stop, rollback, and dual-approval UI in `src/admin/pages/AIReleaseGovernance.tsx`
- [X] T151 [US11] Extend the eval PR path filter to runtime/metering adapters, policy, prompts, tools, rubric, and REQ-061 eval cases in `.github/workflows/033-eval-gate.yml`
- [X] T152 [US11] Add Playwright/CLI acceptance for offline rejection, gray progression, automatic stop, rollback, evidence retention, and override policy in `tests/e2e/061-ai-eval-gray-release.spec.ts`

**Checkpoint**: Every production capability has measurable release evidence and no unsafe candidate can silently expand.

---

## Phase 14: User Story 12 — 在管理后台检查每次 AI 使用与每个 Bad Case (Priority: P1)

**Goal**: Let authorized roles inspect every AI task and Bad Case through four consistent workspaces, with complete causal drilldown, projection health, RBAC, privacy, and read-only replay.

**Independent Test**: Create a retrying partial task with settlement, confirmed cost, feedback, and Bad Case; inspect it under every role and with OTel/LangSmith disabled, then verify complete local facts and idempotent catch-up.

### Tests first

- [X] T153 [P] [US12] Add failing operations contract tests for task search/detail/timeline/attempts/replay, Bad Case deep links, cursor pagination, data quality, unavailable projections, and structured 403/404/409 responses in `backend/tests/contract/test_061_ai_inspection_api.py`
- [X] T154 [P] [US12] Add failing outage tests proving 30-minute OTel/LangSmith failure loses zero facts/effects, exposes backlog/last success, catches up ≥99% within 30 minutes, and never re-executes AI work in `backend/tests/integration/test_061_projection_outage_recovery.py`
- [X] T155 [P] [US12] Add failing full-drill integration tests for task→execution→stage→attempt→milestone→point/cost→feedback/eval/Bad Case and reverse links with no orphans in `backend/tests/integration/test_061_operational_task_drilldown.py`
- [X] T156 [P] [US12] Add failing API/field matrix tests for support, AI ops, quality, cost, model-policy, privacy-content, audit-export, and ordinary-user scopes in `backend/tests/contract/test_061_admin_inspection_rbac.py`
- [X] T157 [P] [US12] Add failing frontend tests for four-workspace stable deep links, task filters/detail tabs, timeline/attempt pagination, privacy reveal, projection degradation, and read-only replay in `src/admin/pages/__tests__/AIInspectionWorkspaces.test.tsx`

### Implementation

- [X] T158 [US12] Implement operational task projection consumers, completeness/orphan checks, freshness/coverage/unknown calculations, and rebuild positions in `backend/app/modules/ai_runtime/projections/operational_task.py`
- [X] T159 [P] [US12] Complete OTel trace/log projection, real HTTP→worker→engine→attempt parent propagation, bounded metric labels, and destination status in `backend/app/observability/tracing.py` and `backend/app/modules/ai_runtime/projections/otel.py`
- [X] T160 [P] [US12] Complete policy-authorized LangSmith projection, task/execution/attempt deep links, blocked representation, backlog status, and idempotent catch-up in `backend/app/eval/langsmith_sync.py` and `backend/app/modules/ai_runtime/projections/langsmith.py`
- [X] T161 [US12] Implement admin task search/detail/timeline/attempts/evidence-replay endpoints and stable reverse links from points/costs/Bad Cases in `backend/app/modules/admin_console/observability/api.py` and `backend/app/modules/admin_console/observability/schemas.py`
- [X] T162 [US12] Implement projection-status/retry CLI commands that cannot call engines/providers/tools/metering in `backend/app/modules/ai_runtime/cli.py`
- [X] T163 [US12] Replace mock/trace-centric LogsAndTraces data with generated task inspection APIs, filters, full causal timeline, attempts, costs, quality links, and read-only replay in `src/admin/pages/LogsAndTraces.tsx` and `src/admin/pages/LogCenter.tsx`
- [X] T164 [P] [US12] Implement restricted-content reveal, access reason/TTL/export audit, and unavailable external link states in `src/admin/pages/Governance.tsx` and `src/admin/components/governance/AuditLogViewer.tsx`
- [X] T165 [US12] Replace all-workspaces `is_admin` gating with named capability navigation/action guards while preserving the four routes in `src/admin/components/AdminShell.tsx`
- [X] T166 [US12] Add Playwright acceptance for every task/Bad Case section, bidirectional drilldown, four-role matrix, restricted reveal, read-only replay, exporter outage/catch-up, freshness, and zero seed/mock data in `tests/e2e/061-admin-ai-inspection.spec.ts`

**Checkpoint**: An authorized operator can reconstruct any task within five minutes and inspect every Bad Case without external-log dependence or unscoped content access.

---

## Phase 15: Aggregate Production Release Gate

**Purpose**: Aggregate and verify controls already introduced in the foundational and story slices, remove competing legacy truth, and assemble final production evidence without expanding into REQ-062. This phase is a blocking release gate, not the first implementation point for security, recovery, privacy, evaluation, observability or rollback.

- [X] T167 Add failing shadow-capture reconciliation tests comparing canonical attempts/usage/status against `ai_messages`, `ai_invocation_records`, legacy domain states, and supplier fixtures in `backend/tests/integration/test_061_shadow_capture_reconciliation.py`
- [X] T168 Implement idempotent `legacy_partial` metadata backfill and shadow comparison CLI without fabricating retries, zero usage, or historical point charges in `backend/app/modules/ai_runtime/migration.py` and `backend/app/modules/ai_runtime/cli.py`
- [X] T169 Freeze direct `monthly_token_used` writes after feature-flag cutover and disable both monthly reset schedules without deleting compatibility fields in `backend/app/agents/llm_client.py`, `backend/app/workers/tasks/monthly_quota_reset.py`, and `backend/app/workers/tasks/reset_monthly_quota_cron.py`
- [X] T170 Remove production seed/demo/in-memory fallbacks from AI operations, observability, incidents, and Bad Case services; return explicit unavailable/freshness responses instead in `backend/app/modules/admin_console/ai_operations/service.py`, `backend/app/modules/agent_observability/service.py`, and `backend/app/modules/admin_console/incidents/service.py`
- [X] T171 Re-run and consolidate the bounded checkpointer/pool/reconnect controls already implemented in Foundation/story slices: per-process budgets, shutdown, strict deserialization, live-version matrix/decoder coverage, N-1 rolling fixtures and visible quarantine outcomes in `backend/app/agents/checkpointer.py`, `backend/app/agents/checkpointer_pool.py`, and `backend/app/main.py`
- [X] T172 [P] Re-run the lifecycle/deletion orchestrator already implemented in T022 against every §10 matrix row, including snapshots, receipts, checkpoint/store/index, Redis/ARQ/DLQ, cache/temp, log/trace/eval, backup/export/provider copies, pseudonymous facts and restore-and-redelete evidence in `backend/app/workers/tasks/ai_retention.py`
- [X] T173 [P] Run aggregate adversarial regression across the per-slice RLS, prompt-injection/tool-authority, risk-bound confirmation, export-policy, secret-redaction, and cross-tenant controls in `backend/tests/security/test_061_ai_runtime_metering_security.py`
- [X] T174 Add load/resilience tests for 10k users, 2k DAU, 100 concurrent tasks, 20 accepts/s, 100 attempts/s, 10M monthly facts, 2× burst, and midnight grant in `backend/tests/performance/test_061_ai_runtime_capacity.py`
- [X] T175 Run aggregate fault-injection regression over existing story recovery controls for PostgreSQL/Redis loss, worker kill, dispatch/projection backlog, provider 429/5xx, breaker recovery, saturation admission, stale fencing and 30-minute control-plane recovery in `backend/tests/integration/test_061_ai_resilience.py`
- [X] T176 Consolidate and verify inherited control-plane plus capability-specific SLO/alert definitions for availability, queue saturation, retry amplification, breaker state, evidence gaps, backlog, ledger imbalance, unknown rate and reconciliation SLA in `backend/app/observability/ai_slos.py`
- [X] T177 [P] Update runtime, metering, Bad Case, eval, and admin operations READMEs with public API, config, CLI examples, privacy, migration, rollback, and runbooks in `backend/app/modules/ai_runtime/README.md`, `backend/app/modules/ai_metering/README.md`, `backend/app/modules/badcases/README.md`, and `backend/app/eval/README.md`
- [X] T178 Add CI validation that all reachable AI starts return the canonical envelope, all adapter registry entries have cost/eval/runbook ownership, and generated OpenAPI TypeScript is clean in `backend/tests/contract/test_061_capability_registry_completeness.py` and `.github/workflows/ci.yml`
- [X] T179 Execute all automated commands from `specs/061-ai-agent-production/quickstart.md` and record command outputs, versions, pass/fail, and unresolved evidence in `docs/evidence/061-ai-agent-production/quickstart-validation.md`
- [X] T180 Execute the shadow→points display→reservation→capability enforcement→full operations rollout/rollback drill and record every gate in `docs/evidence/061-ai-agent-production/rollout-drill.md`
- [X] T181 Run the complete backend/frontend/contract/eval/E2E suites and record the final production-readiness review against FR-001–FR-187 and SC-001–SC-049 in `docs/evidence/061-ai-agent-production/final-review.md`
- [X] T182 Update REQ-061 requirement status and the repository index only from verified evidence in `specs/061-ai-agent-production/requirements-status.md` and `specs/README.md`
- [X] T183 Close the LangGraph 0.2.28 dependency deviation by obtaining documented vendor support or migrating to the concrete target `langgraph==1.2.9` + `langgraph-checkpoint-postgres==3.1.0`; update the lock, enable strict deserialization, validate every live state/node/interrupt/dispatch/effect payload matrix row plus N-1 rolling resume, and record staged rollout/rollback evidence in `backend/pyproject.toml`, `backend/uv.lock`, `backend/app/agents/`, and `docs/evidence/061-ai-agent-production/langgraph-support-migration.md`

**Final Checkpoint**: No task is marked done without implementation plus verification evidence; the dependency deviation is closed; every selected capability has inherited or specific R3 controls; payment/order/recharge/invoice code remains absent and REQ-062 remains deferred.

---

## Dependencies & Execution Order

### Phase dependencies

```text
Setup
  └─> Foundational Runtime & Ledger
        └─> US1 Unified Task Control (MVP)
              ├─> US2 Replay / Retry / Re-execution
              └─> US8 Beta Points
                    ├─> US3 Resume AI ─┐
                    ├─> US4 Interview ─┤
                    ├─> US5 Agent/Coach├─> US11 Evaluation & Gray
                    └─> US6 Profile/Research ┘
              └─> US7 Model Policy ───────────┘
              ├─> US9 Operations & Cost
              └─> US10 Bad Case Closure
                     └───────────────┐
 US2 + US8 + US9 + US10 + US11 ─────┴─> US12 Admin Inspection
                                           └─> Aggregate Production Release Gate
```

### User story dependencies

- **US1**: Depends only on Setup and Foundation; suggested MVP.
- **US2**: Depends on US1 task identity/events and foundational recovery/metering.
- **US8**: Depends on US1 task links and foundational point commands; can run in parallel with US2 after US1.
- **US3/US4/US5/US6**: Depend on US1 and US8; their adapters and UIs can proceed in parallel.
- **US7**: Depends on US1 and foundational policy snapshots; can proceed in parallel with capability adapters.
- **US9**: Depends on US1, US8, and US7 for joined task/point/cost/policy dimensions.
- **US10**: Depends on US1 and US8 for task/feedback/point links; can proceed in parallel with US9.
- **US11**: Depends on US3–US7 adapters, US7 policy governance, and US10 regression promotion.
- **US12**: Depends on US2 read-only replay, US8 point drilldown, US9 operational/cost facts, US10 Bad Case management, and US11 evaluation/release links.
- **Aggregate Production Release Gate**: Depends on every story selected for release; no production cutover occurs before this gate, and legacy token freeze occurs only after shadow and no-double-charge evidence.

### Within each story

1. Define and run the listed regression/invariant tests or record constitution-allowed equivalent pre-change evidence.
2. For bugs and R2/R3 deterministic behavior, retain RED command, expected failure reason and GREEN result.
3. Implement models/services before APIs, then generated clients/components.
4. Run the story's applicable contract/integration/component/E2E/fault/eval tests.
5. Stop at the checkpoint until the independent test and all risk-derived evidence pass.

## Parallel Execution Examples

| Story | Parallel work after its prerequisites | Convergence task |
|---|---|---|
| US1 | T026, T027, T028; then T032 and T033 | T034–T035 |
| US2 | T036, T037, T038; then T043 and T044 | T045 |
| US8 | T046, T047, T048; then T054 and T056 | T058 |
| US3 | T059, T060, T061; then T062/T063 and T066/T067 | T068 |
| US4 | T069, T070, T071; then T076 and T077 | T078 |
| US5 | T079, T080, T081; then T084/T085 and T087/T088 | T090 |
| US6 | T091, T092, T093; then T094/T095 and T097/T098 | T099 |
| US7 | T100, T101, T102, T103; then T108 and T109 | T110 |
| US9 | T111, T112, T113, T114; then T116/T117 and T120/T122/T123 | T124 |
| US10 | T125–T129; then T135 and T136 | T137–T138 |
| US11 | T139–T142; then T144/T145 and T150 | T152 |
| US12 | T153–T157; then T159/T160 and T164 | T165–T166 |

Cross-story parallelism after US1+US8: one stream may implement US3/US4, a second US5/US6, and a third US7; US9 and US10 can then run in parallel before US11/US12 integration.

## Implementation Strategy

### MVP first

1. Complete Phase 1 Setup.
2. Complete Phase 2 Foundation and prove ledger/runtime invariants.
3. Complete US1 only using mock providers and seeded point fixtures.
4. Stop and validate task identity, state, milestones, refresh/re-login, owner isolation, and user-safe failures.
5. Do not call this beta-ready until US8 points and at least one capability adapter also pass.

### Incremental beta delivery

1. **Control-plane MVP**: Setup + Foundation + US1.
2. **Safe retry/points**: US2 + US8.
3. **Capability waves**: US3/US4 first; US5/US6 next; each has an independent adapter flag and rollback.
4. **Model/cost operations**: US7 + US9.
5. **Quality closure**: US10 + US11.
6. **Unified administration**: US12 after all linked facts exist.
7. **Authority cutover**: Pass the Aggregate Production Release Gate, close T183, then perform shadow validation, legacy freeze and staged rollout.

### Release discipline

- Never enable new point enforcement while legacy monthly-token deduction is also authoritative.
- Never roll back by deleting or rewriting runtime/ledger facts; append correction/compensation and switch read/adapter flags.
- Never use OTel, LangSmith, seed/mock, or read-model availability as proof that a mandatory fact exists.
- Never expand a capability with unknown cost rate, missing eval/runbook owner, ledger imbalance, evidence gap, or unresolved P0/P1 gate.
- Keep REQ-062 payment, RMB pricing, purchase, cash refund, invoice, and commercial revenue out of all tasks.

## Notes

- Every task must be completed with the exact tests/evidence named in its phase.
- `[P]` means file-level parallelism only after preceding gates; it does not waive TDD order or review.
- Existing user changes in the dirty worktree must be preserved.
- `src/` is the canonical frontend root; do not recreate `frontend/src/`.
- The existing business productivity `modules/tasks` and `TaskRepository` are not AI task implementations and must remain separate.
- The existing WeChat `AgentTask` remains channel-specific; adapters reuse patterns and references rather than making it the universal table.
