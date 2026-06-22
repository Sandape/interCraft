# Tasks: Error Coach 3-Correct E2E

**Input**: Design documents from `/specs/021-error-coach-e2e/`

**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/error-coach-api.md, quickstart.md

**Tests**: TDD approach — tests written FIRST, fail before implementation (Constitution III).

**Organization**: Tasks grouped by user story. Phase A (backend mock infra) → Phase B/C (E2E per story) → Phase D (config) → Phase E (004 closeout).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1=HAPPY, US2=EDGE, US3=ABORT)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Verify baseline state, ensure no stale mock mode env vars, confirm backend test infra.

- [x] T001 Verify clean baseline: run `cd backend && uv run pytest -q` and `npm run e2e -- tests/e2e/round-2/ --project=chromium` to confirm pre-021 green state; record baseline test counts in commit message
- [x] T002 [P] Confirm `backend/app/agents/llm_client.py` current `get_llm_client()` singleton logic (read file, no edit); note line numbers for hook insertion point in commit body
- [x] T003 [P] Confirm `tests/e2e/round-1/helpers/{auth,api,db}.ts` exports available for reuse (read files, list exported functions); document any gaps that require helper extension

---

## Phase 2: Foundational (Backend Mock Infrastructure — blocks all user stories)

**Purpose**: LLM mock client + factory hook + unit tests. MUST complete before any E2E spec can run.

**⚠️ CRITICAL**: No E2E work can begin until this phase is complete and unit tests pass.

### Tests for Foundational (TDD — write FIRST, must FAIL)

- [x] T004 [P] Write unit test `test_get_llm_client_returns_real_when_mock_mode_unset` in `backend/tests/test_llm_client_mock.py` — assert `get_llm_client()` returns `LLMClient` instance when `LLM_MOCK_MODE` env unset; must fail (ImportError on MockLLMClient) before T008
- [x] T005 [P] Write unit test `test_get_llm_client_returns_mock_when_mock_mode_set` in `backend/tests/test_llm_client_mock.py` — set `LLM_MOCK_MODE=1` + `LLM_MOCK_SCENARIO_PATH` to temp file, assert returns `MockLLMClient`; must fail before T008
- [x] T006 [P] Write unit test `test_mock_llm_client_reads_scenario_json` in `backend/tests/test_llm_client_mock.py` — write `{"evaluate_scores":[8,9],"hint_contents":{...}}` to temp file, assert `MockLLMClient.from_scenario_file` parses correctly; must fail before T009
- [x] T007 [P] Write unit test `test_mock_llm_client_evaluate_returns_score_sequence` in `backend/tests/test_llm_client_mock.py` — call `invoke(node_name="error_coach_evaluate")` 3 times, assert scores `[8, 9, 9]` returned in order; must fail before T009

### Implementation for Foundational

- [x] T008 Add `LLM_MOCK_MODE` hook (≤30 lines) to `get_llm_client()` in `backend/app/agents/llm_client.py` — when env var `LLM_MOCK_MODE=1`, return `MockLLMClient.from_scenario_file(env.LLM_MOCK_SCENARIO_PATH)`; else return existing `LLMClient()` singleton. Reset `_llm_client_singleton` to None before branch so env switch takes effect.
- [x] T009 Implement `MockLLMClient` class in `backend/app/agents/llm_client_mock.py` — `from_scenario_file(path)` classmethod loads JSON; `invoke(*, messages, node_name, user_id, thread_id, ...)` returns `LLMResponse` TypedDict:
  - `node_name="error_coach_evaluate"`: pop next score from `evaluate_scores` list, return content `{"score": N, "feedback": "mock"}`; list exhausted → return `{"score": 5, "feedback": "mock exhausted"}`
  - `node_name="error_coach_hint"`: read `current_hint_level` from messages context (or default "small"), return `hint_contents[level]`
  - other node_name: return empty string content
  - skip `_pre_deduct`/`_actual_adjust`/`_write_ai_message` (no DB writes)
  - emit structlog `llm.mock_invoke` event with node_name, user_id, thread_id
- [x] T010 [P] Add fallback unit test `test_mock_llm_client_falls_back_on_missing_scenario` in `backend/tests/test_llm_client_mock.py` — empty scenario path → `MockLLMClient` returns default `{"score":5}` on evaluate, empty string on hint; log warning
- [x] T011 Run `cd backend && uv run pytest tests/test_llm_client_mock.py -v` — all 5 unit tests must pass
- [x] T012 Run `cd backend && uv run pytest -q` — full backend suite must remain green (no regression)

**Checkpoint**: Mock infra ready. `LLM_MOCK_MODE=1` makes `get_llm_client()` return deterministic mock. E2E specs can now drive Error Coach subgraph without real DeepSeek calls.

---

## Phase 3: User Story 1 — HAPPY-01 3-Correct Path (Priority: P1) 🎯 MVP

**Goal**: E2E proves 3 consecutive correct answers end the session and decrement frequency by 1.

**Independent Test**: `npm run e2e -- tests/e2e/round-2/error-coach-3-correct.spec.ts -g "HAPPY-01"` passes.

### Tests for User Story 1 (E2E — written FIRST, must FAIL)

- [x] T013 [P] [US1] Write E2E fixture `tests/e2e/round-2/fixtures/error-coach-mock.ts` — export `ErrorCoachScenario` interface, `writeScenarioFile(scenario): string` function (writes JSON to `os.tmpdir()`, returns absolute path), and 3 preset scenarios: `HAPPY_SCENARIO` (`evaluate_scores:[8,9,9]`), `EDGE_SCENARIO` (`[5,9,9,9]`), `ABORT_SCENARIO` (`[9]`)
- [x] T014 [P] [US1] Write E2E spec skeleton `tests/e2e/round-2/error-coach-3-correct.spec.ts` — `test.describe('Error Coach 3-correct E2E')`, `beforeEach` logs in via `auth.ts`, seeds error question via `POST /api/v1/error-questions` (`frequency=3, status=fresh`), writes scenario file, sets `LLM_MOCK_SCENARIO_PATH` env (via process env or runtime config); `afterEach` deletes error question via `db.ts` and cleans temp file
- [x] T015 [US1] Write HAPPY-01 test case in `tests/e2e/round-2/error-coach-3-correct.spec.ts`:
  1. `POST /agents/error-coach/start` with `error_question_id` → assert `status=running`, `thread_id` non-empty
  2. `POST /agents/error-coach/{tid}/messages` content="useMemo caches value" → assert `correct_count=1`, `status=running`
  3. Second messages → assert `correct_count=2`, `status=running`
  4. Third messages → assert `correct_count=3`, `status=completed`
  5. `GET /agents/error-coach/{tid}/state` → assert `status=completed`, `correct_count=3`, `attempt_count=3`
  6. Query `error_questions` via `db.ts` (set `app.user_id` GUC) → assert `frequency=2` (was 3, decrement by 1), `status=fresh` (frequency > 0)
  - Test MUST FAIL at step 2 (mock not yet wired into playwright.config.ts) until T024 completes

### Implementation for User Story 1

- [x] T016 [US1] Run HAPPY-01 locally with `LLM_MOCK_MODE=1 LLM_MOCK_SCENARIO_PATH=/tmp/happy.json npm run e2e -- tests/e2e/round-2/error-coach-3-correct.spec.ts -g "HAPPY-01"` — confirm it passes after T024 (playwright config) lands; if fails on REST contract mismatch, cross-check against `specs/021-error-coach-e2e/contracts/error-coach-api.md`
- [x] T017 [US1] Capture evidence: run HAPPY-01 10× consecutively, record pass rate in `specs/021-error-coach-e2e/evidence/happy-01-stability.md`; must be ≥ 95% (SC-003)

**Checkpoint**: HAPPY-01 green + stable. MVP delivered. 004 SC-002 still `in_progress` until EDGE/ABORT also green.

---

## Phase 4: User Story 2 — EDGE-01 1-Wrong + 3-Correct (Priority: P2)

**Goal**: E2E proves hint escalation (small→medium at attempt_count=3) and that frequency still decrements by 1 when session ends after 4 rounds.

**Independent Test**: `npm run e2e -- tests/e2e/round-2/error-coach-3-correct.spec.ts -g "EDGE-01"` passes.

### Tests for User Story 2 (E2E — written FIRST, must FAIL)

- [x] T018 [US2] Write EDGE-01 test case in `tests/e2e/round-2/error-coach-3-correct.spec.ts`:
  1. start → assert `status=running`
  2. messages #1 (score=5 from scenario) → assert `correct_count=0`, `hint_level=small`
  3. messages #2 (score=9) → assert `correct_count=1`, `hint_level=small`
  4. messages #3 (score=9) → assert `correct_count=2`, `hint_level=medium` (attempt_count=3 triggers upgrade per `evaluate.py:64-68`)
  5. messages #4 (score=9) → assert `correct_count=3`, `status=completed`, `hint_level=medium`
  6. DB query → assert `frequency=2` (was 3, decrement by 1 per R-1 decision)
  - Test MUST FAIL until scenario file path wiring (T024) lands

### Implementation for User Story 2

- [x] T019 [US2] Run EDGE-01 locally, confirm pass; if hint_level assertion fails, verify `MockLLMClient` reads `current_hint_level` from messages context correctly (T009 may need adjustment to parse last assistant message for level hint)
- [x] T020 [US2] Capture EDGE-01 evidence in `specs/021-error-coach-e2e/evidence/edge-01-trace.md` — include mock scenario JSON, REST request/response sequence, DB before/after

**Checkpoint**: HAPPY-01 + EDGE-01 both green.

---

## Phase 5: User Story 3 — ABORT-01 User-Initiated Abort (Priority: P2)

**Goal**: E2E proves abort endpoint sets `session_aborted`, triggers `decrement_frequency` once, returns `correct_count_achieved`.

**Independent Test**: `npm run e2e -- tests/e2e/round-2/error-coach-3-correct.spec.ts -g "ABORT-01"` passes.

### Tests for User Story 3 (E2E — written FIRST, must FAIL)

- [x] T021 [US3] Write ABORT-01 test case in `tests/e2e/round-2/error-coach-3-correct.spec.ts`:
  1. start → assert `status=running`
  2. messages #1 (score=9) → assert `correct_count=1`
  3. `POST /agents/error-coach/{tid}/abort` → assert `status=aborted`, `correct_count_achieved=1`
  4. `GET /agents/error-coach/{tid}/state` → assert `status=completed` (session_aborted triggers END)
  5. DB query → assert `frequency=2` (was 3, abort triggers decrement_frequency per R-1)
  - Test MUST FAIL until T024 lands

### Implementation for User Story 3

- [x] T022 [US3] Run ABORT-01 locally, confirm pass; if `correct_count_achieved` is null instead of 1, verify `graph.abort()` returns `correct_count` from final state (may need to read `error_coach.py:114-120` and confirm `result.get("correct_count")` populates)
- [x] T023 [US3] Capture ABORT-01 evidence in `specs/021-error-coach-e2e/evidence/abort-01-trace.md`

**Checkpoint**: All 3 E2E cases green. 004 SC-002 ready to flip.

---

## Phase 6: Playwright Config Integration (Cross-Story Enabler)

**Purpose**: Wire `LLM_MOCK_MODE` into `playwright.config.ts` webServer so E2E specs don't require manual env var export.

- [x] T024 Modify `playwright.config.ts` — in the backend webServer config, inject `LLM_MOCK_MODE: '1'` into `env` field; keep `LLM_MOCK_SCENARIO_PATH` unset (each spec writes its own file and sets path via `process.env.LLM_MOCK_SCENARIO_PATH = path` before test runs — note: this requires backend to re-read env per request OR specs restart webServer; simpler approach: set path via a shared `tests/e2e/round-2/fixtures/error-coach-mock.ts` helper that writes to a fixed path `tests/e2e/round-2/fixtures/error-coach-scenarios/active.json` and config sets `LLM_MOCK_SCENARIO_PATH` to that fixed path). Choose the fixed-path approach to avoid webServer restarts.
- [x] T025 [P] Update `tests/e2e/round-2/fixtures/error-coach-mock.ts` `writeScenarioFile` to write to fixed path `tests/e2e/round-2/fixtures/error-coach-scenarios/active.json` (overwrite each call); return that path. Add `cleanupScenarioFile()` helper for `afterEach`.
- [x] T026 Run full round-2 suite: `npm run e2e -- tests/e2e/round-2/ --project=chromium` — assert ≥ 21 tests pass (18 existing + 3 new), 0 fail, 0 skip (SC-005)

---

## Phase 7: 004 SC-002 Closeout & Spec Updates

**Purpose**: Flip 004 SC-002 to done, update 021 requirements-status, sync README.

- [x] T027 [P] Update `specs/004-phase5-agent-subgraphs/requirements-status.md` — SC-002 row: `in_progress` → `done`; Evidence column: `tests/e2e/round-2/error-coach-3-correct.spec.ts (HAPPY-01, EDGE-01, ABORT-01)`; Notes: remove "requires a live-LLM scoring loop" text
- [x] T028 [P] Update `specs/README.md` 004 row Notes — remove "SC-002 (Error Coach 3-correct + frequency decrement E2E) requires a live-LLM scoring loop; code is complete and production-ready, only deterministic E2E coverage is pending. Does not block trial launch."; replace with "All 41 rows done. Round-2 E2E (error-coach-3-correct.spec.ts) closes SC-002."
- [x] T029 [P] Update `specs/README.md` "Trial-Launch Readiness" section — change "Remaining gap: 004 SC-002..." line to "All gaps closed. v1 trial-launch baseline fully green."
- [x] T030 Update `specs/021-error-coach-e2e/requirements-status.md` — flip all FR-001..FR-032 and SC-001..SC-006 rows to `done` with evidence paths
- [x] T031 Run `git diff master -- backend/app/agents/nodes/error_coach/ backend/app/agents/graphs/error_coach.py backend/app/api/v1/agents_error_coach.py backend/app/services/error_coach_service.py` — assert empty output (SC-006 backend zero business-logic diff)
- [x] T032 Run `git diff master -- backend/app/agents/llm_client.py | wc -l` — assert ≤ 30 lines added (SC-006 mock hook size)

---

## Phase 8: Polish & Cross-Cutting Concerns

- [x] T033 [P] Run `npm run typecheck` — confirm frontend typecheck clean (no E2E TS errors)
- [x] T034 [P] Run `cd backend && uv run pytest -q` — full backend suite green (no regression from mock hook)
- [x] T035 [P] Run `npm run e2e -- --project=chromium` — full canonical E2E suite green (round-1 + round-2 + feature-level)
- [x] T036 [P] Document 004 spec vs code semantic divergence in `specs/021-error-coach-e2e/evidence/004-semantic-divergence.md` — record that 004 acceptance #2 / FR-014 say "每次答对减 frequency" but code decrements once per session end; recommend future feature 025 to align spec with code (or vice versa)
- [x] T037 [P] Run quickstart.md validation: execute all commands in `specs/021-error-coach-e2e/quickstart.md` sections 1-5, confirm expected outputs
- [x] T038 Commit changes on branch `021-error-coach-e2e`; PR body references spec.md, plan.md, research.md; PR description includes evidence file links

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories (mock infra must exist before E2E)
- **User Stories (Phase 3-5)**: All depend on Phase 2 completion
  - US1 (HAPPY) is MVP — complete first
  - US2 (EDGE) and US3 (ABORT) can run in parallel after US1 (different test cases, same spec file — but careful: same spec file means parallel write conflicts; recommended sequential)
- **Playwright Config (Phase 6)**: Depends on Phase 2 (mock infra) + at least US1 spec existing; enables all 3 E2E cases to actually run
- **Closeout (Phase 7)**: Depends on all 3 E2E cases green (Phase 3+4+5 + Phase 6)
- **Polish (Phase 8)**: Depends on Closeout

### User Story Dependencies

- **US1 (HAPPY-01)**: Depends on Phase 2 (mock infra) + Phase 6 (playwright config). No dependency on US2/US3.
- **US2 (EDGE-01)**: Depends on Phase 2 + Phase 6. Same spec file as US1 — write after US1 to avoid merge conflicts.
- **US3 (ABORT-01)**: Depends on Phase 2 + Phase 6. Same spec file — write after US2.

### Within Each User Story

- E2E test case written FIRST (must fail)
- Run test case, confirm failure reason is correct (mock not wired / scenario not found)
- After Phase 6 lands, re-run test case → should pass
- Capture evidence (stability run, trace doc)

### Parallel Opportunities

- T002, T003 (Phase 1 read-only verification) — parallel
- T004-T007 (Phase 2 unit tests) — parallel (different test functions, same file — write sequentially to avoid conflict, but can be marked [P] for conceptual independence)
- T027, T028, T029 (Phase 7 doc updates) — parallel (different files)
- T033, T034, T035, T036, T037 (Phase 8 polish) — parallel

---

## Parallel Example: Phase 2 Unit Tests

```bash
# Launch all unit tests for mock client together (same file, write sequentially but conceptually parallel):
Task: "test_get_llm_client_returns_real_when_mock_mode_unset in backend/tests/test_llm_client_mock.py"
Task: "test_get_llm_client_returns_mock_when_mock_mode_set in backend/tests/test_llm_client_mock.py"
Task: "test_mock_llm_client_reads_scenario_json in backend/tests/test_llm_client_mock.py"
Task: "test_mock_llm_client_evaluate_returns_score_sequence in backend/tests/test_llm_client_mock.py"
```

---

## Implementation Strategy

### MVP First (US1 HAPPY-01 Only)

1. Complete Phase 1: Setup (verify baseline)
2. Complete Phase 2: Foundational (mock infra + unit tests) — CRITICAL blocks everything
3. Complete Phase 6 partial: wire playwright.config.ts (T024-T025) — needed for E2E to run
4. Complete Phase 3: US1 HAPPY-01 (T013-T017)
5. **STOP and VALIDATE**: HAPPY-01 passes 10× with ≥95% stability
6. Demo to user — MVP delivered (SC-002 happy path covered)

### Incremental Delivery

1. Setup + Foundational → mock infra ready
2. + Phase 6 + US1 → HAPPY-01 green → MVP demo
3. + US2 → EDGE-01 green → hint escalation covered
4. + US3 → ABORT-01 green → abort path covered
5. + Phase 7 → 004 SC-002 flipped, README synced
6. + Phase 8 → full suite green, PR ready

### Parallel Team Strategy

Solo developer recommended (spec file conflicts). If multiple devs:
- Dev A: Phase 2 mock infra (T004-T012)
- Dev B: Phase 6 playwright config (T024-T026) — can start in parallel with Phase 2 since config change is independent of mock client code
- After both merge: Dev A → US1, Dev B → US2 (sequential due to same spec file)

---

## Notes

- All E2E test cases MUST fail before Phase 6 lands (mock not wired) — this is the TDD signal
- If HAPPY-01 passes before T024, it means mock is leaking real LLM calls — investigate immediately
- `LLM_MOCK_SCENARIO_PATH` uses fixed path `tests/e2e/round-2/fixtures/error-coach-scenarios/active.json` to avoid webServer restart per test
- 004 spec vs code divergence (R-1) is documented in `evidence/004-semantic-divergence.md` (T036), NOT fixed in 021
- Backend business logic files (nodes/graphs/api/service) MUST show empty git diff vs master (SC-006)
- Commit after each task or logical group; PR requires user review before merge
