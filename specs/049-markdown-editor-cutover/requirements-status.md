# Requirements Status: Markdown Editor Cutover and Pagination (REQ-049)

Status vocabulary follows `specs/README.md`.

REQ-049 is done. Implementation and validation evidence are recorded in
[`docs/evidence/049-markdown-editor-cutover/final-validation.md`](../../docs/evidence/049-markdown-editor-cutover/final-validation.md).

| Requirement | Status | Evidence / Notes |
|---|---|---|
| FR-001 Markdown editor only | done | `BuilderShell` renders the Markdown-only shell; E2E stale/direct route coverage passed. |
| FR-002 Remove or disable legacy editor entry points | done | Legacy panels, template gallery controls, dock controls, and `legacy-open-v1` are absent in component/E2E tests. |
| FR-003 Stale legacy links route safely to Markdown editor | done | `/resume/v2/:id` redirects to `/resume/:id`; covered by REQ-049 E2E. |
| FR-004 Preserve existing Markdown source/settings | done | `ResumeEditorV2.markdown-cutover.test.tsx` covers hydration of source/theme. |
| FR-005 Safe path for older resumes without Markdown | done | Legacy conversion helper, route test, backend legacy test, and E2E legacy fixture all pass. |
| FR-006 Hide internal labels from product copy | done | Resume list visible copy no longer exposes internal `v2`/structured editor wording. |
| FR-007 No active old structured controls | done | BuilderShell regression tests and E2E assert retired controls are absent. |
| FR-008 Keep PDF and Markdown export available | done | `ExportMenu` tests and E2E PDF/Markdown controls passed. |
| FR-009 Keep themes, line spacing, smart one-page | done | Markdown editor component tests and E2E cover themes, line spacing state, and smart fallback. |
| FR-010 Render left/right contact blocks as aligned regions | done | Contact renderer/unit/component tests and all-theme screenshots. |
| FR-011 Align icons with labels/links | done | Semantic row/icon/text slots covered by contact renderer tests and E2E screenshots. |
| FR-012 Wrapped contact text aligns with text column | done | Contact layout CSS/component coverage and visual evidence across themes. |
| FR-013 Icon-prefixed links render as coherent row groups | done | Renderer tests cover icon-prefixed links and semantic row groups. |
| FR-014 Unknown icon fallback preserves alignment | done | Renderer tests and E2E assert fallback icon slot. |
| FR-015 Contact readability across three themes | done | E2E screenshots: `contact-muji-default-autumn.png`, `contact-muji-minimal-color.png`, `contact-muji-flat-atmospheric.png`. |
| FR-016 PDF matches contact preview alignment | done | E2E PDF export request contains semantic contact markup; contact PDF evidence saved. |
| FR-017 Paginate overflowing Markdown resumes | done | Pagination helper/component tests and long-resume E2E passed. |
| FR-018 Show clear page boundaries | done | Multi-page preview containers rendered as ordered page articles; screenshot evidence saved. |
| FR-019 Preserve all content across page breaks | done | Long-resume E2E asserts late fixture content appears in serialized export HTML. |
| FR-020 Avoid stranded headings | done | Pagination helper page-break tests cover heading movement. |
| FR-021 Keep tables/lists/contact blocks readable near breaks | done | Pagination fixture and helper tests preserve block-level readability. |
| FR-022 PDF includes every preview page in order | done | Export serializes all preview page articles and E2E checks preview/export page count. |
| FR-023 Smart one-page falls back to multi-page when infeasible | done | Component and E2E smart fallback checks passed. |
| FR-024 Theme/line-height changes repaginate consistently | done | Pagination depends on rendered HTML and effective line height; component/E2E coverage passed. |
| FR-025 User-visible pagination/smart/export feedback | done | Page count, smart infeasible feedback, export measuring-state guard, and conversion status are covered by tests. |
