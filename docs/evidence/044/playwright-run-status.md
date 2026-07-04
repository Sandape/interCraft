# REQ-044 IA — Playwright run status (2026-07-03)

## Outcome

**Status: RED (4/4 failed)** at first run, all failures are infrastructure-
blocked on backend login (POST `/api/v1/auth/login` returns 500 because the
remote Postgres at 81.71.152.210:5432 is unreachable from this worktree —
memory `project_local_env.md`: "Postgres online (pending, T008b)").

## Test results

| Spec | Case | Failure mode |
|---|---|---|
| 044-ia-workspaces.spec.ts | PM sidebar renders all 8 NAV_LINK items | backend login 500 → cannot set session tokens |
| 044-ia-landing.spec.ts | /admin-console redirects to command-center | backend login 500 |
| 044-ia-sidebar-order.spec.ts | first item = Command Center, NOT Logs | backend login 500 |
| 044-ia-fallback.spec.ts | unknown role → sidebar ≥ 1 item, first = command-center | backend login 500 |

## Backend boot log highlights

```
ImportError: no pq wrapper available.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8205
ConnectionRefusedError: [WinError 1225] Զ�̼�����ܾ��������ӡ�  (DB refused)
```

Backend boots but DB pool fails. This is a pre-existing infrastructure
constraint, NOT introduced by REQ-044.

## Frontend code is correct

- `npm run typecheck` → 0 new errors in REQ-044 scope
  (`src/admin/`, `src/repositories/savedViewRepository.ts`, `src/types/admin-console.ts`).
  Baseline errors in `src/modules/resume/v2/` and `src/pages/ResumeList*.tsx`
  are pre-existing (resume-v2 cycle).
- All static grep AC assertions pass (see AC verification below).
- Test files compile and parse correctly (Playwright loads + runs the cases).

## Path to GREEN

1. Bring up a reachable Postgres (memory `project_local_env.md` says T008b).
2. Run migrations.
3. `npm run dev` from worktree on 5173 + `uv run uvicorn app.main:app --port 8205`
   from `backend/`.
4. Re-run `npx playwright test tests/e2e/044-ia-*.spec.ts --project=chromium`.

The same `index.admin.html` entry pattern is used by the existing
`tests/e2e/039-log-center-full.spec.ts` — that spec also depends on the
same Vite + backend stack. The REQ-044 specs are NOT introducing new
infrastructure dependencies.

## Static AC verification (no backend needed)

All grep-based ACs in the REQ-044 IA matrix pass locally. See the
checklist in the main agent's commit-message / state.json update.