# Contract: Page Measure (REQ-063)

**Owner module**: `backend/app/modules/resume_derive/page_measure.py`
**Frontend source of truth**: `src/modules/resume/pagination/markdown-pages.ts` (+ fill ratio fields)

## Purpose

Provide a **real pagination measure** used by derive calibrate and (optionally) offline CLI. Must not use character-length heuristics as success criteria.

## Function (logical)

```text
measure_resume_pages(
  html: string,           # themed preview HTML (or markdown+theme render input)
  line_height: int,
  theme_id: string,
) -> PageMeasureResult
```

`PageMeasureResult` fields: see [data-model.md](../data-model.md).

## Invariants

1. `page_count >= 1`
2. `0 < last_page_fill_ratio <= 1`
3. If `page_count == 1`, `last_page_fill_ratio` is the single page fill
4. Same `(html, line_height, theme_id, measure_version)` is reproducible within 1px / ratio epsilon in the same browser engine
5. On failure: raise typed error `PAGE_MEASURE_FAILED` — callers MUST NOT invent `measured=target`

## PDF gate (separate)

`count_pdf_pages(pdf_bytes) -> int` remains authoritative for export.
If PDF pages ≠ expected target → `422 PAGE_COUNT_MISMATCH` and persist PDF count to `actual_page_count` when resume id known.

## Relationship to editor

Editor `paginateMarkdownHtml` MUST expose the same fill-ratio fields so list/save sync and calibrate speak one language.
