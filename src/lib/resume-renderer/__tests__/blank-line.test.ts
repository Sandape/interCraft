/**
 * T022 — blank-line plugin unit tests.
 *
 * Verifies that consecutive blank lines between paragraphs produce
 * `<span class="break-line"></span>` × N elements to preserve the user's
 * intentional vertical rhythm (markdown-it collapses them by default).
 */
import { describe, it, expect } from 'vitest'
import { renderToHtml } from '../parser'

describe('blank-line plugin', () => {
  it('produces 3 break-line spans for 3 consecutive blank lines', () => {
    // p1 followed by 3 blank lines, then p2
    // Lines: 'p1', '', '', '', 'p2' (3 empty lines between)
    const md = 'p1\n\n\n\np2'
    const html = renderToHtml(md)
    const count = (html.match(/<span class="break-line"><\/span>/g) || []).length
    expect(count).toBe(3)
  })

  it('produces 1 break-line span for a single blank line', () => {
    // p1 followed by 1 blank line, then p2
    // Lines: 'p1', '', 'p2' (1 empty line between)
    const md = 'p1\n\np2'
    const html = renderToHtml(md)
    const count = (html.match(/<span class="break-line"><\/span>/g) || []).length
    expect(count).toBe(1)
  })

  it('produces 0 break-line spans for adjacent paragraphs (no blank line)', () => {
    // Single newline between p1 and p2 -> markdown-it treats as same paragraph (breaks:true -> <br>)
    // No blank line means no break-line span
    const md = 'p1\np2'
    const html = renderToHtml(md)
    const count = (html.match(/<span class="break-line"><\/span>/g) || []).length
    expect(count).toBe(0)
  })
})
