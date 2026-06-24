/**
 * Resume theme registry — 4 木及风格主题（default / blue / orange / pupple）.
 * Themes are independent CSS files in /public/themes/, fetched at runtime
 * and injected into a single <style id="rs-themes-data"> tag.
 */

export type ThemeId = 'default' | 'blue' | 'orange' | 'pupple'

export interface ResumeTheme {
  id: ThemeId
  /** Chinese display name. */
  name: string
  /** Default accent color HEX for this theme. */
  defaultColor: string
  /** Runtime CSS URL (resolved from /public/themes/<id>.css). */
  cssUrl: string
  /** Whether the theme supports custom accent color via color picker. */
  isColorCustomizable: boolean
}

const THEME_BASE = '/themes'

export const RESUME_THEMES: ResumeTheme[] = [
  {
    id: 'default',
    name: '默认',
    defaultColor: '#39393a',
    cssUrl: `${THEME_BASE}/default.css`,
    isColorCustomizable: true,
  },
  {
    id: 'blue',
    name: '蓝色',
    defaultColor: '#2563eb',
    cssUrl: `${THEME_BASE}/blue.css`,
    isColorCustomizable: true,
  },
  {
    id: 'orange',
    name: '橙色',
    defaultColor: '#f9855d',
    cssUrl: `${THEME_BASE}/orange.css`,
    isColorCustomizable: true,
  },
  {
    id: 'pupple',
    name: '紫色',
    defaultColor: '#9333ea',
    cssUrl: `${THEME_BASE}/pupple.css`,
    isColorCustomizable: true,
  },
]

const THEME_MAP = new Map<ThemeId, ResumeTheme>(
  RESUME_THEMES.map((t) => [t.id, t]),
)

export function getThemeById(id: string): ResumeTheme | undefined {
  return THEME_MAP.get(id as ThemeId)
}

export function listThemes(): ResumeTheme[] {
  return RESUME_THEMES
}

export const DEFAULT_THEME_ID: ThemeId = 'default'
