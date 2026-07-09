/**
 * Heading-block structural wrapping plugin.
 * Ported from 木及简历 (D:\Project\react-resume-site\src\utils\markdown-it-h-container.ts).
 *
 * Every `#`, `##`, `###`, `####`, `#####` heading is wrapped in a
 * `<div class="h<N>_block block">` container using a stack-based open/close
 * algorithm. This lets theme CSS target the entire section under a heading
 * (e.g. colored banners, padding) rather than just the heading text.
 */
import type MarkdownIt from 'markdown-it'

export default function headingBlockPlugin(md: MarkdownIt): void {
  const headingMap: string[] = []

  md.block.ruler.after(
    'fence',
    'heading_block',
    function (state, line: number, _maxLine: number): boolean {
      if ((state.parentType as string) === 'container') {
        return false
      }

      const rg = /^(#+)\s(.*)/
      const start = state.bMarks[line] + state.tShift[line]
      const end = state.eMarks[line]
      const text = state.src.substring(start, end)
      const match = text.match(rg)
      if (match && match.length) {
        const headingLevel = match[1] // e.g. "##"
        const headingLevelLength = headingLevel.length
        const index = headingMap.lastIndexOf(headingLevel)
        if (index === -1) {
          state.push(`container_div_${headingLevelLength}_open`, 'div', 1)
          headingMap.push(headingLevel)
        } else {
          const diffIndex = headingMap.length - 1 - index
          for (let i = 0; i < diffIndex; i++) {
            state.push('container_div_heading__close', 'div', -1)
            headingMap.pop()
          }
          state.push('container_div_heading__close', 'div', -1)
          state.push(`container_div_${headingLevelLength}_open`, 'div', 1)
        }
      }
      return false
    },
  )

  md.core.ruler.after('inline', 'heading_block_close_tail', (state) => {
    const length = headingMap.length
    for (let i = 0; i < length; i++) {
      const token = new state.Token('container_div_heading__close', 'div', -1)
      state.tokens.push(token)
      headingMap.pop()
    }
    return false
  })

  md.renderer.rules['container_div_heading__close'] = function (tokens, idx, options, _env, self) {
    return self.renderToken(tokens, idx, options)
  }

  new Array(5).fill(0).forEach((_, index) => {
    md.renderer.rules[`container_div_${index + 1}_open`] = function (tokens, idx, options, _env, self) {
      if (tokens[idx].nesting === 1) {
        tokens[idx].attrJoin('class', `h${index + 1}_block`)
        tokens[idx].attrJoin('class', 'block')
      }
      return self.renderToken(tokens, idx, options)
    }
  })
}
