# Research — Resume Renderer v2

**Feature**: 032-resume-renderer-v2
**Status**: Phase 0 complete
**Reference**: `D:\Project\reactive-resume` (commit at planning time)
**Date**: 2026-06-25

---

## 0. Scope of this research

The v2 spec (15 US / 97 FR / 18 SC) inherits the data model of reactive-resume v5
**verbatim**, adds a three-column editor + Tiptap rich text + 8-10 templates + auto-save
+ sharing + AI analysis, and stays inside the resume center (no cross-module changes).

This document resolves the open decisions in the spec and the integration points against
the current eGGG codebase.

---

## 1. Source of truth

### 1.1 reactive-resume v5 (`D:\Project\reactive-resume`)

| Artifact | Path | Lines | Decision |
|---|---|---|---|
| ResumeData Zod schema | `packages/schema/src/resume/data.ts` | 683 | **Adopt 1:1**, drop the loose fields we don't need |
| Default resume data | `packages/schema/src/resume/default.ts` | 170 | **Adopt 1:1** for new resume creation |
| Style rules resolver | `packages/schema/src/resume/style-rules.ts` | 74 | **Adopt 1:1** algorithm (`sectionId > sectionType > global` via `Object.assign`) |
| Template enum | `packages/schema/src/templates.ts` | 22 | **Use subset**: 8-10 of the 15 (see §5) |
| Template page components | `packages/pdf/src/templates/<name>/*.tsx` | 15 dirs | **Re-implement as HTML/CSS** (eGGG uses HTML→Playwright, not React-PDF) |
| Section icons (Phosphor) | `packages/schema/src/resume/section-icons.ts` | 21 | **Map to lucide-react** names (eGGG uses lucide) |
| Font registry | `packages/fonts/` | n/a | **Use bundled webfonts** (Google Fonts subset) |
| Sample resume data | `packages/schema/src/resume/sample.ts` | 602 | **Borrow** for `/sample-resume.json` |

### 1.2 eGGG current state (`D:\Project\eGGG`)

| Artifact | Path | Use in v2 |
|---|---|---|
| v1 block ORM | `backend/app/modules/resumes/models.py` | **Read-only legacy** — never touched by v2 |
| 027 themes | `src/modules/resume/themes/registry.ts` | **Superseded** by `metadata.design.colors` |
| 027 styles CSS | `src/modules/resume/styles/*.css` | **Superseded** by template-specific CSS |
| Renderer pipeline | `src/modules/resume/renderer/` (Markdown→HTML) | **Reuse sanitization**, but v2 inputs are JSON, not Markdown |
| Export gateway | `backend/app/api/v1/export.py` + `backend/src/services/pdf_renderer/renderer.py` | **Reuse verbatim** (HTML-in, PDF-out via Playwright) |
| Square marketplace | `src/modules/resume/marketplace/Square.tsx` | **Extend** with industry/style filters and v2 field mapping |
| Lock + COW + version snapshot (027) | `backend/app/modules/locks/`, `versions/`, `audit/` | **Reuse verbatim** as v2 infrastructure |
| Auto-save 500ms (027) | already implemented | **Reuse verbatim** + add optimistic-concurrency `version` field |

---

## 2. Dependency audit (gap analysis)

The spec assumes these libraries are already installed. They are **not** in
`package.json` today:

| Library | Spec role | Currently in eGGG? | Decision |
|---|---|---|---|
| `@tiptap/react` + extensions | Rich text editor (US9 / FR-060) | **No** (have `react-markdown` only) | **ADD** as 4 new deps (Tiptap StarterKit + Link + Highlight + TextAlign) |
| `react-resizable-panels` | Three-column editor (US3 / FR-034) | **No** | **ADD** (1 dep) |
| `@dnd-kit/core` + `@dnd-kit/sortable` | Layout drag (US4) | **Yes** (027 added) | Reuse |
| `zustand` + `immer` | Editor store + history stack (US17 / FR-101) | **Yes** (`zustand` only; no `immer`) | **ADD `immer`** |
| Phosphor icons | `icon: IconName` enum (FR-004) | **No** (lucide-react only) | **Map to lucide-react** (1:1 names where possible; fallback to `Circle`) |
| `zod` | Frontend schema validation | **No** (back-end only) | **ADD** for editor-side schema parity |
| Tailwind | Existing | **Yes** | Reuse |

**NET NEW npm dependencies (8)**:
```
@tiptap/react
@tiptap/starter-kit
@tiptap/extension-link
@tiptap/extension-highlight
@tiptap/extension-text-align
react-resizable-panels
immer
zod
```

**NET NEW font assets**: Bundle a subset of Google Fonts as static `@font-face` rules
in the renderer template (so Playwright does not need network during render).

---

## 3. Resolved NEEDS CLARIFICATION

The spec contained zero `NEEDS CLARIFICATION` items at time of plan generation
(11 were resolved via AskUserQuestion on 2026-06-25 afternoon). This section
records the **integration-level** clarifications that arose during planning —
they are not spec changes, they are scope decisions for the plan.

### C1 — Tiptap output storage format
- **Decision**: Store as **HTML string** in the jsonb `data` field (matches
  reactive-resume's `content: z.string().describe("HTML-formatted string")`).
- **Rationale**: Backend sanitizer (`sanitize_html`) is HTML-aware; the unified
  export pipeline renders HTML verbatim.

### C2 — Tiptap to PDF visual parity
- **Decision**: Render Tiptap HTML through the same HTML generator used for export
  (no separate Markdown roundtrip). The reactive-resume approach uses
  `@react-pdf/renderer` primitives, but eGGG uses HTML; we add a small HTML→PDF
  primitive set in `src/modules/resume/v2/renderer/` that mirrors the v1
  `markdown-it` output style (section, heading, item, rich list, table, link).
- **Rationale**: Preserves 027's "preview ↔ PDF zero-drift" property. FR-073 is
  the contract.

### C3 — Icon name crosswalk (Phosphor → lucide-react)
- **Decision**: Use a 1:1 name map at `src/modules/resume/v2/icons/phosphor-to-lucide.ts`.
  Phosphor names not in lucide fall back to `Circle`. Section icons are migrated
  to lucide names during data import from old block resumes.
- **Rationale**: eGGG has standardised on lucide-react (027). Adding 1500 Phosphor
  icons just for parity is unjustified. Documented limitation in the export pipeline.

### C4 — Sidebar width & multi-page layout validation
- **Decision**: Sidebar width is enforced via `react-resizable-panels` (UI) and
  a Zod min/max check (data layer: 10..50 per FR-006 / `layoutSchema`). Multi-page
  is a JSON array (matches reactive-resume `pages: pageLayoutSchema[]`).
- **Rationale**: No PHI in resume data; Zod gives us free 4xx errors.

### C5 — Concurrency control mechanism
- **Decision**: Implement **optimistic concurrency** per the Q&A clarification
  (2026-06-25):
  - `resumes_v2.version: int NOT NULL DEFAULT 0` — bumped on every successful PUT
  - Client sends `If-Match: <version>` header
  - Server: `UPDATE resumes_v2 SET ..., version = version + 1 WHERE id = :id AND version = :v`
    - 0 rows affected → return 409 with `{ latest_version, latest_data }`
  - Client on 409: toast + auto-GET + replace local (no merge — too complex for v2)
  - **Lock** (`is_locked`) is decoupled and represents owner's permanent freeze
- **Rationale**: Matches reactive-resume's approach (no row-level locks during
  edit); avoids editor stutter while still preventing lost updates.

### C6 — SSE channel
- **Decision**: Reuse the existing LISTEN/NOTIFY channel `resume_update_v2`
  (separate from v1's `resume_update`) to avoid cross-version traffic. Payload:
  `{ resume_id, version, user_id, action: "updated"|"locked"|"deleted" }`.
- **Rationale**: v1 and v2 schemas differ; one channel per version keeps
  per-version consumers simple.

### C7 — Public URL routing
- **Decision**: New route `/r/{username}/{slug}` (not the v1 `/resume/{branch_id}`
  path). Mounted under the same SPA at `src/pages/PublicResume.tsx` with
  `isPublic = true` mode (no edit affordances). Public-access tokens use a
  separate HttpOnly cookie `v2_public_pw`.
- **Rationale**: Different URL shape signals different semantics; keeps v1 and
  v2 public URLs from colliding on shared slug namespaces.

### C8 — 8-10 template shortlist
- **Decision**: Ship 10 in v2 — `onyx`, `azurill`, `kakuna`, `chikorita`, `ditgar`,
  `bronzor`, `pikachu`, `lapras`, `scizor`, `rhyhorn` (mirrors the spec table).
  Drop `ditto`, `gengar`, `glalie`, `leafish`, `meowth` (eGGG's user base is
  generalist; the dropped ones are too similar to surviving cousins).
- **Rationale**: Spec calls this out in the "Risks" table ("核心 5 套 → 后续迭代
  补全"). 10 is the documented upper bound; we ship the upper bound to avoid a
  "why not all 15?" follow-up question.

### C9 — Template rendering technology
- **Decision**: **HTML + CSS** (eGGG pipeline), not React-PDF. Each template is a
  React component in `src/modules/resume/v2/templates/<name>/Template.tsx` plus
  a sibling CSS file `template.css` that captures its visual identity (sidebar
  position, header style, section heading style, background, etc.). The shared
  `<TemplatePage>` component reads `metadata.template` and dispatches.
- **Rationale**: Reuses 027's `wrap_html_document` Playwright flow. Zero new
  rendering engine. Trade-off: visual fidelity to React-PDF rendering is "very
  close" not "byte-identical", but we have full control over CSS for richer
  effects (gradients, transforms, etc.) than React-PDF allows.

### C10 — DOCX removal
- **Decision**: Confirmed per Q&A: **no DOCX**. Export panel is `JSON + PDF` only
  (matches FR-052 amended). No `docx` library added; no `packages/docx` analogue
  in the new tree.

### C11 — Tiptap toolbar table & link
- **Decision**: Tiptap StarterKit covers Table/Link/Heading 1-6/Ordered/Bullet/
  Hard Break/Code Block. We add Highlight extension for the "Highlight" toolbar
  button. Link extension restricts to `http`/`https` per FR-065.
- **Rationale**: Keeps deps lean.

---

## 4. Architectural decisions

### 4.1 Module boundaries

```
frontend/src/modules/resume/
  v1/                        ← 027 (block + Markdown), FROZEN after v2 ships
    editor/                  ← existing Markdown editor
    renderer/                ← existing Markdown→HTML
    ...
  v2/                        ← NEW (JSON Schema + 10 templates)
    schema/                  ← Zod schemas (mirror reactive-resume; trim non-essentials)
    store/                   ← Zustand + immer + history stack (20 steps, 30 min TTL)
    icons/                   ← Phosphor→lucide crosswalk
    templates/               ← 10 React components + 10 CSS files
    editor/
      BuilderShell.tsx       ← 3-column ResizableGroup
      left/                  ← SectionsPanel (16 sections)
      center/                ← PreviewPane (multi-page CSS-paginated)
      right/                 ← SettingsPanel (12 accordion sections)
      dialogs/               ← CreateDialog, ItemEditDialog, TemplateGallery, ...
    renderer/
      jsonToHtml.ts          ← ResumeDataV2 → HTML (preview + export share this)
      pagination.ts          ← (optional) A4 page breaks via rs-md-html-parser
      styleRules.ts          ← Resolve style intent for a slot
      sanitize.ts            ← HTML sanitizer used by editor AND export
      shared.css             ← Theme variables (--color-primary, --font-body, ...)
    types.ts
    sample.ts                ← Sample resume JSON (used by Template Gallery preview)
    api.ts                   ← Frontend API client (talks to /api/v1/v2/*)
```

```
backend/app/modules/resumes_v2/   ← NEW
  __init__.py
  models.py            ← ResumeV2, ResumeStatisticsV2, ResumeAnalysisV2 (SQLAlchemy 2.0)
  schemas.py           ← Pydantic IO (create/update/duplicate/out)
  repository.py        ← async SQLAlchemy repository
  service.py           ← Business logic (duplicate, lock, sharing, SSE emit)
  api.py               ← FastAPI router under /api/v1/v2/resumes
  analysis.py          ← DeepSeek V4 Pro integration (reuses llm_client)
  cli.py               ← Per constitution Principle II: CLI for replay/debug
  tests/

backend/alembic/versions/
  0022_032_resumes_v2.py    ← Creates 3 tables + indexes
```

### 4.2 Frontend pipeline

```
+--------------------+   500ms debounce    +-----------------------+
| Editor (Tiptap     | ------------------->| PUT /api/v1/v2/resumes |
|  + Zustand store   |                      |  (If-Match: version)  |
|  + immer history)  |                      +-----------+-----------+
+--------------------+                                  |
       |                                                 | 409? -> GET + replace
       | <-- SSE on resume_update_v2 channel ------------+
       v
+--------------------+   same htmlToHtml()    +-------------------+
| <PreviewPane>      | <--------------------- | exportResume()    |
|  (live, in-browser)|                         |  wraps full HTML  |
+--------------------+                         +---------+---------+
                                                        |
                                                        v
                                              +---------+---------+
                                              | /api/v1/v2/export |
                                              |  /render (Playwright)
                                              +-------------------+
```

### 4.3 Backend pipeline

```
FastAPI router /api/v1/v2/resumes
  - GET    /                       list (with stats batch)
  - POST   /                       create (template defaults applied)
  - GET    /{id}                   fetch
  - PUT    /{id}                   update with If-Match (optimistic concurrency)
  - DELETE /{id}                   soft delete
  - POST   /{id}/duplicate         create copy
  - PUT    /{id}/lock              set is_locked
  - PUT    /{id}/sharing           set is_public + password_hash
  - GET    /{id}/statistics        read stats
  - POST   /{id}/analyze           run AI analysis (writes to resume_analysis_v2)
  - GET    /public/{username}/{slug}  read public view (no auth)
  - POST   /public/{username}/{slug}/verify-password  set cookie
  - GET    /events                 SSE stream (LISTEN/NOTIFY bridge)
```

### 4.4 Data flow & contracts

1. **GET** returns the full `ResumeDataV2` plus `version` and metadata timestamps.
2. **PUT** validates `If-Match: <version>` against DB; on match, writes
   `data = jsonb` + bumps `version = version + 1`; emits `resume_update_v2`
   NOTIFY. Response carries the new version. On mismatch, returns 409 with
   `{ latest_version, latest_data }` so the client can re-render.
3. **LISTEN/NOTIFY** channel name: `resume_update_v2`. Payload:
   `{"resume_id":"...", "version":7, "user_id":"...", "action":"updated"}`.
4. **SSE** endpoint streams NOTIFY payloads to all subscribers of the channel;
   client filters by `resume_id`.

### 4.5 Storage shape

```sql
CREATE TABLE resumes_v2 (
  id UUID PRIMARY KEY,                  -- UUIDv7
  user_id UUID NOT NULL REFERENCES users(id),
  name VARCHAR(64) NOT NULL,
  slug VARCHAR(64) NOT NULL,
  tags TEXT[] NOT NULL DEFAULT '{}',
  is_public BOOLEAN NOT NULL DEFAULT false,
  is_locked BOOLEAN NOT NULL DEFAULT false,
  password_hash TEXT,                   -- bcrypt, nullable
  data JSONB NOT NULL,                  -- ResumeDataV2
  version INT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (user_id, slug)
);
CREATE INDEX resumes_v2_user_idx ON resumes_v2(user_id, updated_at DESC);
CREATE INDEX resumes_v2_public_idx ON resumes_v2(user_id, slug) WHERE is_public = true;

CREATE TABLE resume_statistics_v2 (
  resume_id UUID PRIMARY KEY REFERENCES resumes_v2(id) ON DELETE CASCADE,
  views INT NOT NULL DEFAULT 0,
  downloads INT NOT NULL DEFAULT 0,
  last_viewed_at TIMESTAMPTZ,
  last_downloaded_at TIMESTAMPTZ
);

CREATE TABLE resume_analysis_v2 (
  resume_id UUID PRIMARY KEY REFERENCES resumes_v2(id) ON DELETE CASCADE,
  analysis JSONB NOT NULL,
  status VARCHAR(16) NOT NULL DEFAULT 'success',
  failure_reason TEXT,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### 4.6 History stack (Undo/Redo)

- Depth: 20 (per FR-101).
- Storage: array of `{ ts: number, data: ResumeDataV2 }` in Zustand.
- Trigger: every `set` call pushes a snapshot **iff** the new data differs from
  the previous top (shallow JSON comparison via `fast-json-patch`).
- TTL: 30 minutes of inactivity (no `set` calls) → clear stack; show toast on
  Ctrl+Z.
- Redo stack clears on any new edit (standard semantics).
- Duplicate operations are NOT in the stack (per FR / spec).

### 4.7 Public sharing & password

- bcrypt cost 12 (matches existing auth hashing).
- Cookie: `v2_public_pw_<resume_id_hash>` HttpOnly + SameSite=Lax + 10 min TTL.
- Public URL: `/r/{username}/{slug}`.
- `<meta name="robots" content="noindex, follow">` in `<head>` (per FR-080).
- Statistics count ONLY non-owner views/downloads.

---

## 5. Template implementation strategy

### 5.1 The 10 templates

Each template is implemented as:

1. **`Template.tsx`** — a React component accepting `data: ResumeDataV2` and
   rendering the resume layout in HTML. Reuses `<SectionRenderer>` for each
   section so the visual difference is purely CSS-driven.

2. **`template.css`** — scoped CSS defining the visual identity (sidebar
   position, header card, heading style, etc.). BEM-style class names
   (`rs-tpl-pikachu__header`, etc.) prevent collisions.

3. **`manifest.json`** — JSON describing: name, tags (3-5), description,
   sidebar position, primary color hint, recommended page format.

The 10 templates (and their reactive-resume references for visual reference):

| # | id | Style slot | Reference | Visual signature |
|---|---|---|---|---|
| 1 | onyx | Minimal | `templates/onyx/` | Pure-text header, vertical sections, 2-column optional |
| 2 | azurill | Business | `templates/azurill/` | Left sidebar (35%) + right main, single column main |
| 3 | kakuna | Minimal | `templates/kakuna/` | Centered header, symmetric single-column body |
| 4 | chikorita | Creative | `templates/chikorita/` | Left main + right tinted sidebar (inverted text) |
| 5 | ditgar | Business | `templates/ditgar/` | Left tint sidebar + main items with left 2px line |
| 6 | bronzor | Business | `templates/bronzor/` | Row-style (section title left, items right) |
| 7 | pikachu | Creative | `templates/pikachu/` | Colored header card, sidebar main split |
| 8 | lapras | Creative | `templates/lapras/` | Rounded header card + floating section titles |
| 9 | scizor | Editorial | `templates/scizor/` | Letterhead + uppercase headings + heavy weight |
| 10 | rhyhorn | Business | `templates/rhyhorn/` | Top header + pipe-separated contact line |

### 5.2 Template dispatch

```ts
const templateMap: Record<Template, ComponentType<TemplateProps>> = {
  onyx: OnyxTemplate,
  azurill: AzurillTemplate,
  ...
}

export function renderTemplate(data: ResumeDataV2) {
  const Tpl = templateMap[data.metadata.template] ?? OnyxTemplate
  return <Tpl data={data} />
}
```

### 5.3 CSS load strategy

Each template's CSS is imported lazily on first selection. Static assets (fonts)
are loaded via a single `<link>` injected at app boot for the most common font
families; additional families are loaded on demand via `document.fonts.load()`.

---

## 6. Testing strategy

Per Constitution Principle III (TDD non-negotiable):

| Layer | Test type | Tool | Scope |
|---|---|---|---|
| Schema (frontend) | Unit | Vitest | Zod parse + crosswalk |
| Schema (backend) | Unit | pytest | Pydantic round-trip |
| Repository | Integration | pytest + test DB | CRUD + version race |
| API | Contract | pytest | All 11 endpoints, happy + 4xx + 409 |
| Templates | Visual regression | Playwright | Snapshot each template at A4 + Letter + free-form |
| Editor UI | Component | Vitest + Testing Library | Dialog, Settings accordion, drag-drop |
| E2E | Story | Playwright | 6+ canonical journeys (see quickstart.md) |
| LLM analysis | Eval | pytest (mocked LLM) | Prompt + parse + retry |
| History stack | Unit | Vitest | Push/pop, TTL, redo clear |

The `playwright E2E` suite under `tests/e2e/032-resume-renderer-v2/` will be
authored per the TDD rule — write the test before implementation, confirm it
fails for the right reason, then implement.

---

## 7. Migration & compatibility

### 7.1 v1 (block + Markdown) resumes

- Table `resume_branches` is **untouched**.
- New `data_format_version` column does not exist on v1 (no migration needed).
- API path `/api/v1/resume-branches/*` continues to serve v1; v2 endpoints mount
  under `/api/v1/v2/resumes/*`.
- Frontend `ResumeList.tsx` shows both v1 and v2 cards (with v1 marked "旧版
  只读"). v1 cards route to the existing `ResumeEditor.tsx` (block editor).
  v2 cards route to the new `ResumeEditorV2.tsx`.

### 7.2 Square marketplace

- Existing `/data/template.json` is the v1 source. We extend with a
  `/data/template-v2.json` array where each item includes a `v2Template`,
  `v2Defaults: ResumeDataV2` shape.
- Marketplace UI (`Square.tsx`) gains a "数据格式" toggle (v1 / v2); v1 still
  uses parseMarkdownImport; v2 uses direct JSON assignment.

### 7.3 AI resume analysis

- Reuse `app.agents.llm_client` (DeepSeek V4 Pro, 500K/month).
- New prompt template at `backend/app/modules/resumes_v2/prompts/analyze.md`.
- 1 retry: 1s, 2s, 4s (exponential backoff per FR-091b).
- No per-user quota, no cache (per Q&A).
- Result stored in `resume_analysis_v2.analysis` (jsonb).

---

## 8. Out of scope (per spec)

- DOCX export (removed in clarification)
- Real-time multi-user collaboration (no CRDT, no OT)
- LinkedIn auto-import
- Template author marketplace (user-uploaded templates)
- v1 → v2 data migration tool (deferred to v3)
- Per-constitution Principle II: CLI for the v2 module is required
  (`python -m app.modules.resumes_v2.cli ...`); it MUST be authored
  alongside the API per the constitution.

---

## 9. Risks & mitigations (operational)

| Risk | Mitigation |
|---|---|
| 10 templates = high porting cost | Phase 4a ships MVP 5 (onyx/azurill/pikachu/scizor/chikorita); remaining 5 follow in Phase 4b within same feature (still 032 scope) |
| Tiptap ↔ PDF visual drift | Share one HTML sanitizer; one style sheet; one preview renderer |
| SSE channel load (N clients × N resumes) | Use single LISTEN/NOTIFY; clients filter in-process |
| bcrypt on every public view is slow | Cache password hash on resume (already in `password_hash` column); verify once per cookie TTL |
| 8 NEW npm deps break the build | Add to `package.json` only after first template compiles with one of them (TDD order) |

---

## 10. Phase rollout (within this 032 spec)

The spec groups 17 user stories (US1–US17). Implementation will execute in
the same order documented in spec §Notes:

```
P1: US1 (data model) → US2 (templates) + US3 (3-col shell)
P1: US5/6/7 (design/typography/page)
P1: US4 (layout DnD)
P1: US9 (Tiptap)
P1: US10 (dock + export)
P1: US12 (auto-save + concurrency)
P2: US8 (style rules)
P2: US11 (sharing)
P2: US14 (AI analysis)
P2: US16 (Duplicate)
P2: US17 (Undo/Redo)
P3: US13 (marketplace compat)
P1: US15 (compat)
```

---

## 11. References

- `D:\Project\reactive-resume\packages\schema\src\resume\data.ts` — Source
  schema (683 lines)
- `D:\Project\reactive-resume\packages\schema\src\resume\default.ts` — Default
  sample data (170 lines)
- `D:\Project\reactive-resume\packages\schema\src\resume\style-rules.ts` —
  Style rule resolver (74 lines)
- `D:\Project\reactive-resume\packages\pdf\src\templates\<name>/` — 15 reference
  templates
- `D:\Project\eGGG\specs\032-resume-renderer-v2\spec.md` — Feature spec
- `D:\Project\eGGG\.specify\memory\constitution.md` — Project constitution
- `D:\Project\eGGG\specs\027-resume-center-muji-alignment\` — Predecessor spec
  for renderer/export/marketplace