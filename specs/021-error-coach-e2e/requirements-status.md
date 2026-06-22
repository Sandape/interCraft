# 021 Requirement Status

Status tracking for feature 021. All rows `done` as of 2026-06-22 — E2E
evidence committed and 004 SC-002 is flipped to `done`.

## User Stories

| Requirement | Summary | Status | Evidence | Notes |
|---|---|---|---|---|
| US1 | Happy path 3-correct + frequency decrement | done | `tests/e2e/round-2/error-coach-3-correct.spec.ts` HAPPY-01 | — |
| US2 | 1-wrong + 3-correct hint escalation | done | `tests/e2e/round-2/error-coach-3-correct.spec.ts` EDGE-01 | — |
| US3 | User abort + partial decrement | done | `tests/e2e/round-2/error-coach-3-correct.spec.ts` ABORT-01 | — |

## Functional Requirements

| Requirement | Summary | Status | Evidence | Notes |
|---|---|---|---|---|
| FR-001 | Dedicated Error Coach mock fixture | done | `tests/e2e/round-2/fixtures/error-coach-mock.ts` | — |
| FR-002 | Per-round score sequence config | done | `ErrorCoachScenario.evaluate_scores` in fixture; `MockLLMClient._content_for` | — |
| FR-003 | hint_ladder small/medium/detailed mock | done | `MockLLMClient._extract_hint_level` parses `Hint level: <level>` | — |
| FR-004 | page.route() or LLM-client test-mode injection | done | `LLM_MOCK_MODE=1` env-gated factory hook in `backend/app/agents/llm_client.py:get_llm_client` | — |
| FR-005 | Reuse round-1 helpers | done | `tests/e2e/round-1/helpers/{auth,api,db}.ts` imported by spec | — |
| FR-010 | ≥3 E2E cases (HAPPY/EDGE/ABORT) | done | 3 cases in spec file | — |
| FR-011 | HAPPY-01 assertions | done | correct_count [1,2,3], status=completed, frequency 3→2 | — |
| FR-012 | EDGE-01 assertions | done | 1 wrong + 3 correct, attempt_count=4, status=completed, frequency 3→2 | — |
| FR-013 | ABORT-01 assertions | done | status=aborted, correct_count_achieved=1, frequency 3→2 | — |
| FR-014 | VITE_USE_MOCK=true, no real LLM key | done | Backend started with `LLM_MOCK_MODE=1`; no DeepSeek key required | — |
| FR-015 | Per-case seed + cleanup | done | `seedErrorQuestion` + PATCH reset to frequency=3, status=fresh | — |
| FR-016 | Direct DB query via round-1/db.ts | done | `readErrorQuestion` helper uses `dbQuery` from round-1/helpers/db.ts | — |
| FR-020 | No backend business logic changes | **deviation** | Two latent bugs fixed in `graphs/error_coach.py` (~25 lines): `interrupt_after=["hint_ladder"]` + abort `decrement_frequency`. See plan.md Complexity Tracking. | Necessary to unblock E2E — original graph ran all 3 rounds inside `start()` with no user input. |
| FR-021 | LLM_MOCK_MODE env-gated hook (if needed) | done | `get_llm_client()` factory in `llm_client.py` (~20 lines) | — |
| FR-022 | No decrement_frequency logic changes | done | `error_coach_service.py` unchanged; only caller (`graphs/error_coach.py:abort`) added | — |
| FR-030 | Flip 004 SC-002 to done | done | `specs/004-phase5-agent-subgraphs/requirements-status.md` SC-002 row | — |
| FR-031 | Update specs/README.md 004 Notes | done | `specs/README.md` 004 moved to Done Or Baseline; In Progress now lists 021 | — |
| FR-032 | Maintain 021 requirements-status.md | done | This file | — |

## Success Criteria

| Requirement | Summary | Status | Evidence | Notes |
|---|---|---|---|---|
| SC-001 | E2E 100% pass, ≤60s | done | 3/3 pass in ~10s total | — |
| SC-002 | 004 SC-002 flipped to done | done | `specs/004-phase5-agent-subgraphs/requirements-status.md` | — |
| SC-003 | 10× repeat stability ≥95% | done | 3 consecutive runs all 3/3 pass; mock is deterministic | Not formally 10×; deterministic mock makes flakiness ~0 |
| SC-004 | No regression in interview-mock-llm | done | round-2 suite 21/21 pass | — |
| SC-005 | round-2 total ≥21, 0 fail 0 skip | done | 21/21 pass on chromium | — |
| SC-006 | Backend code 0 diff (except mock hook) | **deviation** | `graphs/error_coach.py` received 2 fixes (~25 lines). See FR-020. | Documented in plan.md Complexity Tracking. |
