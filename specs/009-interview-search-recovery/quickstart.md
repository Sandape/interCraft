# Quickstart: Interview Search Recovery

## Prerequisites

- Install dependencies with `npm install` if needed.
- Ensure the Vite dev server can run on the Playwright configured port.

## Validation

Run type checking:

```bash
npm run typecheck
```

Run the focused E2E suite:

```bash
npx playwright test tests/e2e/interview-search-recovery.spec.ts
```

## Expected Results

- Searching by company or position filters visible interview history cards.
- No-match search shows the active query and a clear-search action.
- Clear search restores the full currently loaded history list.
- Users with no interview records still see the true empty-history guidance.
