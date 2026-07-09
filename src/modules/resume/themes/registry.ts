import type { MujiThemeId, MujiThemePattern } from '../renderer/types'

/**
 * Resume theme registry.
 *
 * Legacy 027 themes stay available for older callers. REQ-047 adds the
 * Markdown-first v3 theme set as an explicit, exact list.
 */

export type LegacyThemeId = 'default' | 'blue' | 'orange' | 'pupple'
export type ThemeId = LegacyThemeId | MujiThemeId

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
  renderPattern?: MujiThemePattern
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

export const RESUME_V3_THEMES: ResumeTheme[] = [
  {
    id: 'muji-default-autumn',
    name: '默认（秋风同款）',
    defaultColor: '#39393a',
    cssUrl: `${THEME_BASE}/muji-default-autumn.css`,
    isColorCustomizable: false,
    renderPattern: 'dark-header-centered-section',
  },
  {
    id: 'muji-minimal-color',
    name: '极简色',
    defaultColor: '#2563eb',
    cssUrl: `${THEME_BASE}/muji-minimal-color.css`,
    isColorCustomizable: false,
    renderPattern: 'minimal-line',
  },
  {
    id: 'muji-flat-atmospheric',
    name: '平面大气主题',
    defaultColor: '#1f5fbf',
    cssUrl: `${THEME_BASE}/muji-flat-atmospheric.css`,
    isColorCustomizable: false,
    renderPattern: 'accent-band',
  },
]

const THEME_MAP = new Map<ThemeId, ResumeTheme>(
  [...RESUME_THEMES, ...RESUME_V3_THEMES].map((t) => [t.id, t]),
)

export function getThemeById(id: string): ResumeTheme | undefined {
  return THEME_MAP.get(id as ThemeId)
}

export function listThemes(): ResumeTheme[] {
  return RESUME_THEMES
}

export function listV3Themes(): ResumeTheme[] {
  return RESUME_V3_THEMES
}

export const DEFAULT_THEME_ID: LegacyThemeId = 'default'
export const DEFAULT_V3_THEME_ID: MujiThemeId = 'muji-default-autumn'
