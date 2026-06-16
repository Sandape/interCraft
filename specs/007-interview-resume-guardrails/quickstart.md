# Quickstart: Interview Resume Guardrails

## Prerequisites

- Node dependencies installed with `npm install`
- Browser control available through the configured Chrome/Playwright path
- Dev server available through the existing Playwright `webServer` config

## Validation Scenarios

### 1. Normal Interview Completion

Run:

```bash
npx playwright test tests/e2e/interview-resume-guardrails.spec.ts --project=chromium --grep "completes a normal interview"
```

Expected:
- The user starts a session.
- The user submits answers through the final round.
- The page reaches a completed/report state.

### 2. Leave and Resume

Run:

```bash
npx playwright test tests/e2e/interview-resume-guardrails.spec.ts --project=chromium --grep "resumes an in-progress interview"
```

Expected:
- The list exposes an in-progress session card.
- Continue opens the live route.
- A resumed notice and resume summary are visible.
- Prior answers render before the next answer is submitted.

### 3. Resume Failure

Run:

```bash
npx playwright test tests/e2e/interview-resume-guardrails.spec.ts --project=chromium --grep "shows a retryable resume error"
```

Expected:
- The resume endpoint failure does not show the setup form.
- The resume error state, retry action, and return action are visible.

### 4. Full Focused Suite

Run:

```bash
npx playwright test tests/e2e/interview-resume-guardrails.spec.ts --project=chromium
```

Expected:
- All three focused browser scenarios pass.
- Console has no unexpected runtime errors from the touched pages.
