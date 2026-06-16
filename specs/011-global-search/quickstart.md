# Quickstart: Global Search Command Palette

**Feature**: 011-global-search
**Date**: 2026-06-16

End-to-end validation guide for the global search command palette.

## Prerequisites

- Backend: Postgres reachable + `uv run alembic upgrade head` already applied.
- Backend: Redis reachable on `localhost:6379` (for the existing rate limiter).
- Backend: `backend/.env` includes `USE_MOCK=false` and a real `JWT_SECRET`.
- Frontend: `npm install` already run.
- Backend running on `http://localhost:8000` (e.g., `cd backend && uv run uvicorn app.main:app --reload`).
- Frontend running on `http://localhost:5173` (`npm run dev`).
- Logged-in user with at least one resume branch and one interview session in the DB.

## Seed data

The platform already seeds FAQ and resources via `app.modules.content.seed`. For resumes and interview sessions, create them via the normal UI before running the E2E suite, or rely on `tests/e2e/fixtures/` if present.

A minimal manual seed (run inside `backend/scripts/dbq.py`):

```sql
-- Replace :user_id with the real authenticated user UUID.
SET app.user_id = '<user-uuid>';

INSERT INTO resume_branches (id, user_id, name, position, status, is_main, created_at, updated_at)
VALUES (gen_random_uuid(), :user_id, '字节跳动 · 高级前端', '高级前端工程师', 'optimizing', false, now(), now());

INSERT INTO interview_sessions (id, user_id, position, company, status, created_at, updated_at)
VALUES (gen_random_uuid(), :user_id, '高级前端工程师', '字节跳动', 'completed', now(), now());
```

## Manual validation scenarios

### Scenario 1 — Open via shortcut, type, click a result

1. Sign in and land on `/dashboard`.
2. Press `Ctrl+K` (or `⌘K` on macOS). The command palette appears with the input focused.
3. Type `字节`. Within 200 ms, you see a "简历分支" group with the seeded branch and a "面试记录" group with the seeded interview.
4. Click the first result. The palette closes and the route changes to `/resume/<id>`.
5. **Expected**: One request was sent to `GET /api/v1/search?q=%E5%AD%97%E8%8A%82`. The XHR shows status 200 and a 200–500 byte response.

### Scenario 2 — Keyboard navigation

1. Open the palette (`Ctrl+K`), type `字节`.
2. Press `ArrowDown`. The second result is highlighted.
3. Press `ArrowUp`. The first result is highlighted.
4. Press `Enter`. The palette closes and navigates.
5. Press `Ctrl+K` again to open, then `Escape`. The palette closes without navigating.
6. **Expected**: No mouse interactions needed. `aria-selected` is on the highlighted item at all times.

### Scenario 3 — Empty and no-results states

1. Open the palette (`Ctrl+K`). The input is empty. A hint is visible: "支持搜索简历、面试、能力维度、常见问题、学习资源".
2. Type `zzzznotfound` (or any non-matching string). After the request returns, a "未找到匹配结果" message is shown with the query echoed.
3. **Expected**: No 500 in the network tab. The palette remains open and the input keeps the query so you can edit it.

### Scenario 4 — Error state and retry

1. Open the palette, type a query, then in the browser dev tools throttle the network to "Slow 3G".
2. A loading spinner is visible while the request is in flight.
3. After ~5 s, the response arrives.
4. Now block `/api/v1/search` in the dev tools (or in the route mock) to return 500.
5. Type a new query. An error message is visible: "搜索失败，请稍后重试" with a "重试" button.
6. Click "重试" (or clear the block and re-type). The palette returns to the success state.
7. **Expected**: The palette never auto-closes. The error UI is dismissible by re-typing.

### Scenario 5 — Outside click and shortcut toggle

1. Open the palette, type a query.
2. Click outside the palette (e.g., on the page background). The palette closes.
3. Press `Ctrl+K` to reopen. The query is cleared.
4. Press `Ctrl+K` again. The palette closes (toggle).
5. **Expected**: Only one palette instance exists at any time.

### Scenario 6 — RLS isolation (manual)

1. Sign in as user A. Create a resume branch "字节跳动 · 高级前端" (A's branch).
2. Sign out. Sign in as user B.
3. Open the palette and type `字节`. B sees only their own data (or the platform-wide FAQ/resources, but never A's branch).
4. **Expected**: Zero records from user A appear in the response.

## E2E tests (automated)

```
npx playwright test tests/e2e/global-search.spec.ts --workers=1
```

The spec file lives at `tests/e2e/global-search.spec.ts` and contains 4 tests:
1. Open via shortcut, type, see grouped results, click a result, navigate.
2. Keyboard navigation (ArrowDown, ArrowUp, Enter, Escape).
3. Empty hint state + no-results state.
4. Outside click closes; error state shows retry.

The spec mocks `/api/v1/search` and the user endpoints; no live backend is required for the automated suite (consistent with `topbar-utility-actions.spec.ts` and the rest of the e2e suite).

## Lint + typecheck

```
npm run typecheck
```

Should pass with zero new errors. The new `CommandPalette` and `useGlobalSearch` are fully typed.

## Cleanup

No new tables, no migrations. To roll back, remove:
- `backend/app/modules/search/` (new module)
- `src/components/layout/CommandPalette.tsx` (new component)
- `src/api/search.ts` (new API client)
- `src/hooks/queries/useGlobalSearch.ts` (new hook)
- Mount line in `src/components/layout/AppShell.tsx`
- `topbar` input wiring in `src/components/layout/Topbar.tsx`
- Registration line in `backend/app/api/v1/__init__.py`
