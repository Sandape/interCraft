# Quickstart: Topbar New Resume Branch

**Phase**: 1 (Validation)
**Date**: 2026-06-16
**Spec**: [spec.md](./spec.md) — [plan.md](./plan.md)

## Prerequisites

- Frontend dev server running: `npm run dev`
- User authenticated (valid session)
- At least one existing resume (so ResumeList page renders properly)

## 1. Verify Topbar Button Navigates

1. Open browser to any authenticated page (e.g., `/dashboard`)
2. Click the「新建简历分支」button in the topbar (right side, first button)
3. **Expected**: Browser navigates to `/resume?new=true`
4. **Expected**: Create branch modal opens automatically on page load

## 2. Verify Direct URL Access

1. Navigate to `/resume?new=true` directly in the address bar
2. **Expected**: Page loads and create branch modal opens automatically

## 3. Verify Modal Close Cleans Up URL

1. Modal is open (from step 1 or 2)
2. Click「取消」or press `Esc` or click the backdrop
3. **Expected**: Modal closes
4. **Expected**: URL returns to `/resume` (no `?new=true` parameter)
5. **Expected**: Refreshing the page no longer opens the modal

## 4. Verify Existing Button Unchanged

1. Go to `/resume` (without `?new=true`)
2. Click the page's own「新建简历」button
3. **Expected**: Create modal opens
4. **Expected**: URL stays at `/resume` (no `?new=true` added)

## 5. TypeCheck

```bash
npm run typecheck
# Expected: zero errors
```

## 6. Unit Tests

```bash
npm test -- --run src/pages/__tests__/ResumeList.test.ts 2>/dev/null || \
npm test -- --run src/repositories/__tests__/*.test.ts
# Expected: all existing tests pass
```

## 7. E2E Test

```bash
npx playwright test tests/e2e/topbar-new-resume.spec.ts
# Expected: all scenarios pass
```
