# Resume Renderer

The renderer is the single Markdown-to-HTML pipeline used by the REQ-047 live
preview and PDF export request body.

## Public API

```ts
import { renderMarkdown } from "@/modules/resume/renderer";

const result = renderMarkdown(sourceMarkdown, {
  themeId: "muji-default-autumn",
  lineHeight: 19,
});
```

`result.html` is sanitized HTML. `result.warnings` contains structured warnings
for unsupported syntax or unsafe URLs.

## Supported Markdown Dialect

- `#` maps to the resume title block.
- `##` maps to major section headings.
- `###` maps to item or subsection headings.
- `::: left` and `::: right` create Muji-style contact/header columns with
  semantic `.resume-contact-row`, icon slot, and text slot markup.
- `icon:*` tokens render supported inline icons through the local icon map.
  Unknown icons reserve a fallback slot and emit a render warning so alignment
  remains stable.
- Bold, italic, bold-italic, strikethrough, links, inline code, blockquotes,
  horizontal rules, ordered lists, unordered lists, nested lists, and tables are
  rendered.
- Task-list syntax remains literal text (`[x]` / `[ ]`) instead of becoming
  checkbox widgets.
- Markdown images render only when the URL is external HTTP(S).

## Safety And Fallback

- Raw scripts, embedded objects, event-handler attributes, and unsafe
  `javascript:`/local/data/ftp URLs are removed.
- Local Markdown images such as `file:///...` are removed before Markdown
  rendering so the path is not leaked as literal preview text.
- Unsupported syntax should degrade predictably to text or be omitted only when
  it is unsafe.

## Validation

```bash
npm run test -- src/modules/resume/renderer/__tests__/contact-container-rendering.test.ts
```
