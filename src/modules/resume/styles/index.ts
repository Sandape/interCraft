/** Style registry for resume visual templates — 4 styles matching eGG UI/UX */

export interface ResumeStyle {
  id: string
  labelZh: string
  labelEn: string
  description: string
  cssClass: string
  layoutType: 'single-column' | 'two-column'
}

export const RESUME_STYLES: ResumeStyle[] = [
  {
    id: 'classic-one-page',
    labelZh: '经典纯净',
    labelEn: 'Classic One-Page',
    description: '极简排版居中对称，叙事节奏自然，通用性强',
    cssClass: 'resume-style-classic',
    layoutType: 'single-column',
  },
  {
    id: 'compact-one-page',
    labelZh: '紧凑一页',
    labelEn: 'Compact One-Page',
    description: '信息密度高，单栏全宽 A4 单页，海投首选',
    cssClass: 'resume-style-compact',
    layoutType: 'single-column',
  },
  {
    id: 'modern-two-column',
    labelZh: '现代双栏',
    labelEn: 'Modern Two-Column',
    description: '左信息右经历双栏布局，适合资深岗位',
    cssClass: 'resume-style-modern',
    layoutType: 'two-column',
  },
  {
    id: 'editorial',
    labelZh: '编辑式',
    labelEn: 'Editorial',
    description: '衬线字体突出项目叙述，适合外企与研究岗',
    cssClass: 'resume-style-editorial',
    layoutType: 'single-column',
  },
]

export function getStyleById(id: string): ResumeStyle | undefined {
  return RESUME_STYLES.find((s) => s.id === id)
}

export const DEFAULT_STYLE_ID = 'classic-one-page'
