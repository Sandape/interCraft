# 010 Requirement Status

Status reconciled against code on 2026-06-22. All 3 user stories and 9
FR are implemented; E2E covers help/notifications/user-menu/settings-tab
URL flows.

## User Stories

| Requirement | Summary | Status | Evidence | Notes |
|---|---|---|---|---|
| US1 | Help and notifications are actionable | done | `src/components/layout/Topbar.tsx:18,21,47-65` notification panel + outside-click/Escape close; help navigates to help center; `tests/e2e/topbar-utility-actions.spec.ts` | — |
| US2 | User menu items navigate to real destinations | done | `src/components/layout/Topbar.tsx` user menu items link to profile/account/subscription/export | — |
| US3 | Settings tabs support direct links | done | `src/pages/Settings.tsx:34-38` `searchParams.get('tab')` + `setSearchParams({ tab: next })` | — |

## Functional Requirements

| Requirement | Summary | Status | Evidence | Notes |
|---|---|---|---|---|
| FR-001 | topbar help control navigates to help center | done | `src/components/layout/Topbar.tsx` help button → `/help` | — |
| FR-002 | topbar notification control toggles panel with title/state/settings link | done | `src/components/layout/Topbar.tsx:18,21,47-65` `notificationsOpen` state + panel | — |
| FR-003 | notification panel closes on outside-click / Escape / settings link | done | `src/components/layout/Topbar.tsx:47-65` outside-click handler; Escape handler; settings link | — |
| FR-004 | opening notification panel closes avatar menu and vice versa | done | `src/components/layout/Topbar.tsx` mutual exclusion of `notificationsOpen` and avatar menu state | — |
| FR-005 | user menu items navigate to real destinations (profile/account/subscription/export) | done | `src/components/layout/Topbar.tsx` MenuItem onClick navigates | — |
| FR-006 | Settings initializes active tab from `tab` query value | done | `src/pages/Settings.tsx:34-35` `normalizeSettingsTab(searchParams.get('tab'))` | — |
| FR-007 | Settings falls back to profile tab for missing/unsupported `tab` | done | `src/pages/Settings.tsx:35` `normalizeSettingsTab` defaults to `'profile'` | — |
| FR-008 | Settings tab changes update browser URL (reload preserves tab) | done | `src/pages/Settings.tsx:38` `setSearchParams({ tab: next })` | — |
| FR-009 | stable test selectors + a11y state for E2E | done | `data-testid` + aria attributes on all new controls | — |

## Success Criteria

| Requirement | Summary | Status | Evidence | Notes |
|---|---|---|---|---|
| SC-001 | 100% always-visible topbar utility buttons perform action within 1 click | done | `tests/e2e/topbar-utility-actions.spec.ts` | — |
| SC-002 | reach help/profile/subscription/export/notifications in < 2 clicks each | done | `tests/e2e/topbar-utility-actions.spec.ts` | — |
| SC-003 | reload of supported settings tab URL preserves tab in 100% of cases | done | `src/pages/Settings.tsx:34-38`; `tests/e2e/topbar-utility-actions.spec.ts` | — |
| SC-004 | notification panel open/close without page reload, without blocking other controls | done | `tests/e2e/topbar-utility-actions.spec.ts` | — |

## Status Roll-up

- Total: 3 US + 9 FR + 4 SC = 16 rows.
- `done`: 16 rows.
