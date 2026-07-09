# Contract: Pagination, Preview, Smart One-Page, and Export

## Purpose

Guarantee long Markdown resumes render across multiple preview pages and export every page in the same order.

## Preview Contract

The Markdown editor must render one or more page containers:

- Every page has stable A4 dimensions.
- Page boundaries are visible in the preview scroll area.
- Page order is obvious.
- Page count shown or used by export equals the number of preview page containers.
- No content is clipped or hidden because the first page overflows.

The current single-page `article` plus estimated page count is insufficient for REQ-049 acceptance.

## Page Break Rules

Pagination must preserve readability:

- Avoid stranding a heading at the bottom of a page when its first related content line can move with it.
- Keep contact containers readable near page boundaries.
- Keep list items readable and avoid splitting a row in a way that hides markers or wrapped text.
- Keep table rows visible. Oversized tables may continue across pages only if rows remain readable.
- Unbreakable long content may produce a warning, but it must not disappear.

## Smart One-Page Contract

When smart one-page is enabled:

- The system may choose an effective line height from the existing 12-25 presets.
- If all content fits one page, the preview shows one page and the selected line height is visible in state.
- If content cannot safely fit one page, smart status becomes `infeasible`, the user receives visible feedback, and all content remains paginated across multiple pages.
- Smart one-page must never use `overflow:hidden` to hide trailing content for an infeasible resume.

## Export Contract

PDF export must:

- Export every preview page.
- Preserve page order.
- Preserve theme, line-height, contact alignment, and page breaks as closely as the export engine allows.
- Block or wait while pagination is measuring, or clearly show that export is using the latest completed pagination state.

Markdown export must:

- Preserve the original Markdown source.
- Not inject pagination artifacts into the exported Markdown.

## Test Contract

Automated coverage must include:

- Unit tests for pagination state transitions and page-break decisions.
- Component tests for multi-page preview container rendering.
- Smart one-page tests for `fit`, `already-fit`, and `infeasible`.
- Playwright E2E for a 3-page fixture containing headings, lists, tables, links, and contact blocks.
- Export verification that PDF page count equals preview page count.

## Acceptance Gates

- A 3-page fixture renders all content across pages with no clipped text.
- Preview page count and exported PDF page count match.
- Smart one-page reports infeasible for long fixtures and still shows every page.
- Theme and line-height changes trigger repagination and keep page count/export state consistent.

