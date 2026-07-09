/**
 * T175 — v1 → v2 fallback mapping.
 *
 * When the marketplace's v2 list re-uses a legacy v1 item (e.g. a user
 * is browsing templates and the v2 manifest lacks a particular entry),
 * this module derives a v2-shaped template descriptor with sane
 * defaults so the editor's `createResume` call still works.
 *
 * Mapping table:
 *
 *   v1 field         | v2 equivalent               | default
 *   -----------------+-----------------------------+-----------------------------
 *   id (number)      | id (string)                 | "legacy-{id}"
 *   title            | name                        | (required — caller must
 *                    |                             |  supply from v1 list)
 *   theme            | category                    | "business" if not in set
 *   thumbnail        | thumbnail                   | "/templates/jpg/onyx.jpg"
 *   template (md)    | (dropped; v2 has structured | —
 *                    |  sections, no Markdown)
 *   collect / author | tags[]                      | ["Legacy", "v1-import"]
 *   avatar / themeColor | (dropped)                | —
 *
 * The returned `defaults.metadata` is a structural shape that the
 * backend can deep-merge with `defaultResumeDataV2()` to produce a
 * usable v2 resume skeleton.
 */

export interface V1TemplateLike {
  id?: number | string
  title?: string
  theme?: string
  thumbnail?: string
  template?: string
  author?: string
  avatar?: string
  themeColor?: string
  collect?: number
  updateTime?: number
}

export interface V2TemplateMapped {
  id: string
  name: string
  description: string
  tags: string[]
  category: string
  thumbnail: string
  sidebar: 'left' | 'right' | 'none'
  recommendedColors?: Record<string, string>
  defaults: {
    metadata: Record<string, unknown>
  }
}

const KNOWN_CATEGORIES = new Set([
  'minimal',
  'business',
  'creative',
  'editorial',
])

const DEFAULT_THUMBNAIL = '/templates/jpg/onyx.jpg'

/**
 * Convert a v1 template item to a v2-shaped descriptor. Returns
 * `null` when the input is empty / has no usable title.
 */
export function mapV1ToV2(v1: V1TemplateLike | null | undefined): V2TemplateMapped | null {
  if (!v1 || typeof v1 !== 'object') return null
  const name = (v1.title ?? '').toString().trim()
  if (!name) return null
  const id = typeof v1.id === 'string' ? v1.id : `legacy-${v1.id ?? Date.now()}`
  const theme = (v1.theme ?? 'business').toString().toLowerCase()
  const category = KNOWN_CATEGORIES.has(theme) ? theme : 'business'
  const tags: string[] = ['Legacy', 'v1-import']
  if (v1.author) tags.push(String(v1.author))
  return {
    id,
    name,
    description: `从 v1 模板「${name}」自动映射`,
    tags,
    category,
    thumbnail: v1.thumbnail ?? DEFAULT_THUMBNAIL,
    sidebar: 'left',
    recommendedColors: v1.themeColor ? { primary: v1.themeColor } : undefined,
    defaults: {
      metadata: {
        template: id,
        layout: {
          sidebarWidth: 35,
          pages: [
            {
              fullWidth: false,
              main: ['summary', 'experience', 'education', 'projects'],
              sidebar: ['profiles', 'skills', 'languages'],
            },
          ],
        },
        design: v1.themeColor
          ? { colors: { primary: v1.themeColor } }
          : undefined,
      },
    },
  }
}
