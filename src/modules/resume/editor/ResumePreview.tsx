import { useEffect, useMemo, useRef, useState } from 'react'
import { getStyleById, DEFAULT_STYLE_ID } from '@/modules/resume/styles'
import { renderMarkdown, renderBlocksToHtml, sanitizeHtml } from '@/modules/resume/renderer'
import { paginateDom, applySinglePageMode, attachWindowScaleListener } from '@/modules/resume/pagination'
import PageIndicator from './PageIndicator'
import AvatarImage from './AvatarImage'
import type { AvatarPosition, AvatarShape, ResumeBlock } from '../api/types'

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
  /**
   * Structured blocks (US8). When provided, the preview renders each block
   * individually inside `<section data-block-id="…">` so reverse-locate
   * (preview click → block list) and forward-locate (block list click →
   * preview scroll + highlight) work.
   */
  blocks?: ResumeBlock[]
  /**
   * When set, the preview scrolls to the matching `[data-block-id]` element,
   * applies a 1.5s yellow highlight, and resets the value to null via the
   * callback. Resuming the locator when modals are open is the parent's job.
   */
  scrollToBlockId?: string | null
  onScrollToBlockHandled?: () => void
  /** Reverse-locate: called when the user clicks a rendered block in the preview. */
  onBlockClick?: (blockId: string) => void
  /** When true, suspend all locator interactions (parent opens a modal). */
  locatorSuspended?: boolean
}

/** Default accent color when branch.accent_color is not yet exposed (US1). */
const DEFAULT_ACCENT_COLOR = '#39393a'

/** Sections that belong in the sidebar for two-column layouts */
const SIDEBAR_SECTIONS = ['个人简介', '简介', 'summary', '技能', 'skills', '教育背景', '教育', 'education']

/** Block types that should sit in the sidebar for two-column layouts (US8). */
const SIDEBAR_BLOCK_TYPES = new Set(['summary', 'skill', 'education'])

/** CSS.escape polyfill (block ids are UUIDs but defensive). */
function cssEscape(v: string): string {
  if (typeof CSS !== 'undefined' && typeof CSS.escape === 'function') return CSS.escape(v)
  return v.replace(/([!"#$%&'()*+,./:;<=>?@\[\\\]^`{|}~])/g, '\\$1')
}

/**
 * Render a markdown chunk to sanitized HTML using the unified render engine.
 */
function renderChunk(md: string, accentColor: string): string {
  if (!md.trim()) return ''
  const { html } = renderMarkdown(md, { accentColor })
  return sanitizeHtml(html)
}

/**
 * Render an array of blocks into HTML with `data-block-id` wrappers (US8).
 * Empty content is skipped so the preview never renders empty sections.
 */
function renderBlocks(blocks: ResumeBlock[], accentColor: string): string {
  const inputs = blocks
    .filter((b) => b.content_md && b.content_md.trim())
    .map((b) => ({ id: b.id, content_md: b.content_md }))
  const { html } = renderBlocksToHtml(inputs, { accentColor })
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
  blocks,
  scrollToBlockId,
  onScrollToBlockHandled,
  onBlockClick,
  locatorSuspended,
}: ResumePreviewProps) {
  const style = useMemo(() => getStyleById(styleId) ?? getStyleById(DEFAULT_STYLE_ID)!, [styleId])
  const accent = accentColor ?? DEFAULT_ACCENT_COLOR

  // When blocks are provided we treat them as authoritative; `markdown` is
  // still required by the prop signature but ignored in that mode.
  const usingBlocks = Boolean(blocks && blocks.length)
  const isEmpty = usingBlocks ? !blocks || blocks.length === 0 : !markdown?.trim()

  // Pagination state
  const viewRef = useRef<HTMLDivElement>(null)
  const [pageCount, setPageCount] = useState(1)
  const [singlePageMode, setSinglePageMode] = useState(false)

  // Track the currently highlighted block id so we can clear stale highlights.
  const highlightRef = useRef<{ id: string; timer: number } | null>(null)

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

  // US8: per-block rendering for two-column sidebar vs main.
  const blocksSidebarHtml = useMemo(() => {
    if (!usingBlocks || style.layoutType !== 'two-column') return ''
    return renderBlocks(
      (blocks ?? []).filter((b) => SIDEBAR_BLOCK_TYPES.has(b.type)),
      accent,
    )
  }, [usingBlocks, blocks, accent, style.layoutType])
  const blocksMainHtml = useMemo(() => {
    if (!usingBlocks || style.layoutType !== 'two-column') return ''
    return renderBlocks(
      (blocks ?? []).filter((b) => !SIDEBAR_BLOCK_TYPES.has(b.type)),
      accent,
    )
  }, [usingBlocks, blocks, accent, style.layoutType])
  // US8: per-block rendering for single-column flow.
  const blocksFlowHtml = useMemo(() => {
    if (!usingBlocks || style.layoutType !== 'single-column') return ''
    return renderBlocks(blocks ?? [], accent)
  }, [usingBlocks, blocks, accent, style.layoutType])

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
  }, [fullHtml, sidebarHtml, mainHtml, blocksFlowHtml, blocksSidebarHtml, blocksMainHtml, isEmpty, singlePageMode, onPageCountChange])

  // US8: scroll-to-block + 1.5s yellow highlight (forward-locate).
  useEffect(() => {
    if (!scrollToBlockId || !viewRef.current || isEmpty) return
    const root = viewRef.current
    // Search inside the full preview container, not just viewRef, because
    // the section may live inside one of the two-column sub-views.
    const container = root.closest('.resume-preview-container') as HTMLElement | null
    const searchRoot = container ?? root
    const target = searchRoot.querySelector<HTMLElement>(
      `[data-block-id="${cssEscape(scrollToBlockId)}"]`,
    )
    if (!target) {
      onScrollToBlockHandled?.()
      return
    }
    // Cancel previous highlight before starting a new one (FR-069).
    if (highlightRef.current) {
      clearTimeout(highlightRef.current.timer)
      highlightRef.current.id &&
        searchRoot.querySelector(`[data-block-id="${cssEscape(highlightRef.current.id)}"]`)
          ?.classList.remove('rs-block-flash')
    }
    target.scrollIntoView({ behavior: 'smooth', block: 'start' })
    target.classList.add('rs-block-flash')
    const id = scrollToBlockId
    const timer = window.setTimeout(() => {
      target.classList.remove('rs-block-flash')
      if (highlightRef.current?.id === id) highlightRef.current = null
      onScrollToBlockHandled?.()
    }, 1500)
    highlightRef.current = { id, timer }
  }, [scrollToBlockId, isEmpty, onScrollToBlockHandled, blocksFlowHtml, blocksSidebarHtml, blocksMainHtml])

  // US8: reverse-locate — click on rendered block → onBlockClick(id).
  useEffect(() => {
    if (!onBlockClick || !viewRef.current || locatorSuspended) return
    const container = viewRef.current.closest('.resume-preview-container') as HTMLElement | null
    const searchRoot = container ?? viewRef.current
    const handler = (e: MouseEvent) => {
      const target = (e.target as HTMLElement | null)?.closest<HTMLElement>('[data-block-id]')
      if (!target) return
      const id = target.getAttribute('data-block-id')
      if (id) onBlockClick(id)
    }
    searchRoot.addEventListener('click', handler)
    return () => searchRoot.removeEventListener('click', handler)
  }, [onBlockClick, locatorSuspended, blocksFlowHtml, blocksSidebarHtml, blocksMainHtml])

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
              {usingBlocks ? (
                <>
                  <div
                    ref={viewRef}
                    className="resume-sidebar rs-view rs-view-inner"
                    dangerouslySetInnerHTML={{ __html: blocksSidebarHtml }}
                  />
                  <div
                    className="resume-main rs-view rs-view-inner"
                    dangerouslySetInnerHTML={{ __html: blocksMainHtml }}
                  />
                </>
              ) : (
                <>
                  <div
                    ref={viewRef}
                    className="resume-sidebar rs-view rs-view-inner"
                    dangerouslySetInnerHTML={{ __html: sidebarHtml }}
                  />
                  <div
                    className="resume-main rs-view rs-view-inner"
                    dangerouslySetInnerHTML={{ __html: mainHtml }}
                  />
                </>
              )}
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
              {usingBlocks ? (
                <div
                  ref={viewRef}
                  className="rs-view rs-view-inner"
                  dangerouslySetInnerHTML={{ __html: blocksFlowHtml }}
                />
              ) : (
                <div
                  ref={viewRef}
                  className="rs-view rs-view-inner"
                  dangerouslySetInnerHTML={{ __html: fullHtml }}
                />
              )}
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
              dangerouslySetInnerHTML={{ __html: usingBlocks ? blocksFlowHtml : fullHtml }}
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
