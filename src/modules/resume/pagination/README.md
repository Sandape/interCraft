# Resume Pagination

REQ-049 uses Markdown-specific A4 preview pagination for the active resume
editor route.

## Public API

```ts
import { paginateMarkdownHtml } from "@/modules/resume/pagination";

const preview = paginateMarkdownHtml({
  html: renderedMarkdownHtml,
  lineHeight: 19,
});

console.log(preview.pageCount);
```

`paginateMarkdownHtml` returns ordered preview pages plus page-break decisions
and warnings. The editor renders each page as a stable
`data-testid="markdown-preview-page"` article and serializes those same page
containers for PDF export.

## Page Rules

- Keep headings with the first related content block when possible.
- Preserve tables, lists, and contact containers as readable blocks near page
  boundaries.
- Fall back to multiple pages when smart one-page cannot fit content safely.
- Update `metadata.markdown.paginationState` and `pageCount` without adding
  undo history.

## Validation

```bash
npm run test -- src/modules/resume/pagination/__tests__/markdown-pagination.test.ts src/modules/resume/v2/editor/__tests__/MarkdownResumePagination.test.tsx
```
