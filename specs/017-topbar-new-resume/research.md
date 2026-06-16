# Research: Topbar New Resume Branch

**Phase**: 0 (Outline & Research)
**Date**: 2026-06-16

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Navigation pattern | `useNavigate` direct call | Already used in Topbar for help/settings/export routes |
| URL parameter mechanism | `useSearchParams` with `navigate` cleanup | Standard React Router v6 — no new deps, works with browser back/forward |
| Modal trigger on mount | `useEffect` on mount checking `searchParams.get('new') === 'true'` | Simple, predictable, survives page refresh |
| Cleanup on modal close | `setSearchParams({}, { replace: true })` | Only removes `new=true`, preserves other params, doesn't add history entry |
| Prop removal | Remove from Topbar → AppShell → App.tsx | Dead code elimination per spec FR-002/FR-006 |

## Alternatives Considered

- **React Router state** (`navigate('/resume', { state: { openCreate: true } })`): Doesn't survive refresh, harder to test.
- **Global state (Zustand)**: Overkill for a transient UI-triggering flag.
- **Callback prop from ResumeList up to AppShell**: Creates unnecessary coupling across the component tree.

## Key Observations

- Topbar already imports `useNavigate` (used for help, settings paths) — no new imports needed for the core navigation.
- `Button` component already in Topbar — the existing `onClick={onNewResume}` just needs to change to `onClick={() => navigate('/resume?new=true')}`.
- ResumeList already has a full create modal with `name`, `company`, `position` fields and `createBranch.mutate` — no modal logic changes needed.
- `onNewResume` prop currently flows through: `App.tsx → AppShell → Topbar`. It's never defined, so the button is dead. All three sites need cleanup.
