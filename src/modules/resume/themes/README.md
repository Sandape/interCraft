# Resume Themes

Runtime CSS injection + `--bg` single-variable theme system. Ported from 木及简历.

## Architecture

- 4 themes: `default`, `blue`, `orange`, `pupple`
- CSS files in `/public/themes/<id>.css`, fetched at runtime
- Injected into a single `<style id="rs-themes-data">` tag
- All theme-color elements read `var(--bg)` — one variable drives everything

## Public API

```typescript
import { loadTheme, applyColor, listThemes, getThemeById } from '@/modules/resume/themes'

// Switch theme (fetch CSS + inject)
await loadTheme('blue')

// Apply accent color (sets --bg on body)
applyColor('#2563eb')

// List all themes for selector UI
const themes = listThemes()
```

## Adding a New Theme

1. Create `public/themes/<new-id>.css` (copy an existing theme as starting point)
2. Add entry to `RESUME_THEMES` in `registry.ts`
3. Update the `theme_id` CHECK constraint in the Alembic migration
4. No rebuild required — theme is loaded at runtime

## Contract

See `specs/027-resume-center-muji-alignment/data-model.md` (ResumeTheme entity) and `contracts/render-engine.md`.
