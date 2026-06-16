# Implementation Plan: Topbar New Resume Branch

**Branch**: `017-topbar-new-resume` | **Date**: 2026-06-16 | **Spec**: [spec.md](./spec.md)

## Summary

Wire the topbar「新建简历分支」button to navigate to `/resume?new=true`, and have ResumeList auto-open the create branch modal when it detects that URL parameter. Frontend-only change — no backend, no new entities, no new components.

## Technical Context

**Language/Version**: TypeScript (React 18, React Router v6)
**Primary Dependencies**: react-router-dom (`useNavigate`, `useSearchParams`)
**Storage**: N/A
**Testing**: Vitest (unit), Playwright (E2E)
**Target Platform**: Browser (desktop web)
**Project Type**: Web application (frontend-only slice)
**Performance Goals**: N/A — no new data fetching
**Constraints**: Must not break existing ResumeList create modal flow
**Scale/Scope**: 3 files changed (Topbar, AppShell, ResumeList)

## Constitution Check

*GATE: Pass — no constitution violations. Feature is a simple wiring fix within the existing architecture.*

- No new dependencies introduced
- No data model changes
- No backend changes
- Existing patterns followed (URL-driven state, React Router navigation)
- All existing tests must remain green

## Project Structure

### Documentation (this feature)

```text
specs/017-topbar-new-resume/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Research findings
├── quickstart.md        # Validation guide
└── tasks.md             # Implementation tasks (/speckit-tasks)
```

### Source Code (files to change)

```text
src/
├── App.tsx                          # Remove unused onNewResume prop from AppShell
├── components/layout/
│   ├── AppShell.tsx                 # Remove onNewResume prop from interface
│   └── Topbar.tsx                   # Replace onNewResume with direct navigate('/resume?new=true')
└── pages/
    └── ResumeList.tsx               # Read ?new=true from URL, auto-open modal, cleanup on close
```

## Research Summary

No technical unknowns. The feature uses established patterns:
- `useNavigate` from react-router-dom for programmatic navigation (already used in Topbar for help, settings, etc.)
- `useSearchParams` for reading/writing URL parameters (standard React Router v6 API)
- Modal open/close state already exists in ResumeList (`const [open, setOpen] = useState(false)`)
- Create branch mutation already wired in ResumeList
