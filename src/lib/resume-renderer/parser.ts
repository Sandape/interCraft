/**
 * Markdown parser assembly — configures a single markdown-it instance with
 * all 木及 plugins (heading-block, blank-line, color-token, containers,
 * emoji-based icons).
 *
 * Ported from 木及简历 (D:\Project\react-resume-site\src\utils\helper.ts).
 */
import MarkdownIt from 'markdown-it'
import { full as emoji } from 'markdown-it-emoji'

import headingBlockPlugin from './markdown-it-plugins/heading-block'
import blankLinePlugin from './markdown-it-plugins/blank-line'
import containersPlugin from './markdown-it-plugins/containers'
import svgMap from './icons/svg-map'

/** Build the shortcut map: each icon name → `icon:<name>`. */
function buildIconShortcuts(): Record<string, string> {
  return Object.keys(svgMap).reduce<Record<string, string>>((obj, name) => {
    obj[name] = `icon:${name}`
    return obj
  }, {})
}

/**
 * Resume markdown parser — configured with:
 * - html: true (allow inline HTML, sanitization happens upstream)
 * - breaks: true (newlines → <br>)
 * - linkify: true (auto-link URLs)
 * - GFM features via default rules (tables, task lists, strikethrough)
 *
 * Plus 4 木及 plugins:
 * - emoji with svgMap defs + icon:<name> shortcuts
 * - heading-block wrapping
 * - containers (::: left/right/header/title)
 * - blank-line preservation
 */
export const markdownParserResume: MarkdownIt = new MarkdownIt({
  html: true,
  breaks: true,
  linkify: true,
})

markdownParserResume
  .use(emoji, {
    defs: svgMap,
    shortcuts: buildIconShortcuts(),
  })
  .use(headingBlockPlugin)
  .use(containersPlugin)
  .use(blankLinePlugin)

/** Article parser (no plugins) — for rendering tutorial / changelog modals. */
export const markdownParserArticle: MarkdownIt = new MarkdownIt({
  html: true,
})

/** Render Markdown to HTML string using the resume parser. */
export function renderToHtml(markdown: string): string {
  return markdownParserResume.render(markdown)
}
