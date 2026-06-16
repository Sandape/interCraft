# Quickstart: Jobs Status Alignment

**Phase**: 1 (validation)
**Date**: 2026-06-16
**Spec**: [spec.md](./spec.md) — [data-model.md](./data-model.md) — [contracts/jobs-transitions.md](./contracts/jobs-transitions.md)

## Prerequisites

- Backend: Redis 7 on `localhost:6379`; reachable Postgres (per the project's `CLAUDE.md` local-env notes)
- Frontend: Node 20+, npm 10+
- `uv` available for Python dependency management
- Backend running: `cd backend && uv run uvicorn app.main:app --reload`
- Worker running (only needed if you exercise the full interview-prep task trigger): `uv run arq app.workers.main.WorkerSettings`
- Frontend running: `npm run dev`
- A valid auth token from `POST /api/v1/auth/login`

## 1. Verify the new endpoint

```bash
# Expected: 200 OK with the JSON shape documented in contracts/jobs-transitions.md
curl -sS -X GET http://localhost:8000/api/v1/jobs/transitions \
  -H "Authorization: Bearer $ACCESS_TOKEN" | jq
```

Sanity check the response:

- `statuses` has 7 items in the order: `applied`, `test`, `oa`, `hr`, `offer`, `rejected`, `withdrawn`
- `transitions` has 20 edges (6 + 5 + 4 + 3 + 2 + 0 + 0)
- No edge appears with `from === to`
- `rejected` and `withdrawn` have no outgoing edges

## 2. Verify the phantom tabs are gone

In the browser, open `/jobs` and confirm:

- Tabs shown, in order: `全部`, `已投递`, `笔试`, `OA`, `HR 面`, `Offer`, `已拒绝`, `已撤回`
- There is **no** tab labelled `筛选` (the old `screening` phantom)
- There is **no** tab labelled `面试` (the old `interview` phantom)
- The "已拒绝" stat tile no longer includes withdrawn jobs in its count
- A new "已撤回" stat tile is visible and shows only `withdrawn` records

## 3. Verify the happy path (no more 409)

```bash
# Create a job (lands in `applied`)
JOB_ID=$(curl -sS -X POST http://localhost:8000/api/v1/jobs \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"company":"Acme","position":"Senior FE"}' | jq -r .id)

# Advance applied -> test
curl -sS -X PATCH "http://localhost:8000/api/v1/jobs/$JOB_ID/status" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"to":"test"}' | jq .status   # expect "test"

# Advance test -> oa
curl -sS -X PATCH "http://localhost:8000/api/v1/jobs/$JOB_ID/status" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"to":"oa"}' | jq .status     # expect "oa"

# Advance oa -> hr
curl -sS -X PATCH "http://localhost:8000/api/v1/jobs/$JOB_ID/status" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"to":"hr"}' | jq .status     # expect "hr"

# Advance hr -> offer
curl -sS -X PATCH "http://localhost:8000/api/v1/jobs/$JOB_ID/status" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"to":"offer"}' | jq .status  # expect "offer"
```

All four PATCH calls must return 200. None may return 409.

## 4. Verify the failure path (forced 409 surfaces inline)

In the browser, with the Playwright e2e spec (or via `page.route()` in DevTools):

```js
// In the browser console on /jobs
await page.route('**/api/v1/jobs/*/status', (route) =>
  route.fulfill({
    status: 409,
    contentType: 'application/json',
    body: JSON.stringify({
      error: {
        code: 'job.invalid_transition',
        message: "Cannot transition from 'rejected' to 'applied'.",
        details: { from: 'rejected', to: 'applied' },
      },
    }),
  })
)
```

Then click any allowed transition in the popover. Expected:

- The row badge keeps the previous status (no silent rollback)
- An inline error message ("Cannot transition from 'rejected' to 'applied'.") appears inside the popover
- A "重试" button is visible
- Re-open the popover to see both the error and the retry button (the popover closes on selection by design)
- Clicking "重试" re-fires the same PATCH; if the underlying issue is gone, the badge updates to the new status

## 5. Run the e2e spec

```bash
# Backend up + frontend up + .env set
npx playwright test tests/e2e/jobs-status-alignment.spec.ts
```

The spec covers five scenarios:

1. **US1 happy path** — seed 1 job in `applied`, advance to `test` via the popover, assert no 409 in the network log
2. **US2 real tabs** — seed 2 jobs (1 in `applied`, 1 in `test`), assert tab counts and that filtering by `test` shows only the matching row
3. **US3 stats split** — seed 2 withdrawn + 1 rejected, assert "已撤回" tab count is 2 and "已拒绝" is 1
4. **US4 409 retry** — route PATCH to return 409, click a transition, assert the row stays on the previous status and an inline retry button is visible
5. **No phantom tabs** — assert the rendered tab list equals `["all","applied","test","oa","hr","offer","rejected","withdrawn"]` and the strings `screening` and `interview` are absent from the `main` region

## 6. Run the unit tests

```bash
# Frontend hook + JobRepository
npx vitest run src/hooks/queries/__tests__/useJobTransitions.test.ts \
              src/repositories/__tests__/JobRepository.test.ts

# Backend transitions
cd backend && uv run pytest -q app/modules/jobs/tests/test_transitions.py
```

Expected: all pass.

## Done When

- [x] Section 1 returns the documented JSON shape
- [x] Section 2 shows the corrected tab list, with the two phantom tabs gone
- [x] Section 3 advances a job from `applied` to `offer` with no 409s
- [x] Section 4 surfaces the inline retry UI on a forced 409
- [x] Section 5 passes all five e2e scenarios
- [x] Section 6 unit tests pass
