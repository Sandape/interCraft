# 020 Fix Round-1 Defects

Status: `planned`

Source of truth: [spec.md](./spec.md)

This feature fixes the 12 active defects that Round-1 E2E testing surfaced
in `019-cross-module-linking`. It does not introduce new product behavior;
it restores the user stories that 019 promised but the implementation never
fully delivered, and it hardens the contract/UI boundaries that 019 left
inconsistent.

## Implementation Context

| Area | Link |
|---|---|
| Source of truth | [spec.md](./spec.md) |
| Tasks | [tasks.md](./tasks.md) |
| Data model | [data-model.md](./data-model.md) |
| Requirement status | [requirements-status.md](./requirements-status.md) |
| Defect report (Round-1) | [../../docs/testing/round-1/03-defect-report.md](../../docs/testing/round-1/03-defect-report.md) |
| Round-1 summary | [../../docs/testing/round-1/04-summary-report.md](../../docs/testing/round-1/04-summary-report.md) |
| Round-1 acceptance | [../../docs/testing/round-1/05-acceptance-checklist.md](../../docs/testing/round-1/05-acceptance-checklist.md) |
| Parent feature | [../019-cross-module-linking/spec.md](../019-cross-module-linking/spec.md) |

## Contracts

- [error-questions-source.md](./contracts/error-questions-source.md) — D-002 / D-003 / D-004 / D-013
- [resume-branches-path.md](./contracts/resume-branches-path.md) — D-005
- [jobs-frontend-integration.md](./contracts/jobs-frontend-integration.md) — D-014 / D-016 / D-017

## Defect → Requirement Index

| Defect | Round-1 failure cases | Requirement | Priority |
|---|---|---|---|
| D-002 | S5 | FIX-001 | P0 |
| D-003 | contract drift | FIX-004 | P1 |
| D-004 | contract drift | FIX-005 | P1 |
| D-005 | contract drift | FIX-006 | P1 |
| D-006 | S4 / C1 | FIX-007 | P1 |
| D-008 | G1 (chain) | FIX-011 | P2 |
| D-009 | D5 | FIX-008 | P2 |
| D-010 | new (edge suite) | FIX-012 | P3 |
| D-013 | D4 | FIX-003 | P1 |
| D-014 | A1, B1, B4, C1, C6 | FIX-002 | P1 |
| D-016 | E4 | FIX-009 | P2 |
| D-017 | A2 | FIX-010 | P2 |

## Related Tests

- Round-1 E2E: `tests/e2e/round-1/` (8 spec files, 43 cases)
- Round-2 E2E (to be added): `tests/e2e/round-2/`
  - `tests/e2e/round-2/contract-parity.spec.ts` (CONTRACT-01..06)
  - `tests/e2e/round-2/auth-guard.spec.ts` (GUARD-01..04)
  - `tests/e2e/round-2/interview-mock-llm.spec.ts` (MOCK-01..03)
  - `tests/e2e/round-2/pydantic-strictness.spec.ts` (STRICT-01..02)
  - `tests/e2e/round-2/full-edge-r2.spec.ts` (EDGE-06)

## Related Code

| Subsystem | Current Paths |
|---|---|
| Error Book backend | `backend/app/modules/errors/` (api.py, service.py, schemas.py, repo.py) |
| Interview backend | `backend/app/modules/interviews/api.py` |
| Jobs backend | `backend/app/modules/jobs/` (no change in 020) |
| Resume branches backend | `backend/app/modules/resumes/` (no change in 020) |
| Frontend Jobs UI | `src/pages/Jobs.tsx`, `src/components/jobs/JobsDetailPanel.tsx` |
| Frontend ErrorBook UI | `src/pages/ErrorBook.tsx` |
| Frontend router | `src/router.tsx` |
| Frontend repository | `src/repositories/ErrorQuestionRepository.ts` |
| Frontend mutations | `src/hooks/useErrorQuestionMutations.ts` |
| Frontend interview live | `src/pages/InterviewLive.tsx` |
| E2E test infrastructure | `tests/e2e/fixtures/mock-llm.ts`, `tests/e2e/round-1/helpers/{auth,api,db}.ts` |
| DB query wrapper | `backend/scripts/dbq.py` (D-015 already resolved in round-1) |

## Do Not Use As Source

- Removed legacy module documents for implementation decisions.
- Round-1 E2E results as the **only** source of truth for behavior — 020
  re-verifies with the same test names plus Round-2 contract tests.
- Any `frontend/src` paths in old generated plans. The current frontend root
  is `src/`; see [docs/architecture/source-map.md](../../docs/architecture/source-map.md).
