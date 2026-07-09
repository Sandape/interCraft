# Quickstart Validation: REQ-057 求职训练指挥台

**Date**: 2026-07-10  
**Contracts**: [dashboard-summary](./contracts/dashboard-summary.md) · [activity-labels](./contracts/activity-labels.md) · [cache-invalidation](./contracts/cache-invalidation.md) · [frontend-query](./contracts/frontend-query.md)

## Prerequisites

- Backend + Postgres + Redis per `docs/dev-startup-guide.md` (or project standard)
- Seeded test user with password login
- Frontend `npm run dev` optional for manual UI checks

## 1. Contract / unit (backend)

```bash
cd backend
uv run pytest -q tests/contract/test_dashboard_summary_schema.py \
  tests/unit/test_activity_labels.py \
  tests/unit/test_dashboard_funnel.py
```

**Expect**: schema accepts fixture summary; each `ActivityType` maps to Chinese title; funnel counts match seeded statuses + awaiting_feedback rule.

## 2. Integration: summary + today filter

```bash
cd backend
uv run pytest -q tests/integration/test_dashboard_summary.py
```

**Seed idea**:
- Job A: `interview_time` = today 14:00 TZ
- Job B: `interview_time` = tomorrow
- Job C: `status=applied` no interview

**Expect**:
- `today_interviews` length 1 (A only)
- Funnel applying ≥ 1
- Cache isolation: user B never sees user A jobs

## 3. CLI dump

```bash
cd backend
uv run python -m app.modules.dashboard.cli dump-summary --user-id <UUID> --tz Asia/Shanghai --json
```

**Expect**: exit 0; JSON has `l0`/`l1`/`l2`; `title_zh` on activities Chinese.

## 4. Frontend unit

```bash
npm run test -- src/pages/__tests__/Dashboard
# and/or useDashboardSummary / suggestion single-panel tests
```

**Expect**: one suggestion panel; no `useResumeBranches` empty-branch title; no checkbox on today list; mobile CTA present in viewport fixture.

## 5. Auth reblock regression

```bash
npm run test -- src/hooks/queries/__tests__/useCurrentUser
# or equivalent requireAuth test
```

**Expect**: with existing user + tokens, refetch does not force full-screen unknown/loading.

## 6. E2E (P1 smoke)

```bash
npm run e2e -- tests/e2e/057-dashboard-command-center
```

Suggested cases:
1. Today 2 / tomorrow 1 → list shows 2; click opens job
2. Root + derived resumes → dashboard summaries link to editor; no「简历分支」hero title
3. Activity feed shows「新增投递」not `job_created`
4. Narrow viewport → primary CTA visible
5. L2 delayed (route mock) → L0 still interactive

## 7. Manual cache check (optional)

1. Open dashboard (MISS then HIT within 60s)
2. Change job `interview_time` via UI
3. Reload dashboard → today list updated (invalidate) without waiting full TTL

## Definition of done (MVP = US1–US5)

- [ ] Summary endpoint green on contract + integration
- [ ] Dashboard consumes summary; retired branches/tasks/dual suggestions
- [ ] Auth refetch does not reblock
- [ ] E2E P1 smoke green
- [ ] Evidence notes under `docs/evidence/057-dashboard-home-optimize/` (optional but preferred)
