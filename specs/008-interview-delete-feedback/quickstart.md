# Quickstart: Interview Delete Feedback

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
npx playwright test tests/e2e/interview-delete-feedback.spec.ts
```

## Expected Results

- Successful delete removes only the selected interview session card.
- Failed delete keeps the dialog open with inline retryable feedback.
- Retrying after failure can complete the delete from the same dialog.
- Cancelling from the dialog does not send a delete request and does not remove records.
