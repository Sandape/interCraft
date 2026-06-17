# Implementation Plan: Fix Round-1 Defects

**Branch**: `020-fix-round-1-defects` | **Date**: 2026-06-17 | **Spec**: [spec.md](./spec.md) | **Tasks**: [tasks.md](./tasks.md)

**Input**: 12 active defects from Round-1 E2E testing
(`docs/testing/round-1/03-defect-report.md`) on the 019 cross-module-linking
feature. This plan covers the **repair** of those defects, not new product
behavior.

**Note**: This is a defect-fix feature. It is the 020 successor to 019 and
inherits all of 019's contracts; it only modifies the parts of the
implementation that round-1 E2E showed were broken. No new module is
introduced, no DB migration is added (the columns are already in place from
019).

---

## Summary

Close all 12 active defects surfaced by `tests/e2e/round-1/` (34 passed / 9
failed / 0 skipped → 43 passed / 0 failed / 0 skipped) and add a new
Round-2 E2E suite (`tests/e2e/round-2/`, 11 new cases) that locks down the
contract parity, auth-guard, mock-LLM, and Pydantic-strictness guarantees
that the round-1 failures revealed were not covered.

The defects cluster into four shapes:

1. **Backend Pydantic silent drops** — `CreateErrorQuestionInput` lacks
   `source_session_id` and `source_question_id`; Pydantic v2 silently drops
   the unknown fields. (D-002)
2. **Component / route wiring gaps** — `JobsDetailPanel` exists but is
   never imported; `/jobs` has no auth guard; `headcount` has no
   `type="number"` / `min="1"`. (D-014, D-016, D-017)
3. **Contract drift** — `clear-source` method (POST → PATCH), `?source=`
   filter naming, `/resume-branches` path. (D-003, D-004, D-005)
4. **Service / infrastructure** — `clear-source` not idempotent; LLM mock
   not wired; 100-char UTF-8 boundary not covered. (D-013, D-008, D-010)

The technical path is **edit-in-place** for 5 backend files and 4 frontend
files, plus 3 doc files (019 contract corrections), plus 1 new
`backend/tests/unit/test_errors_schemas_strictness.py` and 5 new
`tests/e2e/round-2/*.spec.ts` files. No new dependencies; the existing
`backend/scripts/dbq.py` (D-015 already fixed in round-1) and Playwright
MCP service are sufficient.

---

## Technical Context

**Language/Version** (inherited from 019):
- Backend: Python 3.11+ (pyproject.toml locked)
- Frontend: TypeScript 5.6 strict mode

**Primary Dependencies**: **No new dependencies.**
- Backend: alembic / pydantic v2 / SQLAlchemy 2.0 async / FastAPI / openai SDK
- Frontend: React 18 / Vite / TailwindCSS / react-router-dom / @tanstack/react-query / zustand
- Testing: pytest + pytest-asyncio (backend) / vitest + @testing-library/react (frontend) / Playwright (E2E)

**Storage**:
- **No new DB migration**. All 12 defects are about behavior or wiring; the
  columns needed (`error_questions.source_session_id`, `source_question_id`,
  `jobs` 5 fields, `interview_sessions.job_id`) are already in the
  production DB from 019.
- The Pydantic write-schema gap in `CreateErrorQuestionInput` is a code
  fix only — no schema change.

**Testing**:
- Backend unit (new): `backend/tests/unit/test_errors_schemas_strictness.py`
  — Pydantic write schema accepts `source_session_id` / `source_question_id`
  on POST and round-trips them in the response.
- Backend integration (new):
  `backend/tests/integration/test_clear_source_idempotent.py` — second
  `clear-source` returns 400 `source_already_cleared`.
- Frontend E2E rerun: `tests/e2e/round-1/*.spec.ts` (43 cases) — every
  previously-failing case must now pass; no regression in passing cases.
- Frontend E2E new: `tests/e2e/round-2/*.spec.ts` (11 cases in 5 files) —
  contract-parity, auth-guard, mock-LLM, pydantic-strictness, edge-boundary.
- Test infrastructure: existing `tests/e2e/fixtures/mock-llm.ts` extended
  with `page.routeWebSocket` wiring.

**Target Platform**: (unchanged from 019) Linux container / Windows + WSL2
+ uv for backend; modern desktop browsers (Chrome/Edge/Firefox/Safari last
2 majors) for frontend.

**Project Type**: web (frontend + backend; Phase 1).

**Performance Goals** (no regression from 019):
- Round-1 E2E rerun time ≤ 40 s (currently 34.0 s on MCP).
- Round-2 E2E time ≤ 25 s (estimated; 11 cases).
- `clear-source` first call 200 ≤ 200 ms; second call 400 ≤ 100 ms.

**Constraints**:
- **Inherit 019 constraints**: do not modify 014/016/006/Phase 4 internal
  logic; do not change the 5 new job field semantics, types, or defaults;
  do not change the `AUTO_ERROR_THRESHOLD = 6` constant.
- **Constitution Test-First**: every change in this plan runs the
  associated round-1 / round-2 test **before** the code change to confirm
  the test fails for the right reason, then again after to confirm it
  passes.
- **No new dependency, no new top-level module.** The 020 fix lives in
  the same files 019 modified, plus 5 new test files.
- **Backend round-trip constraint**: the response of
  `POST /api/v1/error-questions` must include the same `source_*` fields
  the request sent (Pydantic strictness is a runtime contract here, not a
  schema constraint).
- **No breaking change to localStorage token strategy** — the auth-guard
  fix uses `localStorage.getItem('access_token')` (D-016 explicitly scopes
  to this storage; cookie migration is a separate hardening feature).

**Scale/Scope**:
- Defect rows: 12 active (P0×1, P1×6, P2×4, P3×1) + 3 archived
  (D-001, D-011, D-015 — already fixed in round-1).
- Files touched: 5 backend (`errors/{api,service,schemas,repo}.py`,
  `interviews/api.py`) + 4 frontend (`pages/Jobs.tsx`, `pages/ErrorBook.tsx`,
  `router.tsx`, `pages/InterviewLive.tsx`) + 3 doc (019 contracts).
- New test files: 1 backend unit + 1 backend integration + 5 frontend
  E2E specs (round-2).
- Total Round-1 + Round-2 cases after fix: 43 + 11 = 54.

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| 原则 | 本 plan 合规性 | 说明 |
|---|---|---|
| **I. Library-First** | ✅ 合规 | 不新建顶层模块;所有修复落在 019 已有的 5 个后端文件 + 4 个前端文件 + 3 个文档;`tests/e2e/round-2/` 是新测试根但与 `tests/e2e/round-1/` 复用同一 fixture / helper |
| **II. CLI Interface** | ✅ 合规 | 沿用 `python -m scripts.dbq`;`backend/tests/integration/test_clear_source_idempotent.py` 可在 CI 单独跑;`npm run e2e` 自动包含 `tests/e2e/round-2/`(因 `playwright.config.ts` 用 `tests/e2e`) |
| **III. Test-First (NON-NEGOTIABLE)** | ✅ 合规 | 每个 task 顺序固定:test(rerun 失败用例)→ fix(代码)→ test(转绿)→ 更新 defect row。`tasks.md` T1-T12 全部按此结构编写。Round-2 新增的 11 个用例先于对应修复代码存在。 |
| **IV. Integration & Synchronization Testing** | ✅ 合规 | 全部 round-1 失败用例用真实 PostgreSQL + 真实 FastAPI + 真实 React(经 Playwright)复测;`backend/tests/integration/test_clear_source_idempotent.py` 跑真实 DB;`tests/e2e/round-2/interview-mock-llm.spec.ts` 走 `page.routeWebSocket` 注入 mock 但保留真实前端组件与状态机 |
| **V. Observability** | ✅ 合规 | 修复后的 `clear-source` 失败路径打结构化日志 `event=clear_source_already_cleared / error_question_id / user_id`;`JobsDetailPanel` 的 dead-component 警告只在 `NODE_ENV !== 'production'` 出现;`page.routeWebSocket` 拦截在 `console.info` 留 mock 标识(便于 debug) |

**Gate 结果**:无违规,无需 Complexity Tracking。

---

## Project Structure

### Documentation (this feature)

```text
specs/020-fix-round-1-defects/
├── plan.md              # 本文件
├── spec.md              # 需求正文(覆盖、目标、非目标、缺陷映射、AC)
├── data-model.md        # 数据模型变更(仅 1 处 Pydantic 写端字段)
├── contracts/           # 端点契约
│   ├── error-questions-source.md    # FIX-001/003/004/005
│   ├── resume-branches-path.md      # FIX-006
│   └── jobs-frontend-integration.md # FIX-002/009/010
├── tasks.md             # 12 个任务分解(test → fix → verify)
├── requirements-status.md # 30 行需求状态(12 FR + 7 AC + 11 SC)
└── README.md            # feature 索引
```

### Source Code (incremental changes)

```text
backend/
├── app/modules/errors/
│   ├── api.py          # D-003: POST → PATCH clear-source; D-004: ?source= alias
│   ├── service.py      # D-013: clear-source idempotency
│   └── schemas.py      # D-002: add source_* to CreateErrorQuestionInput
├── app/modules/interviews/
│   └── api.py          # D-006: Pydantic-validate InterviewSessionCreateOut
└── tests/
    ├── unit/test_errors_schemas_strictness.py           # NEW
    └── integration/test_clear_source_idempotent.py      # NEW

src/
├── pages/Jobs.tsx                      # D-014: mount JobsDetailPanel; D-017: headcount HTML
├── pages/ErrorBook.tsx                 # D-009: source filter UI + badge
├── pages/InterviewLive.tsx             # D-008: VITE_USE_MOCK branch
├── router.tsx                          # D-016: requireAuth loader
├── repositories/ErrorQuestionRepository.ts # D-004: ?source= (canonical)
├── hooks/useErrorQuestionMutations.ts  # D-003: PATCH instead of POST
└── components/errors/ErrorSourceBadge.tsx  # NEW (optional, for D-009 badge)

specs/019-cross-module-linking/
├── quickstart.md                       # D-005: /resumes/branches → /resume-branches
├── contracts/jobs-fields.md            # D-005
├── contracts/error-questions-source.md # D-005 reference
├── spec.md                             # D-005 (text)
└── plan.md                             # D-005 (text)

tests/
├── tests/e2e/round-1/                        # RERUN — 43 cases must go from 9 fail → 0 fail
└── tests/e2e/round-2/                        # NEW
    ├── contract-parity.spec.ts         # CONTRACT-01..06
    ├── auth-guard.spec.ts              # GUARD-01..04
    ├── interview-mock-llm.spec.ts      # MOCK-01..03
    ├── pydantic-strictness.spec.ts     # STRICT-01..02
    └── full-edge-r2.spec.ts            # EDGE-06
```

---

## Phases

### Phase 0: Research (this plan, completed)

- Read all 5 round-1 docs.
- Map every defect to a 020 task.
- Choose resolution for `D-005` (impl wins) and `D-004` (accept both
  query params, canonicalize `?source=`).
- Plan Constitution Check: pass.

### Phase 1: Design (this plan + spec.md + contracts/, completed)

- `spec.md` written; 12 FRs, 7 AC, 11 SC, 7 US, 30 requirement rows.
- `data-model.md` written; only 1 schema change.
- `contracts/` written; 3 contract files.
- `tasks.md` written; 12 tasks in 6 review waves.
- `requirements-status.md` written; 30 rows, all `planned`.

### Phase 2: Implementation (executed by `speckit-implement` or manual)

- Wave 1: T1 (D-002), T4 (D-003), T3 (D-013), T5 (D-004), T7 (D-006) —
  all error_questions + interview-sessions backend fixes in one PR.
- Wave 2: T2 (D-014) — frontend mount.
- Wave 3: T6 (D-005) — doc-only.
- Wave 4: T8 (D-009), T9 (D-016), T10 (D-017) — UI cleanups.
- Wave 5: T11 (D-008) — test infrastructure.
- Wave 6: T12 (D-010) — coverage.

### Phase 3: Verification (Final Verification table in `tasks.md`)

- Round-1 rerun: 43 / 0 / 0.
- Round-2 new: 11 / 0 / 0.
- Backend pytest: green.
- Frontend typecheck / build: 0 errors.
- All 12 defect rows in `03-defect-report.md` flipped to `fixed`.

---

## Risks

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R1 | `JobsDetailPanel` mount breaks an unrelated Jobs list test | Low | High | Run all 8 round-1 spec files; not just the 5 that target the panel |
| R2 | PATCH method change breaks 3rd-party callers | None in this repo | Low | Project has no 3rd-party consumers; doc-only ack |
| R3 | `?source=` canonical form breaks the `?filter[source]=` consumers that already shipped | Low | Low | Backend keeps both as aliases for 1 release; frontend migrates in the same PR; deprecation logged |
| R4 | Mock LLM in `InterviewLive` leaks into production | Low | Medium | Gate by `import.meta.env.VITE_USE_MOCK`; production build drops the branch via Vite tree-shake; CI test asserts `VITE_USE_MOCK !== 'true'` in `npm run build` |
| R5 | `headcount` HTML constraint breaks user paste with leading zeros | Low | Low | JS `replace(/[^0-9]/g, '')` retains the user-friendly filter; HTML `min="1"` is a soft check; the 0 case still posts but the form shows the browser validation tooltip |
| R6 | Round-1 rerun reveals a defect that round-1 missed | Medium | High | Block Wave 6 (T12) until all 5 round-1 failed cases are green for 2 consecutive runs |
| R7 | `requireAuth` redirect loop on token refresh | Low | Medium | Loader checks token presence only; the 401 path is owned by `apiClient` interceptor and clears + redirects once; documented in `jobs-frontend-integration.md` §3.2 |

---

## Open Questions

1. **FIX-006 path direction** — impl wins, but the 019 quickstart doc is
   wrong; do we need a one-time `CHANGELOG.md` entry? (Default: no, the
   contract fix is the entry.)
2. **FIX-005 deprecation timeline** — when to drop `?filter[source]=`?
   (Default: deprecate for 1 minor release, remove in 0.X.0.)
3. **FIX-011 mock placement** — `page.routeWebSocket` (recommended) vs
   backend `MockLLM` provider when `LLM_PROVIDER=mock`. (Default: WS-level
   only; backend mock is a separate concern.)
