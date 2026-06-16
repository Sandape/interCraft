# Quickstart: Topbar Utility Actions

## Prerequisites

- Dependencies installed with `npm install`.
- Frontend can run through the existing Playwright dev server configuration.

## Validation Commands

```bash
npm run typecheck
npx playwright test tests/e2e/topbar-utility-actions.spec.ts --workers=1
```

## Manual Browser Validation

1. Sign in or use an authenticated test session.
2. Open `/dashboard`.
3. Click the help icon and verify `/help` opens.
4. Return to `/dashboard`, click the notification bell, verify the panel appears, press Escape, and verify it closes.
5. Open the notification panel again and click notification settings; verify `/settings?tab=notifications` opens with the notifications panel visible.
6. Open the avatar menu and verify:
   - Personal Profile opens `/profile`.
   - Account Settings opens `/settings?tab=profile`.
   - Upgrade opens `/settings?tab=subscription`.
   - Data Export opens `/settings?tab=export`.
7. Open `/settings?tab=unknown` and verify the profile settings panel is shown.

## Expected Outcome

Topbar utility controls no longer behave like inert UI. Each control either navigates to an existing destination or opens a dismissible status panel.
