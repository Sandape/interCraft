/**
 * Smart pagination library — wraps `rs-md-html-parser` to produce A4 page
 * breaks + page count.
 *
 * Algorithm: walks the rendered DOM, computes A4 page boundaries, inserts
 * `.rs-line-split` separator elements at page break points, sets
 * `data-pages="<n>"` on the root.
 *
 * Ported from 木及简历 (rs-md-html-parser usage in Preview/index.tsx).
 */
import htmlParser from 'rs-md-html-parser'

export interface PaginationResult {
  pageCount: number
  separators: HTMLElement[]
}

const A4_HEIGHT_PX = 1122 // A4 at 96 DPI ≈ 1122px (rounded from 297mm)
const SINGLE_PAGE_HEIGHT = A4_HEIGHT_PX

/**
 * Apply pagination to a rendered DOM node.
 *
 * @param domNode The `.rs-view-inner` (or equivalent) root element containing
 *   the rendered resume HTML.
 * @returns pageCount + inserted separators.
 *
 * @note Call this AFTER the HTML has been set via dangerouslySetInnerHTML and
 *   the browser has laid out the DOM (use requestAnimationFrame or useEffect
 *   after render). Debounce on frequent content changes (use `debounce`).
 */
export function paginateDom(domNode: HTMLElement): PaginationResult {
  if (!domNode) return { pageCount: 1, separators: [] }

  // Remove existing separators before re-paginating.
  const existing = domNode.querySelectorAll('.rs-line-split')
  existing.forEach((el) => el.remove())

  // rs-md-html-parser's htmlParser walks the DOM and inserts separators.
  // It sets `data-pages` attribute on the root.
  try {
    htmlParser(domNode)
  } catch {
    // htmlParser may fail on edge cases (empty DOM, very short content).
    // Fall back to single page.
    return { pageCount: 1, separators: [] }
  }

  const pageCount = parseInt(domNode.dataset.pages ?? '1', 10) || 1
  const separators = Array.from(domNode.querySelectorAll<HTMLElement>('.rs-line-split'))

  return { pageCount, separators }
}

/**
 * Apply single-page mode (clip overflow to A4 height).
 * In single-page mode, only the first page is visible.
 */
export function applySinglePageMode(domNode: HTMLElement, enabled: boolean): void {
  if (!domNode) return
  if (enabled) {
    domNode.style.overflow = 'hidden'
    domNode.style.height = `${SINGLE_PAGE_HEIGHT}px`
  } else {
    domNode.style.overflow = 'visible'
    domNode.style.height = 'auto'
  }
}

export { A4_HEIGHT_PX } from './constants'
export { attachWindowScaleListener, applyWindowScale } from './window-scale'
export { paginateMarkdownHtml } from './markdown-pages'
export type {
  PageBreakDecision,
  PageBreakReason,
  PaginatedResumePreview,
  ResumePreviewPage,
} from './types'
