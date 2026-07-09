# Contract: Markdown Rendering

## Purpose

Define the Markdown source-to-preview contract for the scoped v3 editor. The same rendering behavior must be used by live preview and PDF export.

## Input

```ts
interface MarkdownRenderInput {
  sourceMarkdown: string
  themeId: 'muji-default-autumn' | 'muji-minimal-color' | 'muji-flat-atmospheric'
  lineHeight: number // integer 12-25
}
```

## Output

```ts
interface MarkdownRenderOutput {
  html: string
  warnings: Array<{
    code: 'unsupported_syntax' | 'unsafe_url' | 'broken_image' | 'fallback'
    message: string
    sourceExcerpt?: string
  }>
}
```

## Required Markdown Behavior

| Source | Required rendering |
|---|---|
| `#` | Resume title area. |
| `##` | Major section title styled by active theme. |
| `###` | Section item title. |
| Paragraph | Body text. |
| `**bold**` | Bold inline text. |
| `*italic*` | Italic inline text. |
| `***bold italic***` | Bold and italic inline text. |
| `~~delete~~` | Strikethrough inline text. |
| `[text](url)` | Link text, sanitized URL. |
| Backtick inline code | Tag/pill visual, matching Muji behavior. |
| `>` | Blockquote text, matching Muji's low-decoration rendering. |
| `---` | Horizontal rule. |
| `-` | Square bullet first-level unordered list. |
| Nested `-` | Circle bullet nested list. |
| `1.` | Decimal ordered list. |
| `- [x]` / `- [ ]` | Literal task-list text, not checkbox controls. |
| Markdown table | Borderless resume column layout. |
| `![alt](https://...)` | External URL image render when reachable. |
| `::: left/right` | Muji-compatible contact layout container. |
| `icon:*` | Muji-compatible icon token. |
| `[icon:name text](url)` | Icon-prefixed link. |

## Security and Fallback

- Raw scripts, unsafe URLs, and event attributes must not execute.
- Unsupported Markdown must not be deleted.
- External images may fail gracefully with warning/fallback; source remains preserved.

## Acceptance Tests

- Render the format-lab fixture from `docs/evidence/v3-editor-research/muji-2026-07-06/sample-markdown-format-lab.md`.
- Verify all required syntax outputs are present.
- Verify task-list syntax remains literal.
- Verify unsafe URL/script fixtures produce warnings or sanitized output.

