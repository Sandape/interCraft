# Research: Markdown Editor Cutover and Pagination (REQ-049)

## Decision 1: Make Markdown the single editor route

**Decision**: Route every resume creation and editing path to the REQ-047 Markdown editor and remove the legacy structured editor as an active user-facing option.

**Rationale**: Maintaining two active editors creates conflicting sources of truth for Markdown source, structured section data, themes, line spacing, smart one-page, and export. The user has explicitly required a complete move to the Markdown rendering route.

**Alternatives Considered**:

- Keep a legacy editor toggle: rejected because it keeps the conflicting model alive and weakens the cutover.
- Keep the old editor read-only: rejected for the initial user flow because stale links would still expose the retired surface. Recovery can happen through Markdown conversion or a clear non-editing fallback.
- Delete legacy files immediately: rejected as a first planning decision because safe cutover can be achieved by route disconnection first, while tests prove no active user-facing legacy controls remain.

## Decision 2: Preserve older resume content through deterministic Markdown conversion

**Decision**: Older structured resumes without Markdown source must open through a deterministic JSON-to-Markdown conversion or a clearly recoverable fallback that exposes all non-empty visible content.

**Rationale**: REQ-049 is a product cutover, not a data deletion feature. Existing resume content must remain useful even when the old editor is retired.

**Alternatives Considered**:

- Block old resumes with an error banner: rejected because it traps useful content outside the editing route.
- Redirect to v1 editor: rejected because it violates the "Markdown-only" cutover.
- Convert only common fields and silently drop unknown fields: rejected because custom sections and partially filled older resumes are explicit edge cases.

## Decision 3: Normalize contact containers before visual styling

**Decision**: Treat `::: left` and `::: right` as semantic contact containers that emit stable row groups with an icon slot and a text/link slot. Unknown icons use a reserved fallback slot so alignment does not change.

**Rationale**: The current container plugin emits only generic `.lr-container`, `.left`, and `.right` wrappers. That gives CSS too little structure to align icon, link, and wrapped text consistently across themes and PDF export.

**Alternatives Considered**:

- Fix with CSS only: rejected because icon markup and wrapped text need stable row semantics.
- Absolutely position icons: rejected because long URLs, wrapped rows, and PDF rendering are fragile.
- Require users to write tables for contact layout: rejected because Muji-compatible `::: left/right` syntax is already part of the accepted Markdown dialect.

## Decision 4: Use real preview pagination, not page-count estimation

**Decision**: Replace the Markdown editor's estimated page count with DOM-measured page pagination that creates ordered preview page containers. PDF export uses that paginated preview model or an equivalent serialized page payload.

**Rationale**: The current Markdown preview renders one A4 article and estimates pages from text length. This cannot guarantee that headings, lists, tables, contact blocks, or theme spacing are preserved across page breaks.

**Alternatives Considered**:

- CSS-only print pagination: rejected because live preview must show clear page boundaries and match export.
- Continue estimating page count: rejected because it cannot prevent clipping or heading stranding.
- Compress everything to one page with overflow hidden: rejected because smart one-page must not hide content.

## Decision 5: Treat smart one-page as an optimization with a visible fallback

**Decision**: Smart one-page may reduce line height within the existing preset range only when all content fits. If content cannot fit, smart status becomes `infeasible` and the preview stays multi-page.

**Rationale**: REQ-047 already defines smart one-page behavior. REQ-049 adds the missing long-content safety rule: every page must remain visible when fitting is impossible.

**Alternatives Considered**:

- Shrink font size or margins beyond theme rules: rejected for v2 scope because it would alter theme fidelity and require new controls.
- Hide trailing content: rejected because it violates content preservation.
- Disable smart one-page for all multi-page content without feedback: rejected because users need to understand why the result changed.

## Decision 6: Use visual E2E evidence for contact and pagination acceptance

**Decision**: Unit tests verify DOM/class/contract behavior, while Playwright acceptance captures screenshots for the three themes, contact block alignment, long-resume pagination, smart one-page infeasible state, and export parity.

**Rationale**: The reported defects are visual and layout-specific. Pixel-level screenshots and page-count assertions catch regressions that string snapshots do not.

**Alternatives Considered**:

- Unit tests only: rejected because browser layout and PDF export are central to this feature.
- Manual screenshot review only: rejected because repeated cutover regressions need automated guardrails.

## Decision 7: Export from the same rendered contract as preview

**Decision**: PDF export must consume the current Markdown source, theme, effective line height, smart one-page state, pagination state, and rendered page order from the same contract as the live preview.

**Rationale**: REQ-047 already requires preview/export parity. REQ-049 makes this stricter for multi-page content and contact alignment.

**Alternatives Considered**:

- Backend re-renders from raw Markdown with separate CSS: rejected unless it consumes byte-equivalent CSS/page markup, because drift is likely.
- Export only first page when smart one-page is active: rejected because infeasible smart one-page must export all pages.

