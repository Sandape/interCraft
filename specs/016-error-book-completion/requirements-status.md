# 016 Requirement Status

Status reconciled against code on 2026-06-22. All 3 user stories and 14
FR are implemented; E2E spec covers the full review + leave-return flow.

## User Stories

| Requirement | Summary | Status | Evidence | Notes |
|---|---|---|---|---|
| US1 | 记录并管理错题 | done | `backend/app/modules/errors/api.py` (list/get/create/patch/delete); `backend/app/modules/errors/service.py` FSM | — |
| US2 | 复习推进与掌握状态 | done | `backend/app/modules/errors/api.py:101` `POST /{id}/recall`; `:92` `POST /{id}/reset`; `service.py:16-26` frequency/status matrix | — |
| US3 | 删除、异常和重进恢复 | done | `backend/app/modules/errors/api.py:82` `DELETE /{id}`; `tests/e2e/error-book-completion.spec.ts` | — |

## Functional Requirements

| Requirement | Summary | Status | Evidence | Notes |
|---|---|---|---|---|
| FR-001 | list only own non-deleted with filters + bounded limit | done | `backend/app/modules/errors/api.py` list endpoint; `repository.py:24-41` (status/dimension/frequency/source filters) | — |
| FR-002 | create with question/answer/reference/score/tags/dimension | done | `backend/app/modules/errors/schemas.py` `CreateErrorQuestionInput` | — |
| FR-003 | validate input (dimension enum, text length ≤2000, score, frequency/state) | done | `backend/app/modules/errors/schemas.py` Pydantic validators; `service.py:22-26` frequency constraints | — |
| FR-004 | view single non-deleted own question | done | `backend/app/modules/errors/api.py` `GET /{id}` | — |
| FR-005 | partial update without resending unchanged fields | done | `backend/app/modules/errors/api.py` `PATCH /{id}` | — |
| FR-006 | recall action atomically decreases frequency + updates status + last_practiced_at | done | `backend/app/modules/errors/api.py:101-107`; `service.py` `recall()` | — |
| FR-007 | recall frequency/status mapping (3→fresh, 1-2→practicing, 0→mastered) | done | `backend/app/modules/errors/service.py:3,16-26` | — |
| FR-008 | reset only from mastered to fresh/frequency=3 | done | `backend/app/modules/errors/service.py:18` `"mastered": {"fresh", "archived"}` (fresh via reset) | — |
| FR-009 | soft-delete + exclude from default list/detail | done | `backend/app/modules/errors/api.py:82-88`; `repository.py` filters `deleted_at IS NULL` | — |
| FR-010 | consistent user-safe error responses (validation/transition/missing/deleted/cross-user) | done | `backend/app/modules/errors/service.py` raises domain exceptions; cross-user returns 404 via RLS | — |
| FR-011 | create/search/filter/select/recall/reset/delete from page without broken text/layout/hook errors | done | `src/pages/ErrorBook.tsx` full UI; `tests/e2e/error-book-completion.spec.ts` | — |
| FR-012 | loading/empty/no-results/success/error states for primary workflows | done | `src/pages/ErrorBook.tsx` (loading spinners, empty state, no-results, success toast, error banner) | — |
| FR-013 | restore persisted list/item state after navigation away and back | done | React Query cache + `tests/e2e/error-book-completion.spec.ts` leave-return flow | — |
| FR-014 | preserve Error Coach entry — show start action only when frequency > 0 | done | `src/pages/ErrorBook.tsx` Coach CTA gating on frequency | — |

## Success Criteria

| Requirement | Summary | Status | Evidence | Notes |
|---|---|---|---|---|
| SC-001 | create + find new question in < 60s | done | `tests/e2e/error-book-completion.spec.ts` | — |
| SC-002 | 100% valid recall attempts produce expected transition | done | `backend/app/modules/errors/service.py:16-26`; `tests/e2e/error-book-completion.spec.ts` | — |
| SC-003 | invalid create/recall/reset/deleted/cross-user leave data unchanged | done | `backend/app/modules/errors/service.py` raises before mutation; RLS blocks cross-user | — |
| SC-004 | page renders without console errors or broken Chinese text | done | `src/pages/ErrorBook.tsx` zh-CN copy; `tests/e2e/error-book-completion.spec.ts` | — |
| SC-005 | E2E proves normal review flow + interrupted leave-return | done | `tests/e2e/error-book-completion.spec.ts` | — |

## Status Roll-up

- Total: 3 US + 14 FR + 5 SC = 22 rows.
- `done`: 22 rows.
