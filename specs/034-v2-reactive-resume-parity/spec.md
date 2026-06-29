# REQ-034 — v2 Reactive-Resume Parity + Production Readiness

**Status**: draft (Cycle 2 — v2 reactive-resume parity)
**Feature JSON**: `specs/034-v2-reactive-resume-parity`
**SpecKit role**: new feature
**Parent context**: REQ-032 v2 MVP shipped 6-US scope (US1/2/3/5/6/7/10/11/17). This spec captures the **reactive-resume parity gap** verified 2026-06-29 plus the **production-readiness hardening** needed to ship to real users.

---

## Why this spec exists

After the 032 v2 MVP ship on 2026-06-29 (6/6 E2E pass, `tests/e2e/032-v2-mvp.spec.ts`), the user asked for a hands-on verification: write a complete resume (李祖荫 大模型应用开发工程师) into v2 and check whether the editor's capability matches reactive-resume.

**Verdict**: v2 is a **template + design-token shell**, not a content editor. The left panel "Sections" only edits `section.title/icon/hidden/columns` (the last is schema-only, not exposed). The Settings tabs Typography + Page are real; Layout / Design / Styles / Notes / Sharing / Statistics / Analysis / Export / Information are mostly stubs. There is **no UI to edit a work experience item's bullets, a project's description, a skill's keywords, or a profile's network**.

Concrete verification: written into v2 via `PUT /api/v1/v2/resumes/{id}` because the UI exposes no content form. See `docs/evidence/032-v2-tpl-pikachu-rendered.png` (full resume renders via API-injected content) and `docs/evidence/032-v2-layout-panel.png` (Layout tab stub).

## Goal

> v2 完全达到 reactive-resume 的效果 并且可以上线生产环境。

Translation: implement reactive-resume's content-editing capability on top of the existing v2 shell, then harden for production launch.

## Scope (locked at this draft, subject to AC negotiation)

### Bucket A — Content editing (reactive-resume parity, ~6 dev days, pure UI)

| US | Title | Reactive-resume source | Estimated | Priority |
|----|-------|------------------------|-----------|----------|
| US1 | Basics form + Picture picker | `routes/.../left/sections/basics.tsx` + `picture.tsx` | 1.0 d | P0 |
| US2 | Experience item dialog (with `roles[]` + drag-reorder) + section-item list + add-button | `dialogs/resume/sections/experience.tsx` + `left/sections/experience.tsx` | 1.5 d | P0 |
| US3 | Education + Project + Skill item dialogs (3 × shared `SectionItem` wrapper) | `dialogs/resume/sections/{education,project,skill}.tsx` | 1.5 d | P0 |
| US4 | Profile item dialog (network icon picker) | `dialogs/resume/sections/profile.tsx` | 0.5 d | P0 |
| US5 | Language + Interest + Award + Certification + Publication + Volunteer + Reference item dialogs (7 × bulk) | `dialogs/resume/sections/{language,interest,award,...}.tsx` | 1.0 d | P1 |
| US6 | Custom section dialog + per-section design tab | `dialogs/resume/sections/custom.tsx` + `right/sections/design.tsx` | 0.5 d | P1 |

### Bucket B — Production readiness (~3 dev days)

| US | Title | Source | Estimated | Priority |
|----|-------|--------|-----------|----------|
| US7 | Real implementations for current stub Settings tabs (Layout, Design, Notes, Sharing, Statistics, Analysis, Information, Export) | `editor/right/{Layout,Design,...}Panel.tsx` (stubs) | 1.5 d | P0 |
| US8 | Backend: replace 5 501-stub endpoints with real implementations (analyze / AI enhancement / etc.) | `app/modules/resumes_v2/api.py:501 stubs` + service layer | 0.5 d | P0 |
| US9 | E2E coverage: add `tests/e2e/034-v2-content-editing.spec.ts` covering all 10 section dialogs + basics form + picture + custom section | new spec | 0.5 d | P0 |
| US10 | Production hardening: error boundaries, retry logic, telemetry hooks, RLS audit, rate limiting on hot endpoints | cross-cutting | 0.5 d | P1 |

### Bucket C — Already done in 032 (do not re-implement)

- US11 (= 032 US1) CRUD + structured JSON
- US12 (= 032 US2) Onyx template
- US13 (= 032 US3) 3-panel editor
- US14 (= 032 US5/6/7) Typography / Page / Sections panel
- US15 (= 032 US10) PDF export
- US16 (= 032 US11) Public sharing
- US17 (= 032 US17) Undo/Redo

These will be referenced as prior art and reused; **not re-implemented** in 034.

## Out of scope (explicit non-goals)

- AI auto-fill / content generation (deferred to a separate `ai-resume-optimize` cycle)
- Theme marketplace UI (already a 501 stub; deferred)
- 9 templates beyond Onyx (template gallery shows 1, others dispatch to Onyx; deferred)

## Acceptance criteria (locked after AC negotiation)

TBD — will be specified in `ac-matrix.md` after dev drafts and tester red-teams.

## Architecture constraints

- Pure UI work in `src/modules/resume/v2/editor/{left,dialogs,right}/`. No new backend modules.
- Reuse existing `useResumeV2Store` (`setDataMut` immer draft + 500ms debounced autosave + undoStack) for every item mutation.
- Reuse existing `RichTextEditor` + `RichTextToolbar` for `description` fields (no Tiptap import; keep current react-quill path).
- `SectionItem` component wraps the list-row + drag-handle + edit/duplicate/delete buttons; reused across all 10 sections.
- Backend round-trip: `ResumeDataV2Pydantic` already accepts the full schema; no backend changes except US8 stub replacement.
- All dialogs open via Zustand `openDialog({type: 'experience.create' | 'experience.update', payload})` — single dispatcher in `editor/dialogs/DialogHost.tsx`.

## Dependencies

- 032 ship artifacts (commit history `79b553d` / `fedd14d` / `54bcc3e` / `0603605` / `d657d67` / `8bd56fa` for `ResumeV2Repository`)
- reactive-resume reference: `D:/Project/reactive-resume/apps/artboard/src/`

## Risks

- **L004 applies**: dev agents on big batches historically hit Token Plan 429; plan US1/US2/US3 as separate BATCH_SIZE=1 REQs to keep each under 50 tool_uses.
- **L007 applies**: AC negotiation doubles main-agent tokens; Phase 1.5 will only grep `### R\d+` reflection blocks, not full AC tables.
- **Schema drift risk**: `ResumeDataV2Pydantic` is the source of truth; any dialog must round-trip JSON without losing fields. Verify with a backend round-trip integration test per section type.
- **Tiptap vs react-quill**: `RichTextEditor` is current; do NOT introduce Tiptap (would expand bundle and conflict with US9 deferred status).