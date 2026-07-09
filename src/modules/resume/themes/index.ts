/**
 * Resume theme loader — runtime CSS injection + --bg variable management.
 * Ported from 木及简历 (D:\Project\react-resume-site\src\utils\changeThemes.ts).
 *
 * Themes are fetched at runtime from /public/themes/<id>.css and injected
 * into a single <style id="rs-themes-data"> tag (replacing innerHTML on swap).
 * The single CSS variable `--bg` drives all theme-color elements.
 */
import { getThemeById, DEFAULT_THEME_ID } from './registry'
import type { ThemeId } from './registry'

const STYLE_TAG_ID = 'rs-themes-data'
const CSS_VARIABLE = '--bg'

/** Cache of fetched CSS strings (avoid re-fetching on repeated swaps). */
const cssCache = new Map<string, string>()

/** Get or create the <style> tag that holds the active theme CSS. */
function getStyleTag(): HTMLStyleElement {
  let tag = document.getElementById(STYLE_TAG_ID) as HTMLStyleElement | null
  if (!tag) {
    tag = document.createElement('style')
    tag.id = STYLE_TAG_ID
    document.head.appendChild(tag)
  }
  return tag
}

/**
 * Load a theme's CSS and inject into the <style> tag.
 * Safe to call multiple times — cached after first fetch.
 */
export async function loadTheme(themeId: string): Promise<void> {
  const theme = getThemeById(themeId)
  if (!theme) {
    console.warn(`Unknown theme: ${themeId}, falling back to default`)
    return loadTheme(DEFAULT_THEME_ID)
  }

  let css = cssCache.get(themeId)
  if (!css) {
    const response = await fetch(theme.cssUrl)
    if (!response.ok) {
      throw new Error(`Failed to load theme CSS: ${theme.cssUrl} (${response.status})`)
    }
    css = await response.text()
    cssCache.set(themeId, css)
  }

  const tag = getStyleTag()
  tag.innerHTML = css
}

/**
 * Apply an accent color by setting the `--bg` CSS variable on <body>.
 * All theme CSS that reads `var(--bg)` updates instantly.
 */
export function applyColor(hex: string): void {
  document.body.style.setProperty(CSS_VARIABLE, hex)
}

/** Get the current `--bg` value (or null if unset). */
export function getCurrentColor(): string | null {
  return document.body.style.getPropertyValue(CSS_VARIABLE) || null
}

export {
  RESUME_THEMES,
  RESUME_V3_THEMES,
  getThemeById,
  listThemes,
  listV3Themes,
  DEFAULT_THEME_ID,
  DEFAULT_V3_THEME_ID,
} from './registry'
export type { ResumeTheme, ThemeId, LegacyThemeId } from './registry'
