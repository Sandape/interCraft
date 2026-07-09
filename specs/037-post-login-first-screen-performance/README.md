# 037 - Post-Login First-Screen Performance

**Status**: active / draft
**Spec**: [spec.md](./spec.md)
**Created**: 2026-06-30

## Initial Diagnosis

The slow first screen is likely a two-part issue:

1. **Direct post-login blocker**: login success sets tokens and user, but then invalidates the current-user query. During that refetch, the current-user hook sets auth status back to `unknown`, and the auth guard renders the full-screen auth loading state. Relevant traces:
   - `src/hooks/mutations/useLogin.ts:24` to `src/hooks/mutations/useLogin.ts:28`
   - `src/hooks/queries/useCurrentUser.ts:22` to `src/hooks/queries/useCurrentUser.ts:33`
   - `src/App.tsx:52` to `src/App.tsx:70`

2. **Dashboard fan-out after the shell mounts**: the dashboard and shell request several data domains on first render. Some are critical, but recommendations and broader historical lists are secondary.
   - `src/pages/Dashboard.tsx:32` to `src/pages/Dashboard.tsx:46`
   - `src/hooks/useDashboardSuggestions.ts:25` to `src/hooks/useDashboardSuggestions.ts:29`
   - `src/components/layout/Sidebar.tsx:37` to `src/components/layout/Sidebar.tsx:39`
   - `src/hooks/queries/useAvatarBlob.ts:15` to `src/hooks/queries/useAvatarBlob.ts:31`

Backend list endpoints inspected during specification generally enforce limits, and the resume v2 list response strips the large resume document body, so the first-pass diagnosis is not "one obviously huge endpoint"; it is a critical-path and request-budget problem.

## Proposed Solution Direction

- Treat the login response as sufficient to render the authenticated shell immediately.
- Keep background identity refresh, but do not demote a confirmed logged-in session to unresolved while that refresh is in flight.
- Preserve stale-token cold-load protection.
- Split dashboard data into critical first-screen content and secondary panels.
- Reuse or defer broad recommendation inputs instead of making them part of the first-screen blocker.
- Add browser evidence and tests that simulate slow identity refresh and slow optional dashboard data.

## Requirement Status

See [requirements-status.md](./requirements-status.md).

