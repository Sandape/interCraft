# GitHub Issues Draft for 020-fix-round-1-defects

> **Generated**: 2026-06-17 by `/speckit-taskstoissues`
> **Target repo**: `Sandape/interCraft` (from `git remote -v`)
> **Feature spec**: `specs/020-fix-round-1-defects/spec.md`
> **Tasks source**: `specs/020-fix-round-1-defects/tasks.md`
> **Defect source**: `docs/testing/round-1/03-defect-report.md`

## Why This File Exists

The `/speckit-taskstoissues` skill expects to create GitHub issues via the
GitHub MCP server. This environment has **no GitHub MCP server configured**
and **no `gh` CLI installed** (verified with `command -v gh` → exit 127).
Issue creation must be done by the user, either by:

1. Installing `gh` (`winget install GitHub.cli` or `scoop install gh`),
   authenticating (`gh auth login`), then pasting the commands below.
2. Using the GitHub web UI and pasting each issue body.
3. Configuring the GitHub MCP server in `.claude/mcp.json` and rerunning
   the command.

The 12 drafts below mirror `tasks.md` T1-T12 exactly. Each is ready to
copy into `gh issue create --body-file -` or paste into the GitHub web
form.

## Labels to Create (one-time)

Before opening issues, ensure these labels exist on the repo:

```bash
gh label create "defect"          --color "d73a4a" --description "Bug or defect"
gh label create "round-1-fix"     --color "fbca04" --description "Closes a Round-1 E2E defect"
gh label create "P0"              --color "b60205" --description "Blocker"
gh label create "P1"              --color "d93f0b" --description "High priority"
gh label create "P2"              --color "fbca04" --description "Medium priority"
gh label create "P3"              --color "0e8a16" --description "Low priority"
gh label create "backend"         --color "1d76db" --description "Backend change"
gh label create "frontend"        --color "5319e7" --description "Frontend change"
gh label create "docs"            --color "0075ca" --description "Documentation only"
gh label create "test-infra"      --color "fef2c0" --description "Test infrastructure"
```

## Milestone

Create one milestone to group the 12 issues:

```bash
gh milestone create "020 Fix Round-1 Defects" \
  --description "Closes 12 active defects from docs/testing/round-1/03-defect-report.md" \
  --due-date 2026-07-15
```

Then add `--milestone "020 Fix Round-1 Defects"` to every issue create
command below.

---

## Issue 1 — T1 / FIX-001 / D-002 (P0) — Backend: error_questions write schema drops source_*

**Title**: `[020] [P0] D-002: CreateErrorQuestionInput silently drops source_session_id and source_question_id`

**Labels**: `defect`, `round-1-fix`, `P0`, `backend`

**Body**:

```markdown
## Defect
D-002 — `CreateErrorQuestionInput` Pydantic schema in
`backend/app/modules/errors/schemas.py` does NOT declare
`source_session_id` or `source_question_id`. Pydantic v2's default behavior
is to **silently drop unknown fields**, so clients that POST with these
fields receive a 201 response but the values are never persisted.

## Why it matters
The "auto-deposit low-score interview questions" pathway (019 FR-016) cannot
be implemented end-to-end via the public API. Today round-1 has to use
direct SQL to simulate it. Frontend features that try to manually tag an
error question as "from this interview" silently fail.

## Reproduction
\`\`\`bash
TOKEN=$(curl -X POST .../auth/register ... | jq -r .tokens.access_token)

curl -X POST .../error-questions \\
  -H "Authorization: Bearer $TOKEN" \\
  -d '{"dimension":"communication","question_text":"D1","score":3,"source_session_id":"00000000-0000-0000-0000-000000000001","source_question_id":"00000000-0000-0000-0000-000000000002"}'
# → 201, but response.data.source_session_id is null
\`\`\`

## Expected
`source_session_id` and `source_question_id` are persisted and round-trip
in the response.

## Files to change
- `backend/app/modules/errors/schemas.py` — add two fields to `CreateErrorQuestionInput`

## Acceptance
- [ ] Round-1 smoke `S5` reruns and passes
- [ ] New `tests/e2e/round-2/pydantic-strictness.spec.ts STRICT-01` / `STRICT-02` pass
- [ ] New `backend/tests/unit/test_errors_schemas_strictness.py` passes
- [ ] `docs/testing/round-1/03-defect-report.md` `D-002` row flipped to `fixed`

## Spec anchors
- `specs/020-fix-round-1-defects/spec.md` §5.1 (FIX-001)
- `specs/020-fix-round-1-defects/data-model.md` §3
- `specs/020-fix-round-1-defects/contracts/error-questions-source.md` §2
- `specs/020-fix-round-1-defects/tasks.md` T1
```

**Command**:
```bash
gh issue create --title "[020] [P0] D-002: CreateErrorQuestionInput silently drops source_session_id and source_question_id" --label defect,round-1-fix,P0,backend --body-file - <<'EOF'
... (paste the body above) ...
EOF
```

---

## Issue 2 — T2 / FIX-002 / D-014 (P1) — Frontend: mount JobsDetailPanel

**Title**: `[020] [P1] D-014: JobsDetailPanel component built but never mounted — 5 round-1 cases blocked`

**Labels**: `defect`, `round-1-fix`, `P1`, `frontend`

**Body**:

```markdown
## Defect
D-014 — `src/components/jobs/JobsDetailPanel.tsx` is fully built and
unit-tested, with all `data-testid` IDs declared, but
`src/pages/Jobs.tsx` never imports it. The list rows have no `onClick`
handler. The 5 new job fields (base_location / requirements_md /
employment_type / salary_range_text / headcount) are therefore invisible
in the UI, and the Job → Resume / Job → Interview CTAs are unreachable
from the list page.

## Why it matters
This is the **largest single-point blocker** of the 019 cross-module
linking feature. **5 round-1 E2E cases** (A1, B1, B4, C1, C6) are 100%
failing because of this one missing wire. Component-level unit tests
100% pass; only E2E catches the "shipped but not wired" regression.

## Reproduction
\`\`\`bash
# Frontend dev server running, user logged in
# 1. Add a job "CoA1 / PA1"
# 2. Click the row in /jobs
# → 详情面板从未出现
\`\`\`

## Expected
- Clicking `data-testid="job-row-{id}"` opens `data-testid="job-detail-panel"`
- Panel shows 5 fields and the two CTAs
- 「为该岗位开始模拟面试」CTA is disabled (with tooltip) when `branch_id IS NULL`

## Files to change
- `src/pages/Jobs.tsx` — import, state, onClick, conditional render
- `src/components/jobs/JobsDetailPanel.tsx` — add dev-only dead-component
  useEffect warning

## Acceptance
- [ ] A1, B1, B4, C1, C6 all rerun green
- [ ] `npm run typecheck` 0 errors
- [ ] `JobsDetailPanel.test.tsx` still passes
- [ ] `03-defect-report.md` `D-014` row → `fixed`

## Spec anchors
- `specs/020-fix-round-1-defects/spec.md` §5.4 (FIX-002)
- `specs/020-fix-round-1-defects/contracts/jobs-frontend-integration.md` §2
- `specs/020-fix-round-1-defects/tasks.md` T2
```

---

## Issue 3 — T3 / FIX-003 / D-013 (P1) — Backend: clear-source idempotency

**Title**: `[020] [P1] D-013: clear-source is not idempotent — second call returns 200 instead of 400 source_already_cleared`

**Labels**: `defect`, `round-1-fix`, `P1`, `backend`

**Body**:

```markdown
## Defect
D-013 — `backend/app/modules/errors/service.py:clear_source` always returns
200. When both `source_session_id` and `source_question_id` are already
NULL, the second call should return
`400 {"error": {"code": "source_already_cleared"}}` to give clients a
clear "nothing to do" signal.

## Why it matters
- No idempotency for retry safety (019 Constitution principle IV).
- UI double-click produces no user-visible signal.
- Auditing is harder when the API cannot distinguish "cleared" from
  "already cleared".

## Reproduction
\`\`\`bash
TOKEN=...
EQ_ID=$(curl -X POST .../error-questions -d '{"question_text":"D13","score":3}' | jq -r .id)

# First call → 200, source_* NULL
curl -X PATCH .../error-questions/$EQ_ID/clear-source -H "Authorization: Bearer $TOKEN"
# Second call → should be 400 source_already_cleared; actually returns 200
curl -X PATCH .../error-questions/$EQ_ID/clear-source -H "Authorization: Bearer $TOKEN"
\`\`\`

## Expected
Second call returns 400 with typed error body.

## Files to change
- `backend/app/modules/errors/service.py` — pre-check, raise HTTPException(400, ...)
- `backend/tests/integration/test_clear_source_idempotent.py` (new) — covers 200 + 400 paths

## Acceptance
- [ ] Round-1 `D4` rerun green
- [ ] Round-2 `CONTRACT-02` pass
- [ ] `03-defect-report.md` `D-013` row → `fixed`
```

---

## Issue 4 — T4 / FIX-004 / D-003 (P1) — Backend: clear-source method PATCH

**Title**: `[020] [P1] D-003: clear-source method drift — impl POST, contract PATCH`

**Labels**: `defect`, `round-1-fix`, `P1`, `backend`

**Body**:

```markdown
## Defect
D-003 — `clear-source` is `POST` in implementation
(`backend/app/modules/errors/api.py:103`) but `PATCH` in the 019 contract
(`specs/019-cross-module-linking/contracts/error-questions-source.md §2.1`).
PATCH is more REST-correct (server-side state mutation of a single
resource, not a creation event).

## Why it matters
3rd-party clients following the contract get 404/405. The contract is
the spec; the impl must conform.

## Reproduction
\`\`\`bash
# Per contract (PATCH):
curl -X PATCH .../error-questions/$EQ_ID/clear-source
# → 404/405 (impl only handles POST)
\`\`\`

## Expected
`PATCH` works; `POST` returns 405.

## Files to change
- `backend/app/modules/errors/api.py:103` — `@router.post` → `@router.patch`
- `src/repositories/ErrorQuestionRepository.ts` and/or
  `src/hooks/useErrorQuestionMutations.ts` — flip client to PATCH
- `tests/e2e/round-1/helpers/api.ts clearErrorSource()` — flip helper to PATCH

## Acceptance
- [ ] `/api/v1/openapi.json` shows `clear-source` as `patch`
- [ ] Round-2 `CONTRACT-01` pass
- [ ] Round-1 S5 + D3 rerun green
- [ ] `03-defect-report.md` `D-003` row → `fixed`
```

---

## Issue 5 — T5 / FIX-005 / D-004 (P1) — Backend: source filter param name

**Title**: `[020] [P1] D-004: ?source= filter param — impl uses ?filter[source]=, contract says ?source=`

**Labels**: `defect`, `round-1-fix`, `P1`, `backend`

**Body**:

```markdown
## Defect
D-004 — `GET /error-questions?filter[source]=auto` works in impl but the
contract documents `?source=auto`. 3rd-party clients following the
contract get all rows back (silent filter failure).

## Decision
Accept both. `?source=` is canonical; `?filter[source]=` becomes a
deprecated alias for one release. Frontend migrates to `?source=`.

## Files to change
- `backend/app/modules/errors/api.py` — `Query(alias="source")` with
  fallback alias
- `src/repositories/ErrorQuestionRepository.ts:49` — switch to `?source=`
- `specs/019-cross-module-linking/contracts/error-questions-source.md §2.2`
  — canonical form doc

## Acceptance
- [ ] Round-1 D1, D2 rerun green
- [ ] Round-2 CONTRACT-03/04/05 pass
- [ ] Contract doc shows `?source=` as canonical
- [ ] `03-defect-report.md` `D-004` row → `fixed`
```

---

## Issue 6 — T6 / FIX-006 / D-005 (P1) — Docs: resume-branches path sync

**Title**: `[020] [P1] D-005: Resume-branches path drift — docs say /resumes/branches, impl is /resume-branches`

**Labels**: `defect`, `round-1-fix`, `P1`, `docs`

**Body**:

```markdown
## Defect
D-005 — Multiple 019 contract files reference
`POST /resumes/branches` but the backend implements
`POST /resume-branches`. Frontend already calls the impl path.

## Decision
Implementation wins. Update the 019 docs to match. Adding a backend
alias or migrating the frontend to `/resumes/branches` would invalidate
existing passing tests without semantic gain.

## Files to change (doc-only)
- `specs/019-cross-module-linking/quickstart.md` §3.1.1
- `specs/019-cross-module-linking/contracts/jobs-fields.md` §2.4
- `specs/019-cross-module-linking/spec.md` §5.7
- `specs/019-cross-module-linking/plan.md` §3.1
- `specs/019-cross-module-linking/contracts/error-questions-source.md` §5

## Acceptance
- [ ] `grep -rn "/resumes/branches" specs/019-cross-module-linking/` returns no matches
- [ ] Round-2 CONTRACT-06 pass
- [ ] `03-defect-report.md` `D-005` row → `fixed`
```

---

## Issue 7 — T7 / FIX-007 / D-006 (P1) — Backend: InterviewSessionCreateOut response shape

**Title**: `[020] [P1] D-006: InterviewSessionCreateOut response_model ignored — response is dict-wrapped ORM object`

**Labels**: `defect`, `round-1-fix`, `P1`, `backend`

**Body**:

```markdown
## Defect
D-006 — `backend/app/modules/interviews/api.py` declares
`response_model=InterviewSessionCreateOut` but returns
`{"data": <ORM>}`. FastAPI's `response_model` only applies when the
return value IS a Pydantic instance. Result:
- `checkpoint_ns` missing
- ORM-only fields (position, company, mode, started_at, etc.) leak
- The dict wrapping bypasses serialization filters

## Files to change
- `backend/app/modules/interviews/api.py` — return
  `{"data": InterviewSessionCreateOut.model_validate(result).model_dump()}`

## Acceptance
- [ ] Round-1 S4 rerun green
- [ ] Round-2 MOCK-01 asserts response has exactly 6 fields under `data`
- [ ] Manual curl confirms response shape
- [ ] `03-defect-report.md` `D-006` row → `fixed`
```

---

## Issue 8 — T8 / FIX-008 / D-009 (P2) — Frontend: ErrorBook source filter UI

**Title**: `[020] [P2] D-009: ErrorBook list lacks source filter UI — backend supports ?source= but no UI for it`

**Labels**: `defect`, `round-1-fix`, `P2`, `frontend`

**Body**:

```markdown
## Defect
D-009 — `src/pages/ErrorBook.tsx` has dimension and status filters but
not source. The backend `?source=` filter works (will be canonical after
T5). Users cannot filter the list to "来自面试 vs 手动录入" via the UI.

## Files to change
- `src/pages/ErrorBook.tsx` — add `data-testid="error-source-filter"`
  segmented control (全部 / 来自面试 / 手动录入)
- `src/components/errors/ErrorSourceBadge.tsx` (new) — per-row
  `data-testid="error-source-badge"` "来自 {company} · {position} · {时间}"

## Acceptance
- [ ] Round-1 D5 rerun green
- [ ] New `tests/e2e/round-2/error-source-ui.spec.ts` passes
- [ ] `npm run typecheck` 0 errors
- [ ] `03-defect-report.md` `D-009` row → `fixed`
```

---

## Issue 9 — T9 / FIX-009 / D-016 (P2) — Frontend: auth guard for protected routes

**Title**: `[020] [P2] D-016: Protected routes (/jobs etc.) do not redirect unauthenticated visitors to /login`

**Labels**: `defect`, `round-1-fix`, `P2`, `frontend`

**Body**:

```markdown
## Defect
D-016 — `/jobs`, `/resumes`, `/error-book`, `/interview`, `/profile`
do not redirect unauthenticated visitors. Backend returns 401, but the
frontend just spins the React Query `isLoading` forever.

## Files to change
- `src/router.tsx` — add `requireAuth` loader; apply to protected routes
- `src/lib/requireAuth.ts` (new, optional)

## Acceptance
- [ ] Round-1 E4 rerun green
- [ ] Round-2 GUARD-01..04 pass
- [ ] `npm run typecheck` 0 errors
- [ ] `03-defect-report.md` `D-016` row → `fixed`
```

---

## Issue 10 — T10 / FIX-010 / D-017 (P2) — Frontend: headcount HTML constraints

**Title**: `[020] [P2] D-017: headcount input missing type=number and min=1 — only JS filter present`

**Labels**: `defect`, `round-1-fix`, `P2`, `frontend`

**Body**:

```markdown
## Defect
D-017 — `src/pages/Jobs.tsx` "招聘人数" `<Input>` has only
`inputMode="numeric"` + JS regex filter. Missing `type="number"`,
`min={1}`, `step={1}`. Users can paste `0` or `-1`; the form submits and
the backend returns 422 — should be blocked client-side first.

## Files to change
- `src/pages/Jobs.tsx` (create modal) — add `type`, `min`, `step`
- `src/pages/Jobs.tsx` (edit modal) — same change

## Acceptance
- [ ] Round-1 A2 rerun green
- [ ] DevTools shows `type="number" min="1" step="1"`
- [ ] `03-defect-report.md` `D-017` row → `fixed`
```

---

## Issue 11 — T11 / FIX-011 / D-008 (P2) — Test infra: Phase 4 Mock LLM

**Title**: `[020] [P2] D-008: Phase 4 5-round interview flow needs Mock LLM for E2E without live API key`

**Labels**: `defect`, `round-1-fix`, `P2`, `test-infra`

**Body**:

```markdown
## Defect
D-008 — 5-round interview flow cannot be E2E-tested without a live LLM
key. `tests/e2e/fixtures/mock-llm.ts` has `MOCK_ROUNDS` defined but is
not wired into `InterviewLive`.

## Decision
Inject at the test layer via `page.routeWebSocket` and gate the
frontend on `import.meta.env.VITE_USE_MOCK`. The backend keeps
calling the real LLM; the frontend switches to the mock stream.

## Files to change
- `tests/e2e/fixtures/mock-llm.ts` — wire WS interceptor
- `src/pages/InterviewLive.tsx` — read VITE_USE_MOCK, branch to mock stream
- `tests/e2e/round-2/interview-mock-llm.spec.ts` (new) — MOCK-01..03

## Acceptance
- [ ] Round-2 MOCK-01/02/03 pass
- [ ] `VITE_USE_MOCK=true npm run dev` runs 5 rounds end-to-end with no
  external network
- [ ] Production build drops the mock branch via Vite tree-shake
- [ ] `03-defect-report.md` `D-008` row → `fixed`
```

---

## Issue 12 — T12 / FIX-012 / D-010 (P3) — Test coverage: 100-char salary_range_text boundary

**Title**: `[020] [P3] D-010: Missing E2E coverage for 100/101-char salary_range_text UTF-8 boundary`

**Labels**: `defect`, `round-1-fix`, `P3`, `test-infra`

**Body**:

```markdown
## Defect
D-010 — `30-50K · 16薪` example in the contract docs has 10 chars, well
under 100. The 100-char UTF-8 boundary for `salary_range_text` is not
covered by any E2E.

## Files to change
- `tests/e2e/round-2/full-edge-r2.spec.ts` (new) — EDGE-06

## Acceptance
- [ ] EDGE-06: 100 chars → 201; 101 chars → 422; UI renders 100 chars without truncation
- [ ] `03-defect-report.md` `D-010` row → `fixed`
```

---

## After-Create Checklist

1. Set the 12 issues to the **020 Fix Round-1 Defects** milestone.
2. Set the appropriate priority label on each (P0/P1/P2/P3).
3. Order them: T1 → T4 → T3 → T5 → T7 → T2 → T6 → T8 → T9 → T10 → T11 → T12
   (matches the Wave order in `tasks.md`).
4. Open one tracking issue: "Round-1 43-case rerun green?" with
   `gh issue create --title "Round-1 verification: 43/0/0 after 020 merge"`
   and link to all 12.
