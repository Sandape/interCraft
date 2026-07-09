# Contract: PDF and Markdown Export

## Export Formats

```ts
type ResumeExportFormat = 'pdf' | 'markdown'
```

## Export Request

```ts
interface ResumeExportRequest {
  resumeId: string
  format: ResumeExportFormat
  sourceMarkdown: string
  themeId: 'muji-default-autumn' | 'muji-minimal-color' | 'muji-flat-atmospheric'
  lineHeight: number // 12-25
  smartOnePageEnabled: boolean
}
```

## Export Result

```ts
interface ResumeExportResult {
  status: 'pending' | 'success' | 'failed'
  format: ResumeExportFormat
  filename?: string
  blob?: Blob
  markdown?: string
  errorCode?: string
  message?: string
}
```

## Markdown Export Requirements

- Exports the preserved source Markdown.
- Must retain Muji-compatible syntax, including containers/icons and external URL image syntax.
- Round-trip paste/import of exported Markdown should render supported content without meaningful loss.

## PDF Export Requirements

- Uses current source Markdown and current effective render settings.
- Matches live preview for supported Markdown, selected theme, line height, smart one-page state, tables, icons, and external images.
- Shows visible pending, success, and failure states.
- Failure must not mutate or clear source Markdown.

## Acceptance Tests

- Export Markdown from a format-lab resume and compare text to source.
- Export PDF for each of the three themes with line-height 19.
- Export PDF with smart one-page enabled and verify output uses the effective one-page settings.
- Simulate/export failure and verify user-facing recovery message.

