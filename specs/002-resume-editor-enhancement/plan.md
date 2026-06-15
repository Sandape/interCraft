# Implementation Plan: Resume Editor Enhancement

**Branch**: `002-resume-editor-enhancement` | **Date**: 2026-06-13 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-resume-editor-enhancement/spec.md`

## Summary

Enhance the InterCraft resume editor with five core capabilities: (1) WYSIWYG editing mode with split-pane Markdown editor + live A4 preview, toggleable with the existing Quick Mode; (2) multi-format resume export (Markdown, PDF via server-side Puppeteer, PNG/JPEG at 2x resolution) and Markdown import; (3) a prominent full-width primary resume card above the branch grid on the list page; (4) two minimalist resume style templates (Compact One-Page and Modern Two-Column) with per-branch persistence; and (5) a unified top toolbar consolidating mode toggle, export, style selection, and version controls.

## Technical Context

**Language/Version**: TypeScript 5.x (strict mode) + Python 3.11+ (backend PDF service)

**Primary Dependencies**: React 18, Vite, TailwindCSS, react-router-dom, @tanstack/react-query, @monaco-editor/react (Markdown editor), react-markdown + remark-gfm + rehype-raw (Markdown rendering), remark-parse/unified (import parsing), Puppeteer (backend PDF)

**Storage**: PostgreSQL (style preference as new column on resume_branches table; existing tables unchanged)

**Testing**: Vitest (frontend unit/component), pytest (backend PDF service), Playwright (E2E)

**Target Platform**: Web (desktop ≥1024px for editor; PDF service: Linux server)

**Project Type**: Web application (frontend SPA + backend PDF rendering service)

**Performance Goals**: WYSIWYG preview update ≤1s after typing stops; mode switch ≤2s; export ≤5s; style switch ≤1s

**Constraints**: PDF rendering requires backend service (network-dependent); Markdown/image export works offline; all editing offline-capable via existing outbox/lock system

**Scale/Scope**: 2 style templates, 4 export formats, 1 import format, ~5 new frontend components, 1 new backend endpoint

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Pre-Phase 0 Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Library-First | ✅ PASS | Markdown↔block converter, style renderer, export pipeline each as self-contained modules |
| II. CLI Interface | ✅ PASS | PDF rendering service exposes CLI for local testing; frontend modules testable via vitest |
| III. Test-First (NON-NEGOTIABLE) | ✅ PASS | Tests written before implementation: unit tests for converter/renderer, component tests for UI, API tests for PDF endpoint |
| IV. Integration & Sync Testing | ✅ PASS | E2E tests for dual-mode editing, export pipeline, import flow, and style switching |
| V. Observability | ✅ PASS | Backend PDF service logs request_id, style used, rendering duration; frontend logs mode switches and export actions |

### Post-Phase 1 Re-Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Library-First | ✅ PASS | Confirmed: 4 library modules identified in project structure |
| II. CLI Interface | ✅ PASS | PDF service CLI: `python -m pdf_renderer --markdown-file foo.md --style compact --output foo.pdf` |
| III. Test-First | ✅ PASS | Test structure defined; test files exist before implementation |
| IV. Integration Testing | ✅ PASS | Contracts defined for PDF service; E2E scenarios in quickstart |
| V. Observability | ✅ PASS | Logging schema defined in contracts |

## Project Structure

### Documentation (this feature)

```text
specs/002-resume-editor-enhancement/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── pdf-service.md   # PDF rendering service API contract
└── tasks.md             # Phase 2 output (NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
# Frontend (existing structure + new modules)
frontend/src/
├── components/
│   └── resume/
│       ├── editor/
│       │   ├── WysiwygEditor.tsx        # Split-pane editor (NEW)
│       │   ├── MarkdownEditor.tsx       # Monaco-based editor (NEW)
│       │   ├── ResumePreview.tsx        # A4 preview pane (NEW)
│       │   ├── QuickEditor.tsx          # Current block editor (REFACTOR)
│       │   ├── UnifiedToolbar.tsx       # Top toolbar (NEW)
│       │   └── StyleSelector.tsx        # Style dropdown (NEW)
│       ├── list/
│       │   ├── PrimaryResumeCard.tsx    # Main resume hero card (NEW)
│       │   └── BranchCardGrid.tsx       # Existing grid (REFACTOR)
│       ├── export/
│       │   ├── ExportMenu.tsx           # Export dropdown (NEW)
│       │   └── useExport.ts            # Export logic hook (NEW)
│       └── import/
│           └── ImportModal.tsx          # Import modal (NEW)
├── lib/
│   ├── markdown-converter.ts            # Block ↔ Markdown conversion (NEW)
│   ├── markdown-parser.ts               # Import markdown parser (NEW)
│   ├── resume-styles/
│   │   ├── index.ts                     # Style registry (NEW)
│   │   ├── compact-one-page.css         # Style 1 CSS (NEW)
│   │   └── modern-two-column.css        # Style 2 CSS (NEW)
│   └── export/
│       ├── pdf-export.ts                # PDF export (calls backend) (NEW)
│       ├── image-export.ts              # Image export (NEW)
│       └── markdown-export.ts           # Markdown export (NEW)
├── pages/
│   ├── ResumeEditor.tsx                 # Updated with mode toggle (MODIFY)
│   └── ResumeList.tsx                   # Updated with primary card (MODIFY)
├── hooks/
│   └── useStylePreference.ts            # Style persistence hook (NEW)
└── api/
    └── export.ts                        # Export API client (NEW)

# Backend (NEW - PDF rendering service)
backend/
├── src/
│   └── services/
│       └── pdf_renderer/
│           ├── __init__.py
│           ├── renderer.py              # Puppeteer-based PDF/PNG rendering
│           ├── templates/
│           │   ├── compact-one-page.html # Style 1 HTML template
│           │   └── modern-two-column.html # Style 2 HTML template
│           └── styles/
│               ├── compact-one-page.css  # Style 1 CSS
│               └── modern-two-column.css # Style 2 CSS
└── tests/
    └── test_pdf_renderer.py

tests/
├── unit/
│   ├── markdown-converter.test.ts
│   ├── markdown-parser.test.ts
│   └── export/
├── component/
│   ├── WysiwygEditor.test.tsx
│   ├── PrimaryResumeCard.test.tsx
│   └── StyleSelector.test.tsx
└── e2e/
    ├── resume-editor.spec.ts
    └── resume-export.spec.ts
```

**Structure Decision**: Frontend follows existing project structure under `src/`. New `lib/markdown-converter.ts`, `lib/resume-styles/`, and `lib/export/` modules follow Constitution Principle I (Library-First). Backend PDF rendering service is a new self-contained module under `backend/src/services/pdf_renderer/`. Tests follow existing patterns.

## Complexity Tracking

No violations. All constitutional principles satisfied.
