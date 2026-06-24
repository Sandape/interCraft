/**
 * T021 — heading-block plugin unit tests.
 *
 * Verifies that `#`, `##`, `###` headings are wrapped in
 * `<div class="h<N>_block block">` containers, and that nested headings
 * close parent blocks properly.
 */
import { describe, it, expect } from 'vitest'
import { renderToHtml } from '../parser'

describe('heading-block plugin', () => {
  it('wraps H1 in <div class="h1_block block">', () => {
    const html = renderToHtml('# Title')
    expect(html).toContain('<div class="h1_block block">')
    expect(html).toContain('<h1>Title</h1>')
    expect(html).toContain('</div>')
  })

  it('wraps H2 in <div class="h2_block block">', () => {
    const html = renderToHtml('## Section')
    expect(html).toContain('<div class="h2_block block">')
    expect(html).toContain('<h2>Section</h2>')
    expect(html).toContain('</div>')
  })

  it('wraps H3 in <div class="h3_block block">', () => {
    const html = renderToHtml('### Subsection')
    expect(html).toContain('<div class="h3_block block">')
    expect(html).toContain('<h3>Subsection</h3>')
  })

  it('closes H1 block before opening H2 inside it (nested)', () => {
    // # H1\n## H2 should close the H1 block after the H2 block,
    // so the structure is: <div h1_block><h1>H1</h1><div h2_block><h2>H2</h2></div></div>
    const html = renderToHtml('# H1\n## H2')
    // Both block wrappers present
    expect(html).toContain('<div class="h1_block block">')
    expect(html).toContain('<div class="h2_block block">')
    // H2 block is nested inside H1 block (h2 opens after h1, h2 closes before h1)
    const h1Open = html.indexOf('<div class="h1_block block">')
    const h2Open = html.indexOf('<div class="h2_block block">')
    const h2Close = html.indexOf('</div>', h2Open)
    const h1Close = html.indexOf('</div>', h2Close + 6)
    expect(h1Open).toBeGreaterThan(-1)
    expect(h2Open).toBeGreaterThan(h1Open)
    expect(h2Close).toBeGreaterThan(h2Open)
    expect(h1Close).toBeGreaterThan(h2Close)
  })
})
