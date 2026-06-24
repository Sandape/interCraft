/**
 * Resume render engine — unified Markdown→HTML pipeline shared by preview
 * and PDF export to eliminate rendering drift (spec 027 US1).
 *
 * Pipeline:
 *   Markdown → markdown-it (+ 木及 plugins) → colorPlugin (#{color}) → HTML string
 *
 * Pagination (rs-md-html-parser) is applied separately by `resume-pagination`
 * because it needs a live DOM node (browser only).
 *
 * Contract: specs/027-resume-center-muji-alignment/contracts/render-engine.md
 */
import { renderToHtml } from './parser'
import { colorPlugin } from './markdown-it-plugins/color-token'

export interface RenderOptions {
  /** Theme accent color HEX (e.g. '#39393a'). Replaces `#{color}` tokens. Default '#39393a'. */
  accentColor?: string
}

export interface RenderResult {
  /** Rendered HTML string (body content, no <html>/<head>/<body> wrapper). */
  html: string
}

export interface BlockRenderInput {
  /** Stable block id from backend (`ResumeBlock.id`). */
  id: string
  /** Markdown source for this block. */
  content_md: string
}

export interface RenderBlocksResult {
  /** Concatenated HTML wrapped in `<section data-block-id="…">` per block. */
  html: string
  /** Ids in the order they were rendered (used by callers to build mappings). */
  blockIds: string[]
}

const DEFAULT_ACCENT_COLOR = '#39393a'

/**
 * Render Markdown to HTML using the unified engine.
 *
 * Pure function: same input → same output (byte-identical). No randomness,
 * no global state mutation (except the markdown-it instance, which is stateless
 * per `render()` call).
 *
 * @param markdown Markdown source string
 * @param opts Render options (accentColor for `#{color}` token replacement)
 * @returns RenderResult with HTML string
 */
export function renderMarkdown(markdown: string, opts: RenderOptions = {}): RenderResult {
  const accentColor = opts.accentColor ?? DEFAULT_ACCENT_COLOR
  const rawHtml = renderToHtml(markdown)
  const html = colorPlugin(rawHtml, { color: accentColor })
  return { html }
}

/** Sanitize HTML — filter dangerous tags/attributes (defense in depth). */
export function sanitizeHtml(html: string): string {
  return html
    .replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '')
    .replace(/<iframe\b[^<]*(?:(?!<\/iframe>)<[^<]*)*<\/iframe>/gi, '')
    .replace(/<object\b[^<]*(?:(?!<\/object>)<[^<]*)*<\/object>/gi, '')
    .replace(/<embed\b[^>]*>/gi, '')
    .replace(/\son\w+\s*=\s*"[^"]*"/gi, '')
    .replace(/\son\w+\s*=\s*'[^']*'/gi, '')
    .replace(/\son\w+\s*=\s*[^\s>]+/gi, '')
    .replace(/javascript:/gi, '')
}

/**
 * Render a list of blocks separately and wrap each in `<section data-block-id="…">`.
 *
 * Used by the live preview to expose block identity to the bidirectional
 * locator (US8). Each section has `data-block-id` so reverse-locate (preview
 * → block list) and forward-locate (block list → preview scroll + highlight)
 * both work without re-parsing markdown.
 */
export function renderBlocksToHtml(
  blocks: BlockRenderInput[],
  opts: RenderOptions = {},
): RenderBlocksResult {
  const accentColor = opts.accentColor ?? DEFAULT_ACCENT_COLOR
  const parts: string[] = []
  const blockIds: string[] = []
  for (const b of blocks) {
    const raw = renderToHtml(b.content_md)
    const styled = colorPlugin(raw, { color: accentColor })
    parts.push(
      `<section class="rs-block" data-block-id="${escapeAttr(b.id)}">${styled}</section>`,
    )
    blockIds.push(b.id)
  }
  return { html: parts.join('\n'), blockIds }
}

function escapeAttr(v: string): string {
  return v.replace(/[&"<>]/g, (c) =>
    c === '&' ? '&amp;' : c === '"' ? '&quot;' : c === '<' ? '&lt;' : '&gt;',
  )
}

export { default as svgMap, ICON_NAMES } from './icons/svg-map'
export type { IconName } from './icons/svg-map'
export { markdownParserResume, markdownParserArticle, renderToHtml } from './parser'
