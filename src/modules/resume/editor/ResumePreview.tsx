import { useEffect, useMemo, useRef, useState } from 'react'
import { getStyleById, DEFAULT_STYLE_ID } from '@/modules/resume/styles'
import { renderMarkdown, sanitizeHtml } from '@/modules/resume/renderer'
import { paginateDom, applySinglePageMode, attachWindowScaleListener } from '@/modules/resume/pagination'
import PageIndicator from './PageIndicator'
import AvatarImage from './AvatarImage'
import type { AvatarPosition, AvatarShape } from '../api/types'

interface ResumePreviewProps {
  markdown: string
  styleId?: string
  /** Optional accent color HEX (e.g. '#39393a'). Used by `#{color}` token replacement. */
  accentColor?: string
  className?: string
  /** Optional callback when page count changes (for parent toolbar display). */
  onPageCountChange?: (count: number) => void
  /** Optional avatar URL (branch.avatar_url). When set, renders <AvatarImage />. */
  avatarUrl?: string | null
  avatarSize?: number | null
  avatarPosition?: AvatarPosition | null
  avatarShape?: AvatarShape | null
}

/** Default accent color when branch.accent_color is not yet exposed (US1). */
const DEFAULT_ACCENT_COLOR = '#39393a'

/** Sections that belong in the sidebar for two-column layouts */
const SIDEBAR_SECTIONS = ['个人简介', '简介', 'summary', '技能', 'skills', '教育背景', '教育', 'education']

/**
 * Render a markdown chunk to sanitized HTML using the unified render engine.
 */
function renderChunk(md: string, accentColor: string): string {
  if (!md.trim()) return ''
  const { html } = renderMarkdown(md, { accentColor })
  return sanitizeHtml(html)
}

export default function ResumePreview({
  markdown,
  styleId = DEFAULT_STYLE_ID,
  accentColor,
  className = '',
  onPageCountChange,
  avatarUrl,
  avatarSize,
  avatarPosition,
  avatarShape,
}: ResumePreviewProps) {
  const style = useMemo(() => getStyleById(styleId) ?? getStyleById(DEFAULT_STYLE_ID)!, [styleId])
  const accent = accentColor ?? DEFAULT_ACCENT_COLOR

  const isEmpty = !markdown?.trim()

  // Pagination state
  const viewRef = useRef<HTMLDivElement>(null)
  const [pageCount, setPageCount] = useState(1)
  const [singlePageMode, setSinglePageMode] = useState(false)

  // Split markdown into sidebar + main sections for two-column layout.
  const { sidebarMd, mainMd } = useMemo(() => {
    if (isEmpty || style.layoutType !== 'two-column') return { sidebarMd: '', mainMd: '' }

    const lines = markdown.split('\n')
    const sections: { heading: string; content: string[] }[] = []
    let currentHeading = ''
    let currentContent: string[] = []

    for (const line of lines) {
      if (/^##\s/.test(line)) {
        if (currentHeading) {
          sections.push({ heading: currentHeading, content: currentContent })
        }
        currentHeading = line.replace(/^##\s+/, '').trim()
        currentContent = []
      } else {
        currentContent.push(line)
      }
    }
    if (currentHeading) {
      sections.push({ heading: currentHeading, content: currentContent })
    }

    let headerEndIdx = 0
    for (let i = 0; i < lines.length; i++) {
      if (/^##\s/.test(lines[i])) {
        headerEndIdx = i
        break
      }
    }

    const headerLines = lines.slice(0, headerEndIdx)
    const sidebarSections: string[] = []
    const mainSections: string[] = []

    for (const section of sections) {
      const headingLower = section.heading.toLowerCase()
      const isSidebar = SIDEBAR_SECTIONS.some((k) =>
        headingLower.includes(k.toLowerCase()),
      )
      const sectionText = `## ${section.heading}\n${section.content.join('\n')}`
      if (isSidebar) {
        sidebarSections.push(sectionText)
      } else {
        mainSections.push(sectionText)
      }
    }

    return {
      sidebarMd: headerLines.join('\n') + '\n' + sidebarSections.join('\n'),
      mainMd: mainSections.join('\n'),
    }
  }, [markdown, isEmpty, style.layoutType])

  // Render each chunk to sanitized HTML via the unified engine.
  const sidebarHtml = useMemo(() => renderChunk(sidebarMd, accent), [sidebarMd, accent])
  const mainHtml = useMemo(() => renderChunk(mainMd, accent), [mainMd, accent])
  const fullHtml = useMemo(() => renderChunk(markdown, accent), [markdown, accent])

  // Smart pagination — re-run when HTML changes (debounced via requestAnimationFrame).
  useEffect(() => {
    if (!viewRef.current || isEmpty) {
      setPageCount(1)
      onPageCountChange?.(1)
      return
    }

    // Defer to next frame to ensure DOM is laid out after dangerouslySetInnerHTML.
    const rafId = requestAnimationFrame(() => {
      if (!viewRef.current) return
      const { pageCount: count } = paginateDom(viewRef.current)
      setPageCount(count)
      onPageCountChange?.(count)
      // Apply single-page mode if enabled.
      applySinglePageMode(viewRef.current, singlePageMode)
    })

    return () => cancelAnimationFrame(rafId)
  }, [fullHtml, sidebarHtml, mainHtml, isEmpty, singlePageMode, onPageCountChange])

  // Window-scale auto-resize listener (A4 fit on narrow windows).
  useEffect(() => {
    const detach = attachWindowScaleListener()
    return detach
  }, [])

  return (
    <div className={`resume-preview-container overflow-auto h-full bg-ink-4/5 relative ${className}`}>
      {/* Page indicator — floating top-right over the preview */}
      {!isEmpty && (
        <div className="absolute top-2 right-3 z-10">
          <PageIndicator
            pageCount={pageCount}
            singlePageMode={singlePageMode}
            onSinglePageModeChange={setSinglePageMode}
          />
        </div>
      )}
      {isEmpty ? (
        <div className={`${style.cssClass} flex items-center justify-center`}>
          <div className="text-ink-muted text-sm text-center py-20">
            {style.id === 'editorial' ? (
              <span style={{ fontFamily: 'Georgia, serif' }}>
                预览区域 — 在左侧编辑器中输入 Markdown 内容
              </span>
            ) : (
              <>预览区域 — 在左侧编辑器中输入 Markdown 内容</>
            )}
          </div>
        </div>
      ) : style.layoutType === 'two-column' ? (
        <div className={style.cssClass} data-testid="resume-preview-root">
          {/* Avatar — top / center / bottom sit above/below content; left/right float beside it */}
          {avatarUrl && (avatarPosition === 'top' || avatarPosition === 'center') && (
            <div className={`rs-avatar rs-avatar-${avatarPosition}`}>
              <AvatarImage
                avatarUrl={avatarUrl}
                size={avatarSize ?? 100}
                position={avatarPosition}
                shape={avatarShape ?? 'circle'}
                block={false}
                className="rs-avatar-img"
              />
            </div>
          )}
          {(sidebarMd.trim() || mainMd.trim()) ? (
            <>
              {avatarUrl && (avatarPosition === 'left' || avatarPosition === 'right') && (
                <div className={`rs-avatar rs-avatar-${avatarPosition}`}>
                  <AvatarImage
                    avatarUrl={avatarUrl}
                    size={avatarSize ?? 100}
                    position={avatarPosition}
                    shape={avatarShape ?? 'circle'}
                    block={false}
                    className="rs-avatar-img"
                  />
                </div>
              )}
              <div
                ref={viewRef}
                className="resume-sidebar rs-view rs-view-inner"
                dangerouslySetInnerHTML={{ __html: sidebarHtml }}
              />
              <div
                className="resume-main rs-view rs-view-inner"
                dangerouslySetInnerHTML={{ __html: mainHtml }}
              />
              {avatarUrl && avatarPosition === 'bottom' && (
                <div className={`rs-avatar rs-avatar-${avatarPosition}`}>
                  <AvatarImage
                    avatarUrl={avatarUrl}
                    size={avatarSize ?? 100}
                    position={avatarPosition}
                    shape={avatarShape ?? 'circle'}
                    block={false}
                    className="rs-avatar-img"
                  />
                </div>
              )}
            </>
          ) : (
            <>
              {avatarUrl && (avatarPosition === 'left' || avatarPosition === 'right') && (
                <div className={`rs-avatar rs-avatar-${avatarPosition}`}>
                  <AvatarImage
                    avatarUrl={avatarUrl}
                    size={avatarSize ?? 100}
                    position={avatarPosition}
                    shape={avatarShape ?? 'circle'}
                    block={false}
                    className="rs-avatar-img"
                  />
                </div>
              )}
              <div
                ref={viewRef}
                className="rs-view rs-view-inner"
                dangerouslySetInnerHTML={{ __html: fullHtml }}
              />
              {avatarUrl && avatarPosition === 'bottom' && (
                <div className={`rs-avatar rs-avatar-${avatarPosition}`}>
                  <AvatarImage
                    avatarUrl={avatarUrl}
                    size={avatarSize ?? 100}
                    position={avatarPosition}
                    shape={avatarShape ?? 'circle'}
                    block={false}
                    className="rs-avatar-img"
                  />
                </div>
              )}
            </>
          )}
        </div>
      ) : (
        <div className={style.cssClass} data-testid="resume-preview-root">
          {/* Avatar — top/center above content, bottom below, left/right float beside */}
          {avatarUrl && (avatarPosition === 'top' || avatarPosition === 'center') && (
            <div className={`rs-avatar rs-avatar-${avatarPosition}`}>
              <AvatarImage
                avatarUrl={avatarUrl}
                size={avatarSize ?? 100}
                position={avatarPosition}
                shape={avatarShape ?? 'circle'}
                block={false}
                className="rs-avatar-img"
              />
            </div>
          )}
          <div className="rs-content-row">
            {avatarUrl && (avatarPosition === 'left' || avatarPosition === 'right') && (
              <div className={`rs-avatar rs-avatar-${avatarPosition}`}>
                <AvatarImage
                  avatarUrl={avatarUrl}
                  size={avatarSize ?? 100}
                  position={avatarPosition}
                  shape={avatarShape ?? 'circle'}
                  block={false}
                  className="rs-avatar-img"
                />
              </div>
            )}
            <div
              ref={viewRef}
              className="rs-view rs-view-inner"
              dangerouslySetInnerHTML={{ __html: fullHtml }}
            />
          </div>
          {avatarUrl && avatarPosition === 'bottom' && (
            <div className={`rs-avatar rs-avatar-${avatarPosition}`}>
              <AvatarImage
                avatarUrl={avatarUrl}
                size={avatarSize ?? 100}
                position={avatarPosition}
                shape={avatarShape ?? 'circle'}
                block={false}
                className="rs-avatar-img"
              />
            </div>
          )}
        </div>
      )}
    </div>
  )
}
