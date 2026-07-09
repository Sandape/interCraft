# 017 Requirement Status

Status reconciled against code on 2026-06-22. All 7 FR and 4 SC are
implemented; E2E covers the topbar → /resume?new=true → auto-open flow.

## User Stories

| Requirement | Summary | Status | Evidence | Notes |
|---|---|---|---|---|
| US1 | 从顶栏发起新建简历分支 | done | `src/components/layout/Topbar.tsx:121-156` 下拉菜单 + `navigate('/resume?new=true')`; `src/pages/ResumeList.tsx:57-59` auto-open on `?new=true`; `tests/e2e/topbar-new-resume.spec.ts` | — |

## Functional Requirements

| Requirement | Summary | Status | Evidence | Notes |
|---|---|---|---|---|
| FR-001 | Topbar「新建简历分支」MUST call `navigate('/resume?new=true')` | done | `src/components/layout/Topbar.tsx:148,155` `navigate('/resume?new=true')` and `source_job_id` variant | — |
| FR-002 | remove `onNewResume` prop from Topbar | done | `grep onNewResume src/components/layout/Topbar.tsx src/App.tsx` returns no matches | — |
| FR-003 | ResumeList checks `searchParams.get('new') === 'true'` and auto-opens | done | `src/pages/ResumeList.tsx:57-59` | — |
| FR-004 | clear `new=true` from URL on close (cancel/Esc/overlay/submit) via `navigate('/resume', { replace: true })` | done | `src/pages/ResumeList.tsx:138,338,349` `setSearchParams({}, { replace: true })` | — |
| FR-005 | in-page 「新建简历」button behavior unchanged (no URL modification) | done | `src/pages/ResumeList.tsx` in-page button sets `open=true` only | — |
| FR-006 | remove `onNewResume` prop passing in `App.tsx` | done | `src/App.tsx` does not pass `onNewResume` to `AppShell` | — |
| FR-007 | stable `data-testid` for E2E | done | `topbar-new-resume-button` / `topbar-new-resume-menu` / `topbar-new-resume-blank` / `topbar-new-resume-from-job` test IDs | — |

## Success Criteria

| Requirement | Summary | Status | Evidence | Notes |
|---|---|---|---|---|
| SC-001 | click topbar button → /resume with auto-open modal in < 2s | done | `tests/e2e/topbar-new-resume.spec.ts` | — |
| SC-002 | `new=true` cleared on close; reload does not re-open | done | `src/pages/ResumeList.tsx:138,338,349` `setSearchParams({}, { replace: true })` | — |
| SC-003 | in-page button behavior unchanged (no URL modification) | done | `src/pages/ResumeList.tsx` in-page button | — |
| SC-004 | all `onNewResume` prop code removed from Topbar + AppShell | done | grep finds no `onNewResume` references | — |

## Status Roll-up

- Total: 1 US + 7 FR + 4 SC = 12 rows.
- `done`: 12 rows.
