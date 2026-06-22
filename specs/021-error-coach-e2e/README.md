# 021 Error Coach 3-Correct E2E

Status: `planned`

Source of truth: [spec.md](./spec.md)

This feature closes the last remaining gap in the v1 trial-launch baseline:
004 SC-002 (Error Coach 3-correct + frequency decrement E2E). The M17 Error
Coach subgraph code is complete and production-ready, but deterministic E2E
coverage was never authored. Feature 021 adds that coverage without changing
backend business logic.

## Implementation Context

| Area | Link |
|---|---|
| Source of truth | [spec.md](./spec.md) |
| Parent spec | [../004-phase5-agent-subgraphs/spec.md](../004-phase5-agent-subgraphs/spec.md) (SC-002) |
| Requirement status | [requirements-status.md](./requirements-status.md) |
| Parent status | [../004-phase5-agent-subgraphs/requirements-status.md](../004-phase5-agent-subgraphs/requirements-status.md) |

## Contracts

- [error-coach-api.md](./contracts/error-coach-api.md) — REST contract snapshot for `/agents/error-coach/*` (unchanged from 004, included for E2E reference)

## Related Code (read-only — do not modify)

| Subsystem | Current Paths |
|---|---|
| Error Coach graph | `backend/app/agents/graphs/error_coach.py` |
| Error Coach nodes | `backend/app/agents/nodes/error_coach/` (fetch_question, hint_ladder, evaluate, loop_or_finish) |
| Error Coach REST | `backend/app/api/v1/agents_error_coach.py` |
| Error Coach service | `backend/app/services/error_coach_service.py` (`decrement_frequency`) |
| LLM client | `backend/app/agents/llm_client.py` (potential mock injection point) |
| Frontend ErrorBook UI | `src/pages/ErrorBook.tsx`, `src/components/error-book/` |

## Related Tests

- New E2E: `tests/e2e/round-2/error-coach-3-correct.spec.ts`
- New fixture: `tests/e2e/round-2/fixtures/error-coach-mock.ts` (or extension of `tests/e2e/fixtures/mock-llm.ts`)
- Reused helpers: `tests/e2e/round-1/helpers/{auth,api,db}.ts`
- Regression guard: `tests/e2e/round-2/interview-mock-llm.spec.ts` (must stay green)

## Non-Goals

- Do not change M17 subgraph behavior (nodes, graph, service).
- Do not fix defects in `decrement_frequency` — if found, open a separate feature.
- Do not add WebSocket streaming to Error Coach (REST is the stable contract).
- Do not cover real-LLM mode (manual verification only).
- Do not touch other Agent subgraphs (M16/M18/M19).
