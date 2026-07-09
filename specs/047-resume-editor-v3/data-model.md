# Data Model: Resume Editor v3 for InterCraft v2

This model describes feature-level state and contracts. It does not require a new backend schema unless current resume v2 persistence cannot store the fields below.

## Entity: ResumeMarkdownDocument

| Field | Type | Required | Validation |
|---|---|---|---|
| `resumeId` | string | yes | Existing resume identifier. |
| `sourceMarkdown` | string | yes | Preserved exactly except for intentional user edits/import/export round trips. |
| `renderSettings` | `ResumeRenderSettings` | yes | Settings used by preview and export. |
| `updatedAt` | ISO datetime | yes | Existing resume updated timestamp if available. |

## Entity: ResumeRenderSettings

| Field | Type | Required | Validation |
|---|---|---|---|
| `themeId` | `MujiThemeId` | yes | One of `muji-default-autumn`, `muji-minimal-color`, `muji-flat-atmospheric`. |
| `manualLineHeight` | integer | yes | 12-25 inclusive. |
| `smartOnePageEnabled` | boolean | yes | Defaults false. |
| `smartLineHeight` | integer or null | no | 12-25 inclusive when smart mode has selected a value; null when inactive or not computed. |
| `effectiveLineHeight` | integer | derived | `smartLineHeight` when smart mode is active and computed; otherwise `manualLineHeight`. |

## Entity: MujiTheme

| Field | Type | Required | Validation |
|---|---|---|---|
| `id` | `MujiThemeId` | yes | Stable internal id. |
| `displayName` | string | yes | User-visible names: 默认（秋风同款）, 极简色, 平面大气主题. |
| `renderPattern` | string | yes | One of `dark-header-centered-section`, `minimal-line`, `accent-band`. |
| `supportsMultiPage` | boolean | yes | True for all three first-version themes. |

## Entity: MarkdownRenderResult

| Field | Type | Required | Validation |
|---|---|---|---|
| `html` | string | yes | Sanitized render output. |
| `warnings` | array | yes | Unsupported syntax, unsafe URL, broken image, or parser fallback warnings. |
| `blockIndex` | array | no | Optional source-to-preview block mapping for preview navigation/tests. |

## Entity: SmartOnePageResult

| Field | Type | Required | Validation |
|---|---|---|---|
| `status` | string | yes | `fit`, `already-fit`, or `infeasible`. |
| `selectedLineHeight` | integer or null | no | 12-25 when a fitting value is selected. |
| `pageCount` | integer | yes | Must remain >= 1. |
| `message` | string or null | no | Required when status is `infeasible`. |

## Entity: ExportRequest

| Field | Type | Required | Validation |
|---|---|---|---|
| `resumeId` | string | yes | Existing resume identifier. |
| `format` | string | yes | `pdf` or `markdown`. |
| `sourceMarkdown` | string | yes | Current source used for export. |
| `renderSettings` | `ResumeRenderSettings` | yes | Current theme/spacing/smart-one-page settings. |

## Entity: ExportResult

| Field | Type | Required | Validation |
|---|---|---|---|
| `status` | string | yes | `pending`, `success`, or `failed`. |
| `format` | string | yes | `pdf` or `markdown`. |
| `filename` | string | no | Required on success. |
| `errorCode` | string | no | Required on failure. |
| `message` | string | no | Required on failure or long-running pending state. |

## State Transitions

```text
manual line spacing selected
  -> preview uses manualLineHeight
  -> smart one-page enabled
  -> compute selected smartLineHeight
  -> preview uses smartLineHeight while enabled
  -> smart one-page disabled
  -> preview restores manualLineHeight
```

```text
export idle
  -> pending
  -> success(download produced)
  OR failed(error shown, source preserved)
```

