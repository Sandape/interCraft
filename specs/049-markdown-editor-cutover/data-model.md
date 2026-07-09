# Data Model: Markdown Editor Cutover and Pagination (REQ-049)

## MarkdownResumeDocument

Represents the active editable document after cutover.

| Field | Type | Notes |
|---|---|---|
| `resumeId` | string | Existing resume v2 id. |
| `sourceMarkdown` | string | Authoritative editable source shown in the Markdown editor. |
| `themeId` | one of `muji-default-autumn`, `muji-minimal-color`, `muji-flat-atmospheric` | Existing REQ-047 theme id. |
| `manualLineHeight` | integer 12-25 | User-selected line spacing when smart one-page is off. |
| `smartOnePageEnabled` | boolean | Whether smart one-page fitting is active. |
| `smartLineHeight` | integer 12-25 or null | Selected fitting line height, if fitting succeeds. |
| `smartStatus` | `idle | fit | already-fit | infeasible` | Current smart one-page result. |
| `paginationState` | `idle | measuring | paginated | warning | failed` | Live preview pagination status. |
| `pageCount` | integer | Number of preview pages after pagination. Minimum 1. |
| `legacyConversionStatus` | `not_needed | pending | converted | warning | failed` | Conversion state for older structured resumes. |
| `updatedAt` | datetime | Existing persistence timestamp. |

### Validation Rules

- `sourceMarkdown` is the only editable resume content surface after cutover.
- `themeId` must be one of the three REQ-047 theme ids.
- `manualLineHeight` and `smartLineHeight` must use existing line-height presets.
- `smartStatus=infeasible` requires `smartLineHeight=null` and must still allow multi-page preview/export.
- `pageCount` must match the number of preview page containers and exported PDF pages.

## LegacyResumeContent

Represents older structured content that existed before the Markdown-only cutover.

| Field | Type | Notes |
|---|---|---|
| `resumeId` | string | Existing resume id. |
| `sourceKind` | `structured_v1 | structured_v2 | unknown` | Original data shape as detected by API/store code. |
| `visibleTextSections` | array | Ordered non-empty visible sections extracted from old data. |
| `convertedMarkdown` | string or null | Deterministic Markdown conversion result. |
| `conversionWarnings` | array | Field-level warnings when conversion is lossy or ambiguous. |
| `originalSnapshotReference` | string or null | Existing resume record or local recovery reference. |
| `convertedAt` | datetime or null | Set once conversion succeeds. |

### Validation Rules

- Non-empty visible text must not be silently omitted.
- Unknown custom sections must become Markdown headings or warning-backed preserved blocks.
- Conversion must be idempotent. Reopening a converted resume must not duplicate content.
- Conversion failure must not delete the original structured content.

## ContactContainer

Represents a rendered Muji-compatible `::: left` or `::: right` block.

| Field | Type | Notes |
|---|---|---|
| `side` | `left | right` | Container side from Markdown syntax. |
| `rows` | `ContactRow[]` | Ordered rows rendered inside the side. |
| `themeId` | string | Active theme id, used for icon color/size tokens. |
| `alignmentStatus` | `ok | fallback_icon | wrapped | warning` | Layout diagnostic used in tests/debug state. |

## ContactRow

| Field | Type | Notes |
|---|---|---|
| `iconName` | string or null | Icon name from `icon:*` syntax. |
| `iconStatus` | `known | fallback | none` | Unknown icons reserve the same icon slot. |
| `label` | string | Visible text. |
| `href` | string or null | Link target for icon-prefixed links. |
| `wrapPolicy` | `text_column | unbreakable_warning` | Long text wraps under the text slot, not under the icon. |

### Validation Rules

- Icon, text, and link belong to one row group.
- Wrapped text aligns with the text column.
- Unknown icon fallback must preserve icon-slot width.
- PDF export must use equivalent contact row markup or visual output.

## PaginatedResumePreview

Represents the preview pages shown to the user and exported as PDF.

| Field | Type | Notes |
|---|---|---|
| `resumeId` | string | Existing resume id. |
| `pages` | `ResumePreviewPage[]` | Ordered preview pages. |
| `pageSize` | `A4` | Existing preview dimensions. |
| `pageCount` | integer | Equal to `pages.length`. |
| `renderVersion` | string | Renderer/pagination version or hash used for debug. |
| `overflowWarnings` | array | Warnings for oversized tables, unbreakable content, or failed measurement. |

## ResumePreviewPage

| Field | Type | Notes |
|---|---|---|
| `pageIndex` | integer | Zero-based page index. |
| `pageNumber` | integer | One-based visible page number. |
| `html` | string | Sanitized rendered page content. |
| `breakBeforeBlockId` | string or null | Optional source block boundary. |
| `breakAfterBlockId` | string or null | Optional source block boundary. |

## PageBreakDecision

| Field | Type | Notes |
|---|---|---|
| `beforeNodeKey` | string or null | DOM/source marker before the break. |
| `afterNodeKey` | string or null | DOM/source marker after the break. |
| `reason` | `page_full | avoid_orphan_heading | keep_table_readable | keep_list_readable | oversized_block | fallback` | Why the break was selected. |
| `warnings` | array | Any non-fatal compromises. |

### State Transitions

```text
source/theme/line-height change
  -> paginationState=measuring
  -> paginationState=paginated | warning | failed

legacy structured resume without Markdown
  -> legacyConversionStatus=pending
  -> converted | warning | failed
  -> MarkdownResumeDocument.sourceMarkdown becomes authoritative when conversion succeeds

smart one-page enabled
  -> measure candidate page counts
  -> smartStatus=fit | already-fit | infeasible
  -> if infeasible, keep paginated preview and export all pages
```
