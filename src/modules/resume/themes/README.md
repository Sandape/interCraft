# Resume Themes

REQ-047 exposes exactly three Muji-compatible v3 resume themes while leaving the
legacy theme registry stable for older callers.

## V3 Theme IDs

| Theme ID | Display Name | Pattern |
|---|---|---|
| `muji-default-autumn` | Default autumn | Dark header / classic Muji pattern |
| `muji-minimal-color` | Minimal color | White page with restrained section lines |
| `muji-flat-atmospheric` | Flat atmospheric | Accent-band title treatment |

The public selector surface is `listV3Themes()`. It must always return these
three themes only for REQ-047.

## CSS Files

- `public/themes/muji-default-autumn.css`
- `public/themes/muji-minimal-color.css`
- `public/themes/muji-flat-atmospheric.css`

The Markdown preview root carries `data-theme="<theme-id>"`, a theme class, and
the line-height class (`height12` through `height25`). Theme CSS is responsible
for keeping headings, tables, lists, icons, and body text readable across line
spacing changes.

## Validation

```bash
npm run test -- src/modules/resume/themes/__tests__/muji-v3-themes.test.ts src/modules/resume/v2/editor/__tests__/MarkdownResumePreviewThemes.test.tsx
```
