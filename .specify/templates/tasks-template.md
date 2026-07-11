---

description: "Task list template for feature implementation"
---

# Tasks: [FEATURE NAME]

**Input**: Design documents from `/specs/[###-feature-name]/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Every behavior slice requires a regression/invariant test that fails without the
change or documented equivalent pre-change evidence. Bugs and R2/R3 deterministic behavior
retain RED/GREEN commands and results; all slices require passing verification evidence.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `src/`, `tests/` at repository root
- **InterCraft web app**: backend `backend/app/`, backend tests `backend/tests/`,
  frontend `src/`, canonical E2E `tests/e2e/`
- **Mobile**: `api/src/`, `ios/src/` or `android/src/`
- Paths shown below assume single project - adjust based on plan.md structure

<!--
  ============================================================================
  IMPORTANT: The tasks below are SAMPLE TASKS for illustration purposes only.

  The /speckit-tasks command MUST replace these with actual tasks based on:
  - User stories from spec.md (with their priorities P1, P2, P3...)
  - Feature requirements from plan.md
  - Entities from data-model.md
  - Endpoints from contracts/

  Tasks MUST be organized by user story so each story can be:
  - Implemented independently
  - Tested independently
  - Delivered as an MVP increment

  DO NOT keep these sample tasks in the generated tasks.md file.
  ============================================================================
-->

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [ ] T001 Create project structure per implementation plan
- [ ] T002 Initialize [language] project with [framework] dependencies
- [ ] T003 [P] Configure linting and formatting tools

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

Examples of foundational tasks (adjust based on your project):

- [ ] T004 Setup database schema and migrations framework
- [ ] T005 [P] Implement authentication/authorization framework
- [ ] T006 [P] Setup API routing and middleware structure
- [ ] T007 Create base models/entities that all stories depend on
- [ ] T008 Configure error handling and logging infrastructure
- [ ] T009 Setup environment configuration management
- [ ] TXXX Record exact resolved dependencies, support status, and time-bounded deviations
- [ ] TXXX Define framework-neutral service/context factories plus API/worker/CLI/graph composition roots
- [ ] TXXX Define per-process resources, session-per-concurrent-task, transaction and external-I/O boundaries
- [ ] TXXX Define authorization and tenant/resource isolation at API and worker/tool boundaries
- [ ] TXXX Define request/task/thread/execution correlation and mandatory audit facts
- [ ] TXXX Define database-enforced migration exclusion/ledger, resumable backfill, separate expand/contract releases, and tested backout or roll-forward
- [ ] TXXX [Background] Define atomic task+dispatch intent, idempotent dispatcher/reconciler, bounded admission, authoritative-write/effect fencing, and dead-letter
- [ ] TXXX [AI/Agent] Define typed graph state, reducers, durable checkpointer, interrupt/resume, live-version/retention matrix, decoder/upcasters, and N-1 rolling compatibility
- [ ] TXXX [AI/Agent] Define centralized model/tool adapters, timeouts, budgets, idempotency, and result reconciliation
- [ ] TXXX [Agent] Define immutable authorization receipts and fenced durable external-effect intents with bound-field/CAS tests
- [ ] TXXX Define per-store/provider/derived-copy privacy lifecycle, provenance deletion propagation and verification, and inherited operational controls

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - [Title] (Priority: P1) 🎯 MVP

**Goal**: [Brief description of what this story delivers]

**Independent Test**: [How to verify this story works on its own]

### Tests for User Story 1 (REQUIRED) ⚠️

> **NOTE: Define pre-change evidence first. Retain an actual RED run for bugs and R2/R3
> deterministic behavior; use an approved equivalent baseline for migrations/config/evaluations.**

- [ ] T010 [P] [US1] Contract test for [endpoint] in backend/tests/contract/test_[name].py
- [ ] T011 [P] [US1] Integration test for [user journey] in backend/tests/integration/test_[name].py
- [ ] TXXX [P] [US1] Authorization, validation, timeout, cancellation, and duplicate-delivery tests
- [ ] TXXX [P] [US1] [AI/Agent] Node/routing/checkpoint/interrupt-resume and malformed-output tests
- [ ] TXXX [P] [US1] [AI/Agent] Offline evaluation cases and release threshold
- [ ] TXXX [P] [US1] Capture applicable RED/equivalent pre-change evidence and GREEN commands/results

### Implementation for User Story 1

- [ ] T012 [P] [US1] Create [Entity1] model in backend/app/modules/[module]/models.py
- [ ] T013 [P] [US1] Create [Entity2] schema in backend/app/modules/[module]/schemas.py
- [ ] T014 [US1] Implement [Service] in backend/app/modules/[module]/service.py (depends on T012, T013)
- [ ] T015 [US1] Implement [endpoint/feature] in backend/app/modules/[module]/api.py
- [ ] T016 [US1] Add validation and error handling
- [ ] T017 [US1] Add logging for user story 1 operations
- [ ] TXXX [US1] Add metrics, traces, immutable audit facts, redaction, and rollback controls
- [ ] TXXX [US1] Complete risk-derived security, recovery, privacy, evaluation, and runbook evidence

**Checkpoint**: User Story 1 is independently functional and has all applicable risk,
security, recovery, privacy, evaluation, telemetry, and operational evidence.

---

## Phase 4: User Story 2 - [Title] (Priority: P2)

**Goal**: [Brief description of what this story delivers]

**Independent Test**: [How to verify this story works on its own]

### Tests for User Story 2 (REQUIRED) ⚠️

- [ ] T018 [P] [US2] Contract test for [endpoint] in backend/tests/contract/test_[name].py
- [ ] T019 [P] [US2] Integration test for [user journey] in backend/tests/integration/test_[name].py
- [ ] TXXX [P] [US2] Add applicable authorization/failure/recovery tests and RED/equivalent evidence

### Implementation for User Story 2

- [ ] T020 [P] [US2] Create [Entity] model in backend/app/modules/[module]/models.py
- [ ] T021 [US2] Implement [Service] in backend/app/modules/[module]/service.py
- [ ] T022 [US2] Implement [endpoint/feature] in backend/app/modules/[module]/api.py
- [ ] T023 [US2] Integrate with User Story 1 components (if needed)
- [ ] TXXX [US2] Complete risk-derived security, recovery, privacy, evaluation, telemetry, and runbook evidence

**Checkpoint**: User Stories 1 and 2 work independently and each has all applicable
risk controls and verification evidence.

---

## Phase 5: User Story 3 - [Title] (Priority: P3)

**Goal**: [Brief description of what this story delivers]

**Independent Test**: [How to verify this story works on its own]

### Tests for User Story 3 (REQUIRED) ⚠️

- [ ] T024 [P] [US3] Contract test for [endpoint] in backend/tests/contract/test_[name].py
- [ ] T025 [P] [US3] Integration test for [user journey] in backend/tests/integration/test_[name].py
- [ ] TXXX [P] [US3] Add applicable authorization/failure/recovery tests and RED/equivalent evidence

### Implementation for User Story 3

- [ ] T026 [P] [US3] Create [Entity] model in backend/app/modules/[module]/models.py
- [ ] T027 [US3] Implement [Service] in backend/app/modules/[module]/service.py
- [ ] T028 [US3] Implement [endpoint/feature] in backend/app/modules/[module]/api.py
- [ ] TXXX [US3] Complete risk-derived security, recovery, privacy, evaluation, telemetry, and runbook evidence

**Checkpoint**: All selected stories are independently functional and each has all
applicable risk controls and verification evidence.

---

[Add more user story phases as needed, following the same pattern]

---

## Phase N: Aggregate Validation & Release Readiness

**Purpose**: Aggregate controls already implemented in each slice. This phase MUST NOT be
the first implementation of security, recovery, privacy, evaluation, observability, or rollback.

- [ ] TXXX [P] Documentation updates in docs/
- [ ] TXXX Code cleanup and refactoring
- [ ] TXXX Performance optimization across all stories
- [ ] TXXX [P] Additional unit/regression tests required by uncovered risks in backend/tests/unit/ or src/**/*.test.ts(x)
- [ ] TXXX Verify every selected story already has its applicable risk controls and evidence
- [ ] TXXX Run aggregate fault/recovery and cross-story security regression suites
- [ ] TXXX [AI/Agent] Run aggregate offline eval and verify online feedback wiring already exists
- [ ] TXXX Verify inherited/capability SLOs, capacity, alerts, runbooks, staged rollout, and rollback
- [ ] TXXX Verify dependency support deviations and migration/checkpoint compatibility gates are closed
- [ ] TXXX Run quickstart.md validation

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3+)**: All depend on Foundational phase completion
  - User stories can then proceed in parallel (if staffed)
  - Or sequentially in priority order (P1 → P2 → P3)
- **Aggregate Validation (Final Phase)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (P2)**: Can start after Foundational (Phase 2) - May integrate with US1 but should be independently testable
- **User Story 3 (P3)**: Can start after Foundational (Phase 2) - May integrate with US1/US2 but should be independently testable

### Within Each User Story

- Regression/invariant tests or equivalent pre-change evidence MUST precede implementation
- Models before services
- Services before endpoints
- Core implementation before integration
- Story complete before moving to next priority

### Parallel Opportunities

- All Setup tasks marked [P] can run in parallel
- All Foundational tasks marked [P] can run in parallel (within Phase 2)
- Once Foundational phase completes, all user stories can start in parallel (if team capacity allows)
- All tests for a user story marked [P] can run in parallel
- Models within a story marked [P] can run in parallel
- Different user stories can be worked on in parallel by different team members

---

## Parallel Example: User Story 1

```bash
# Launch independent tests for User Story 1 together:
Task: "Contract test for [endpoint] in backend/tests/contract/test_[name].py"
Task: "Integration test for [user journey] in backend/tests/integration/test_[name].py"

# Launch all models for User Story 1 together:
Task: "Create [Entity1] model in backend/app/modules/[module]/models.py"
Task: "Create [Entity2] schema in backend/app/modules/[module]/schemas.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: Test User Story 1 independently
5. Deploy/demo if ready

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test independently → Deploy/Demo (MVP!)
3. Add User Story 2 → Test independently → Deploy/Demo
4. Add User Story 3 → Test independently → Deploy/Demo
5. Each story adds value without breaking previous stories

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: User Story 1
   - Developer B: User Story 2
   - Developer C: User Story 3
3. Stories complete and integrate independently

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Capture RED or constitution-approved equivalent pre-change evidence before implementing
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Avoid: vague tasks, same file conflicts, cross-story dependencies that break independence
