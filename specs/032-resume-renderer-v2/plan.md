# Implementation Plan: Resume Renderer v2

**Branch**: `032-resume-renderer-v2` | **Date**: 2026-06-25 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/032-resume-renderer-v2/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Replace the v1 block + Markdown resume model with a **JSON Schema data model**
mirrored from reactive-resume v5 (`ResumeDataV2`: 12 typed sections + custom
sections + 6-slot metadata), and ship a new three-column editor backed by
**10 templates** (HTML/CSS, rendered through the existing 027 Playwright
pipeline for zero-drift PDF export). All v2 routes mount under
`/api/v1/v2/resumes/*`; v1 routes are frozen read-only.

The plan introduces two new database tables (`resumes_v2`,
`resume_statistics_v2`, `resume_analysis_v2`), a Zustand + immer editor store
with 20-step undo history and optimistic concurrency via `If-Match: <version>`,
SSE real-time updates via PostgreSQL `LISTEN/NOTIFY`, and an AI analysis flow
that reuses the DeepSeek V4 Pro LLM client.

**Critical path** (per spec §Notes): US1 data model → US2/3 templates + 3-col
shell → US5/6/7 design/typography/page → US4 layout DnD → US9 Tiptap → US10
dock + export → US12 auto-save → US8 style rules → US11 sharing → US14 AI
analysis → US16 Duplicate → US17 Undo/Redo → US13 marketplace compat → US15
legacy compat.

## Technical Context

**Language/Version**:
- Backend: Python 3.12 (FastAPI + SQLAlchemy 2.0 + ARQ + Alembic)
- Frontend: TypeScript 5.6 (React 18 + Vite 5 + Tailwind 3.4)

**Primary Dependencies**:
- Backend (existing): FastAPI, SQLAlchemy 2.0, asyncpg, ARQ, Playwright (Python, via `backend/.venv`), bcrypt, Pydantic v2, DeepSeek LLM client (`app.agents.llm_client`)
- Frontend (existing): React 18, react-router-dom 6, TanStack Query 5, Zustand 4, @dnd-kit/core + @dnd-kit/sortable, markdown-it, rs-md-html-parser, lucide-react, react-color, Tailwind 3.4
- Frontend (NEW — 8 deps): `@tiptap/react`, `@tiptap/starter-kit`, `@tiptap/extension-link`, `@tiptap/extension-highlight`, `@tiptap/extension-text-align`, `react-resizable-panels`, `immer`, `zod`

**Storage**:
- PostgreSQL 16 (online) — 3 new tables (`resumes_v2`, `resume_statistics_v2`, `resume_analysis_v2`) + 1 new NOTIFY channel `resume_update_v2`
- Redis 7 (local :6379) — ARQ queue for PDF export + AI analysis tasks
- Filesystem — none (avatar already exists; no new file storage)

**Testing**:
- Backend unit/contract: `pytest` (`backend/tests/` + `backend/app/modules/resumes_v2/tests/`)
- Frontend unit/component: `vitest` (`src/modules/resume/v2/__tests__/`)
- E2E (canonical): `@playwright/test` 1.60 under `tests/e2e/032-resume-renderer-v2/`
- Visual regression: Playwright snapshot per template at A4 + Letter + free-form

**Target Platform**:
- Backend: Linux server (existing deployment); Windows dev (current env)
- Frontend: modern browsers (Chrome 120+, Edge 120+, Firefox 121+, Safari 17+)
- PDF renderer: headless Chromium (bundled by `playwright install chromium`)

**Project Type**: web-service + library (resume renderer is a reusable TypeScript module)

**Performance Goals**:
- Template switch: < 1s preview update (500ms debounce + render)
- PDF export: < 60s typical, 99th percentile < 60s (SC-005: 99% success rate)
- SSE propagation latency: < 2s (SC-008)
- Auto-save: 500ms debounce, 2 edits → 1 PUT (SC-007)
- AI analysis: < 60s typical, 30s median (SC-011)

**Constraints**:
- HTML payload to Playwright: ≤ 1 MB UTF-8 (existing 027 limit)
- Section items per section: ≤ 100 (spec edge case)
- Summary content: ≤ 50,000 chars
- Undo history: 20 entries; 30-min TTL
- SSE connections per user: 5
- Resume name: 1..64 chars; slug: `^[a-z0-9-]+$`, 1..64 chars, unique per user

**Scale/Scope**:
- 10 templates (subsample of reactive-resume's 15)
- 12 built-in section types + custom sections
- 12 right-panel settings accordions
- 8 dock buttons (DOCX removed per clarification)
- 17 user stories (US1–US17; US16/17 added via clarification)
- 103 functional requirements (FR-001..FR-103)
- ~6 new backend files + ~25 new frontend files + ~12 new test files

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution: `.specify/memory/constitution.md` v1.0.0 (ratified 2026-06-12).

| Principle | Status | Evidence |
|---|---|---|
| **I. Library-First** | ✅ PASS | `backend/app/modules/resumes_v2/` is a self-contained module with `__init__.py`, `models.py`, `schemas.py`, `repository.py`, `service.py`, `api.py`, `cli.py`, `tests/`, `README.md`. Frontend: `src/modules/resume/v2/` is a peer to existing `v1/` module, with its own `schema/`, `store/`, `templates/`, `editor/`, `renderer/`, `__tests__/`. No cross-module state mutation. |
| **II. CLI Interface** | ✅ PASS (with task) | `backend/app/modules/resumes_v2/cli.py` MUST be authored as part of US1 tasks (per constitution note). Exposes: `seed-test-data`, `show <id>`, `analyze <id>`, `duplicate <id>`, `dump-schema`. JSON output via `--json` flag. The frontend's `jsonToHtml` renderer is callable from a Node CLI fixture for visual regression tests. |
| **III. Test-First** | ✅ PASS | Each US has an `Independent Test` scenario (spec) and a Playwright E2E spec (quickstart.md S01–S10). Tasks.md (Phase 2 output) MUST order test authoring before implementation for every US. Vitest unit tests for store/schema precede component work. |
| **IV. Integration & Sync Testing** | ✅ PASS | Integration tests cover: (a) optimistic concurrency race (`PUT` with stale `If-Match` → 409); (b) SSE round-trip (LISTEN/NOTIFY → EventSource → store update); (c) Playwright PDF parity (preview snapshot == export snapshot, ≤1px diff); (d) Duplicate isolation; (e) Public password cookie flow. No "all-mock happy path" — all integration tests hit a real Postgres + real Chromium. |
| **V. Observability** | ✅ PASS | Structured logging via `app.core.logging` (existing). New log keys: `resume_v2.create`, `resume_v2.update.conflict`, `resume_v2.duplicate`, `resume_v2.analyze.retry`, `resume_v2.sse.subscribe`, `resume_v2.export.render`. Request_id propagated via `X-Request-ID` header (existing). AI token usage + retry count emitted as metrics (reuses 029/030 OTel skeleton). |

**Technology & Stack Constraints**: ✅ All choices comply.
- Frontend: TypeScript strict + React 18 + Vite + Tailwind ✓ (no new UI framework)
- Backend: FastAPI + SQLAlchemy 2.0 + Alembic (no ad-hoc SQL) ✓
- AI: DeepSeek via centralized `app.agents.llm_client` (rate limit + retry + structured logging) ✓
- Security: bcrypt + HttpOnly cookies + RLS on `resumes_v2` ✓

**Post-Phase-1 re-check**: ✅ PASS. The `data-model.md` design adds no violations; the `contracts/` artifacts formalise the public API surface (Constitution Principle IV); the `quickstart.md` exercises every layer end-to-end (Principle III + IV).

## Project Structure

### Documentation (this feature)

```text
specs/032-resume-renderer-v2/
├── plan.md              # This file
├── spec.md              # Feature spec (input)
├── research.md          # Phase 0 — decisions + reactive-resume audit
├── data-model.md        # Phase 1 — entity model + JSON Schema
├── quickstart.md        # Phase 1 — Playwright validation scenarios
├── contracts/
│   ├── 00-overview.md           # Contract index
│   ├── 01-rest-api.md           # REST endpoints + error catalogue
│   ├── 02-resume-data-schema.md # ResumeDataV2 JSON Schema
│   ├── 03-sse-events.md         # SSE event payloads
│   ├── 04-template-gallery.md   # Template manifest
│   └── 05-frontend-store.md      # Zustand store shape
├── checklists/
│   └── requirements.md  # (existing, from /speckit-specify)
└── tasks.md              # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
backend/
├── alembic/versions/
│   └── 0022_032_resumes_v2.py           # NEW migration
├── app/
│   ├── modules/
│   │   └── resumes_v2/                   # NEW module (Library-First)
│   │       ├── __init__.py
│   │       ├── README.md                 # module purpose + public API
│   │       ├── models.py                 # SQLAlchemy ORM (3 tables)
│   │       ├── schemas.py                # Pydantic v2 IO
│   │       ├── repository.py             # async SQLAlchemy repo
│   │       ├── service.py                # business logic + SSE emit
│   │       ├── api.py                    # FastAPI router (/api/v1/v2/resumes)
│   │       ├── analysis.py               # DeepSeek integration + retry
│   │       ├── prompts/
│   │       │   └── analyze.md            # AI prompt template
│   │       ├── cli.py                    # CLI (Constitution Principle II)
│   │       ├── defaults.py               # defaultResumeDataV2()
│   │       └── tests/
│   │           ├── test_models.py
│   │           ├── test_repository.py
│   │           ├── test_api.py
│   │           ├── test_concurrency.py
│   │           └── test_analysis.py
│   └── api/v1/
│       └── ws/
│           └── resume_v2.py              # SSE endpoint (LISTEN/NOTIFY bridge)
└── src/services/pdf_renderer/            # EXISTING (027) — reused verbatim
    └── (no changes)

src/                                        # frontend root (not frontend/src)
├── modules/resume/
│   ├── v1/                                 # EXISTING (027) — frozen read-only
│   │   ├── editor/
│   │   ├── renderer/
│   │   └── ...
│   └── v2/                                 # NEW module
│       ├── schema/                         # Zod schemas (mirror backend)
│       │   ├── data.ts
│       │   ├── defaults.ts
│       │   └── style-rules.ts
│       ├── store/
│       │   ├── index.ts                   # createResumeV2Store factory
│       │   ├── history.ts                 # 20-step undo/redo + TTL
│       │   └── persistence.ts              # 500ms debounce + If-Match
│       ├── icons/
│       │   └── phosphor-to-lucide.ts      # name crosswalk
│       ├── templates/                     # 10 templates
│       │   ├── onyx/{ Template.tsx, template.css }
│       │   ├── azurill/{ ... }
│       │   ├── kakuna/{ ... }
│       │   ├── chikorita/{ ... }
│       │   ├── ditgar/{ ... }
│       │   ├── bronzor/{ ... }
│       │   ├── pikachu/{ ... }
│       │   ├── lapras/{ ... }
│       │   ├── scizor/{ ... }
│       │   ├── rhyhorn/{ ... }
│       │   ├── index.ts                   # templateMap dispatcher
│       │   └── shared/                     # <Section>, <Heading>, primitives
│       ├── editor/
│       │   ├── BuilderShell.tsx           # 3-column ResizableGroup
│       │   ├── left/
│       │   │   ├── SectionsPanel.tsx
│       │   │   └── SectionItem.tsx
│       │   ├── center/
│       │   │   ├── PreviewPane.tsx
│       │   │   └── Dock.tsx               # 8-icon bottom dock
│       │   ├── right/
│       │   │   ├── SettingsPanel.tsx      # 12 accordion children
│       │   │   ├── TemplatePanel.tsx
│       │   │   ├── LayoutPanel.tsx        # dnd-kit sortable
│       │   │   ├── TypographyPanel.tsx
│       │   │   ├── DesignPanel.tsx        # color + level
│       │   │   ├── StylesPanel.tsx        # style rules editor
│       │   │   ├── PagePanel.tsx
│       │   │   ├── NotesPanel.tsx         # Tiptap private notes
│       │   │   ├── SharingPanel.tsx
│       │   │   ├── StatisticsPanel.tsx
│       │   │   ├── AnalysisPanel.tsx
│       │   │   ├── ExportPanel.tsx
│       │   │   └── InformationPanel.tsx
│       │   └── dialogs/
│       │       ├── TemplateGallery.tsx
│       │       ├── ItemEditDialog.tsx
│       │       └── RichTextEditor.tsx      # Tiptap wrapper
│       ├── renderer/
│       │   ├── jsonToHtml.ts              # ResumeDataV2 → HTML (preview + export)
│       │   ├── styleRules.ts              # resolveStyleIntentForSlot
│       │   └── shared.css                  # theme CSS variables
│       ├── hooks/
│       │   ├── useResumeSse.ts
│       │   └── useResumeV2Store.ts
│       ├── api.ts                         # /api/v1/v2/* client
│       ├── sample.ts                     # sample data
│       ├── types.ts
│       └── __tests__/
│           ├── store.test.ts
│           ├── schema.test.ts
│           ├── styleRules.test.ts
│           ├── jsonToHtml.test.ts
│           └── templates/                  # one snapshot per template
└── pages/
    ├── ResumeEditorV2.tsx                 # new editor route /resume/v2/:id
    ├── ResumeListV2.tsx                   # v2 entry in resume list
    └── PublicResumeV2.tsx                 # /r/:username/:slug

tests/e2e/032-resume-renderer-v2/
├── 01-happy-path.spec.ts
├── 02-template-switch.spec.ts
├── 03-resizable-layout.spec.ts
├── 04-tiptap-roundtrip.spec.ts
├── 05-autosave-concurrency.spec.ts
├── 06-public-sharing.spec.ts
├── 07-ai-analysis.spec.ts
├── 08-duplicate.spec.ts
├── 09-undo-redo.spec.ts
└── 10-legacy-readonly.spec.ts

public/
└── templates/
    ├── manifest.json                      # template gallery manifest
    └── jpg/
        └── <10 template thumbnails>

docs/evidence/032-resume-renderer-v2/      # screenshots + traces (gitignored)
```

**Structure Decision**: Web application layout (Option 2 from the template). The
eGGG project uses `src/` as the frontend root (not `frontend/src/`), confirmed
via `AGENTS.md` §"Project Shape" and `docs/architecture/source-map.md`. The
backend follows the existing `backend/app/modules/<name>/` convention; the
new `resumes_v2` module is a peer to `resumes`, `interviews`, `jobs`, etc.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No Constitution violations. The 8 new npm dependencies (`@tiptap/react` +
4 Tiptap extensions + `react-resizable-panels` + `immer` + `zod`) are
third-party libraries, not project-internal libraries, so Principle I does
not require them to be self-contained modules. They are added to
`package.json` with explicit justifications in `research.md §2`.

The frontend `v2/` module is structurally a peer to `v1/` (both under
`src/modules/resume/`), preserving the existing module boundary. The backend
`resumes_v2/` module follows the same pattern as `interviews/`, `jobs/`,
etc., preserving the existing `backend/app/modules/<name>/` convention.