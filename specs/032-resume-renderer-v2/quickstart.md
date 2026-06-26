# Quickstart — Resume Renderer v2

This guide validates the v2 feature end-to-end. Each scenario is a Playwright
test that runs against a real backend (PostgreSQL + ARQ + Playwright Chromium)
and real frontend (Vite dev server).

---

## Prerequisites

| Tool | Version |
|---|---|
| Node.js | 20+ |
| uv | latest |
| PostgreSQL | 16 (eGGG has one online; see `docs/architecture/source-map.md`) |
| Redis | 7 (local port 6379) |
| Chromium | bundled by `playwright install chromium` |

```bash
# 1. Install backend deps
cd backend
uv sync

# 2. Install frontend deps + Playwright browsers
cd ..
npm install
npx playwright install chromium

# 3. Run migrations (creates the 3 new tables)
cd backend
uv run alembic upgrade head

# 4. Start the backend stack (FastAPI :8000 + ARQ worker + pdf-renderer :9000)
make dev          # or: uv run uvicorn app.main:app --reload & uv run arq app.workers.main.WorkerSettings &

# 5. Start the frontend (Vite :5173)
cd ..
npm run dev
```

Confirm:

- http://localhost:8000/api/v1/health → 200
- http://localhost:9000/health → 200
- http://localhost:5173 → loads

---

## Test accounts

| Role | Email | Password |
|---|---|---|
| Owner | `owner@example.com` | `password123` |
| Visitor | (no account; uses public URL) | n/a |

`owner` has one pre-seeded v2 resume (slug `senior-eng`) and one v1 block resume
(slug `legacy-block`) for compat scenarios.

Seed via:

```bash
cd backend
uv run python -m app.modules.resumes_v2.cli seed-test-data --user owner@example.com
```

---

## Scenarios

Each scenario is implemented as a Playwright test under
`tests/e2e/032-resume-renderer-v2/`. The numbered prefixes match the
canonical order in `tasks.md`.

### S01 — Happy path: create → edit → export PDF

**Given** an authenticated user with zero v2 resumes
**When** they click "New Resume" → "Use sample data"
**And** choose Pikachu template
**Then** they see the three-column editor with sample data rendered
**And** after 500ms idle, a PUT request fires (verified in network log)
**And** clicking "Download PDF" downloads a non-empty PDF
**And** the PDF, when rendered to image, matches the preview to within 1px tolerance.

```ts
// tests/e2e/032-resume-renderer-v2/01-happy-path.spec.ts
test('create → edit → export PDF', async ({ page, request }) => {
  await login(page, 'owner@example.com')
  await page.getByTestId('new-resume-button').click()
  await page.getByTestId('use-sample-pikachu').click()
  await expect(page.getByTestId('preview-pane')).toBeVisible()
  await page.getByTestId('dock-download-pdf').click()
  const [download] = await Promise.all([
    page.waitForEvent('download'),
    page.getByTestId('export-pdf').click()
  ])
  expect(download.suggestedFilename()).toMatch(/^senior-eng-\d{4}-\d{2}-\d{2}\.pdf$/)
  expect(await download.path()).toBeTruthy()
})
```

### S02 — Template switch is live and preserves data

**Given** a resume using Pikachu
**When** the user opens Template Gallery and selects Onyx
**Then** the preview updates within 1s
**And** all section items remain (verified by counting `data-testid="section-item"`).

### S03 — Three-column resizable layout

**Given** the editor is open
**When** the user drags the left sidebar edge
**Then** the section list width changes immediately
**And** the ratio persists in localStorage (reload and verify).

### S04 — Tiptap rich text round-trip

**Given** Experience section has one item with `description = "<p>old</p>"`
**When** the user opens the item, selects the word "old", clicks Bold
**Then** `description = "<p><strong>old</strong></p>"` and the preview reflects it.

### S05 — 500ms auto-save with optimistic concurrency

**Given** the editor is open
**When** the user edits a field
**Then** a PUT fires after 500ms idle (network log assertion).
**Given** a parallel client PUTs with `version = current`
**When** the original client PUTs
**Then** it receives a 409 + toast "其他设备刚保存了更新，正在刷新数据"
**And** the editor reloads the latest data.

### S06 — Public sharing with password

**Given** a resume is set to `is_public = true` with password `secret123`
**When** an anonymous browser opens `/r/{username}/{slug}`
**Then** a password prompt is shown.
**And** correct password sets a cookie (verify `document.cookie` contains `v2_public_pw_`).
**And** the same browser can re-open without re-entering for 10 minutes.

### S07 — AI analysis round-trip

**Given** a resume with non-empty content
**When** the user clicks "Analyze"
**Then** within 60s an analysis object appears with `overallScore`, 10
dimension scores, ≥3 strengths, ≥3 suggestions.
**And** a second click updates the same row in `resume_analysis_v2` (verify
in DB: `SELECT count(*) FROM resume_analysis_v2 WHERE resume_id=...` returns 1).

### S08 — Duplicate

**Given** a resume `A`
**When** the user clicks Duplicate
**Then** within 1s a resume `B` appears in the list
**And** `B.name = "A (Copy)"`, `B.slug = "senior-eng-copy-1"`, `B.is_public = false`
**And** editing B does not affect A.

### S09 — Undo/Redo

**Given** the user edited 5 fields
**When** they press Ctrl+Z 5 times
**Then** field values revert in LIFO order
**And** Ctrl+Shift+Z restores them.
**And** typing a new value after undo clears the redo stack.

### S10 — Legacy v1 resume is read-only

**Given** a v1 block resume (slug `legacy-block`)
**When** the user opens it
**Then** the v1 editor loads (existing 027 behavior)
**And** the v2 editor route `/resume/v2/{id}` redirects to `/resume/{id}` with
a banner "该简历使用旧版格式，请创建新版 v2 简历".

---

## Running the suite

```bash
# All scenarios
npm run e2e -- tests/e2e/032-resume-renderer-v2/

# Single scenario
npm run e2e -- tests/e2e/032-resume-renderer-v2/01-happy-path.spec.ts

# Headed mode (useful for visual debugging)
npm run e2e -- --headed tests/e2e/032-resume-renderer-v2/02-template-switch.spec.ts
```

After the run, evidence (screenshots, traces) lives in `docs/evidence/032-*/`.
Do NOT commit these.

---

## Manual smoke check (no Playwright)

If Playwright is unavailable:

1. Log in as `owner@example.com`.
2. Click "New Resume" → "Use sample Pikachu".
3. Verify: 3-column layout renders; left sidebar shows 16 sections; right
   sidebar shows 12 settings.
4. Drag the left sidebar edge — width should change.
5. Open Experience → "Add a new experience" — form has 7 fields including
   `description` (rich text).
6. Click Template Gallery, switch to Onyx — preview changes within 1s.
7. Click Download PDF — file downloads.
8. Click Lock — editor shows "Locked" badge; edits blocked.
9. Click Sharing → enable public → set password `secret123`.
10. Log out → open `/r/owner/senior-eng` → password prompt → enter
    `secret123` → resume renders.
11. Click Undo (Ctrl+Z) 5 times → fields revert.
12. Click Analyze → wait ≤60s → overall score visible.

---

## What this guide does NOT cover

- Production hardening (rate limiting, DDoS, observability dashboards)
- Migration tooling from v1 to v2 (out of scope per spec)
- DOCX export (removed in clarification)
- Multi-user collaborative editing (not supported)

For implementation status, see `requirements-status.md` (created by
`speckit-tasks` workflow).