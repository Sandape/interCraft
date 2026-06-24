/**
 * `::: left / ::: right / ::: header / ::: title` container plugin.
 * Ported from 木及简历 (D:\Project\react-resume-site\src\utils\helper.ts:24-45).
 *
 * Uses markdown-it-container to emit two-column layout divs:
 *   ::: left ... ::: right ... → <div class="lr-container"><div class="left">...<div class="right">...</div></div>
 *   ::: header ... → <div class="header-block">...</div>
 *   ::: title ... → <div class="title-block">...</div>
 */
import MarkdownIt from 'markdown-it'
import container from 'markdown-it-container'

export default function containersPlugin(md: MarkdownIt): void {
  // markdown-it-container's type signature uses a narrower MarkdownIt than
  // @types/markdown-it; cast to bypass the mismatch (runtime works fine).
  const mdAny = md as unknown as { use: (plugin: unknown, ...args: unknown[]) => void }

  mdAny.use(container, 'header', {
    render: (tokens: { nesting: number }[], idx: number) => {
      if (tokens[idx].nesting === 1) {
        return '<div class="header-block">'
      }
      return '</div>'
    },
  })

  mdAny.use(container, 'left', {
    render: (tokens: { nesting: number }[], idx: number) => {
      if (tokens[idx].nesting === 1) {
        return '<div class="lr-container"><div class="left">'
      }
      return '</div>'
    },
  })

  mdAny.use(container, 'right', {
    render: (tokens: { nesting: number }[], idx: number) => {
      if (tokens[idx].nesting === 1) {
        return '<div class="right">'
      }
      return '</div></div>'
    },
  })

  mdAny.use(container, 'title', {
    render: (tokens: { nesting: number }[], idx: number) => {
      if (tokens[idx].nesting === 1) {
        return '<div class="title-block">'
      }
      return '</div>'
    },
  })
}
