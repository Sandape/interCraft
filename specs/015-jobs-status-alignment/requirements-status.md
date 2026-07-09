# 015 Requirement Status

Status reconciled against code on 2026-06-22. All 4 user stories and 10
FR are implemented; E2E covers happy path + 409 failure.

## User Stories

| Requirement | Summary | Status | Evidence | Notes |
|---|---|---|---|---|
| US1 | Advance a job through its real lifecycle | done | `src/pages/Jobs.tsx:53` fetches `GET /jobs/transitions`; status menu rendered from transitions array | — |
| US2 | Filter the job list by real status | done | `src/pages/Jobs.tsx:27-33` 7 status tabs + `all`; `:180` count badges | — |
| US3 | See accurate stats including `withdrawn` | done | `src/pages/Jobs.tsx:145,151,157,163` 5 stat tiles (total/active/offer/rejected/withdrawn — separated) | — |
| US4 | Recover from an invalid transition with inline feedback | done | `src/pages/Jobs.tsx` 409 handling + `data-testid="job-row-retry"` | `tests/e2e/jobs-status-alignment.spec.ts` covers 409 path |

## Functional Requirements

| Requirement | Summary | Status | Evidence | Notes |
|---|---|---|---|---|
| FR-001 | status tabs match backend `JobStatus` enum exactly | done | `src/pages/Jobs.tsx:27-33` (applied/test/oa/hr/offer/rejected/withdrawn + all) | — |
| FR-002 | count badge on every tab (0 allowed, must display 0) | done | `src/pages/Jobs.tsx:180` `data-testid="status-tab-count-${t.key}"` | — |
| FR-003 | row "advance" replaced with status menu from transitions | done | `src/pages/Jobs.tsx:53,68` transitions fetch + menu derive | — |
| FR-004 | never post a transition not in the transitions response | done | `src/pages/Jobs.tsx` menu entries filtered by transitions array | — |
| FR-005 | 5 stat tiles in lifecycle order; rejected ≠ withdrawn | done | `src/pages/Jobs.tsx:145,151,157,163` | — |
| FR-006 | keep row visible until server confirms success | done | `src/pages/Jobs.tsx` optimistic update + row-leaves-tab on success | — |
| FR-007 | 409 inline error + `重试` button (`job-row-retry`) | done | `src/pages/Jobs.tsx` `data-testid="job-row-retry"` | — |
| FR-008 | tab order: applied → test → oa → hr → offer → rejected → withdrawn | done | `src/pages/Jobs.tsx:27-33` literal order | — |
| FR-009 | backend exposes `GET /api/v1/jobs/transitions` | done | `backend/app/modules/jobs/api.py:25-39` | — |
| FR-010 | frontend fetches transitions once per session (staleTime: Infinity) + fallback banner | done | `src/pages/Jobs.tsx:53,125-127` `transitions-stale-banner` | — |

## Success Criteria

| Requirement | Summary | Status | Evidence | Notes |
|---|---|---|---|---|
| SC-001 | applied → offer in 3 clicks without 409 | done | `tests/e2e/jobs-status-alignment.spec.ts` | — |
| SC-002 | tab counts match `/jobs/stats` | done | `src/pages/Jobs.tsx` count derivation from stats | — |
| SC-003 | 409 shown inline within one interaction, never silent rollback | done | `tests/e2e/jobs-status-alignment.spec.ts` failure path | — |
| SC-004 | E2E covers happy path + 409 failure on same row | done | `tests/e2e/jobs-status-alignment.spec.ts` | — |
| SC-005 | 7 real statuses as tabs; `screening`/`interview` no longer appear | done | `src/pages/Jobs.tsx:27-33` | grep finds no `screening`/`interview` tab literals |

## Status Roll-up

- Total: 4 US + 10 FR + 5 SC = 19 rows.
- `done`: 19 rows.
