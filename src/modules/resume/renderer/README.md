# Resume Render Engine

Unified Markdown→HTML pipeline shared by preview and PDF export to eliminate rendering drift (spec 027 US1).

## Public API

```typescript
import { renderMarkdown, sanitizeHtml } from '@/modules/resume/renderer'

const { html } = renderMarkdown('# Hello\n\nContent...', {
  accentColor: '#2563eb',
})
const safe = sanitizeHtml(html)
```

## Pipeline

```
Markdown → markdown-it (+ 木及 plugins) → colorPlugin (#{color}) → HTML string
```

### Plugins (ported from 木及简历)

1. **heading-block** — wraps `#/##/###/####/#####` in `<div class="h<N>_block block">`
2. **blank-line** — preserves consecutive blank lines as `<span class="break-line">` × N
3. **color-token** — replaces `#{color}` with current accent color hex
4. **containers** — `::: left/right/header/title` → two-column layout divs
5. **emoji + svgMap** — `icon:<name>` → inline SVG (14 brand icons)

## CLI

```bash
npx tsx src/lib/resume-renderer/cli.ts \
  --input resume.md \
  --color '#2563eb' \
  --output resume.html
```

Used for E2E test fixtures and local debugging.

## Testing

```bash
npx vitest run src/lib/resume-renderer/__tests__/
```

## Contract

See `specs/027-resume-center-muji-alignment/contracts/render-engine.md` for the full interface contract.
