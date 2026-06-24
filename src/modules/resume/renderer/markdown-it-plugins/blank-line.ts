/**
 * Blank-line preservation plugin.
 * Ported from 木及简历 (D:\Project\react-resume-site\src\utils\markdown-it-n.ts).
 *
 * Uses the markdown-it token `map` (line-number ranges) to count blank lines
 * between paragraphs and inserts `<span class="break-line">` × N. markdown-it
 * collapses multiple blank lines by default; this restores the user's
 * intentional vertical rhythm.
 */
import type MarkdownIt from 'markdown-it'

export default function blankLinePlugin(md: MarkdownIt): void {
  const defaultParagraphRenderer =
    md.renderer.rules.paragraph_open ||
    ((tokens, idx, options, _env, self) => self.renderToken(tokens, idx, options))

  md.renderer.rules.paragraph_open = function (tokens, idx, options, env, self) {
    let result = ''
    if (idx > 1) {
      const inline = tokens[idx - 2]
      const paragraph = tokens[idx]
      if (
        inline.type === 'inline' &&
        inline.map &&
        inline.map[1] &&
        paragraph.map &&
        paragraph.map[0]
      ) {
        const diff = paragraph.map[0] - inline.map[1]
        if (diff > 0) {
          result = '<span class="break-line"></span>'.repeat(diff)
        }
      }
    }
    return result + defaultParagraphRenderer(tokens, idx, options, env, self)
  }
}
