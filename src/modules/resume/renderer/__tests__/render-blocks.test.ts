/**
 * T158 — renderBlocksToHtml tests (US8 bidirectional locator).
 *
 * Verifies:
 * - Wraps each block in `<section class="rs-block" data-block-id="…">`
 * - blockIds array preserves input order
 * - HTML-attribute escaping protects against `id="x"><script>` payloads
 * - Empty blocks render as empty sections (caller filters them out before passing in)
 */
import { describe, it, expect } from 'vitest'
import { renderBlocksToHtml } from '../index'

describe('renderBlocksToHtml — wrapper contract', () => {
  it('wraps each block in a section with class and data-block-id', () => {
    const { html, blockIds } = renderBlocksToHtml([
      { id: 'b1', content_md: '# A' },
      { id: 'b2', content_md: '## B' },
    ])
    expect(blockIds).toEqual(['b1', 'b2'])
    expect(html).toContain('class="rs-block"')
    expect(html).toContain('data-block-id="b1"')
    expect(html).toContain('data-block-id="b2"')
  })

  it('preserves block order in both html and blockIds', () => {
    const { html, blockIds } = renderBlocksToHtml([
      { id: 'a', content_md: 'one' },
      { id: 'b', content_md: 'two' },
      { id: 'c', content_md: 'three' },
    ])
    expect(blockIds).toEqual(['a', 'b', 'c'])
    const aIdx = html.indexOf('data-block-id="a"')
    const bIdx = html.indexOf('data-block-id="b"')
    const cIdx = html.indexOf('data-block-id="c"')
    expect(aIdx).toBeGreaterThanOrEqual(0)
    expect(bIdx).toBeGreaterThan(aIdx)
    expect(cIdx).toBeGreaterThan(bIdx)
  })

  it('escapes HTML-attribute-breaking chars in id', () => {
    // Attacker-controlled id (defensive): must not allow breaking out of the attribute.
    const { html } = renderBlocksToHtml([
      { id: '"><script>alert(1)</script>', content_md: 'safe' },
    ])
    expect(html).not.toContain('<script>alert(1)</script>')
    // The payload's quotes are escaped so the attribute stays well-formed.
    expect(html).toContain('&quot;')
  })

  it('returns empty html + empty blockIds for empty input', () => {
    const { html, blockIds } = renderBlocksToHtml([])
    expect(blockIds).toEqual([])
    expect(html).toBe('')
  })

  it('applies accent color via #{color} token replacement', () => {
    const { html } = renderBlocksToHtml(
      [{ id: 'b1', content_md: '<span style="color: #{color}">accent</span>' }],
      { accentColor: '#ff0000' },
    )
    expect(html).toContain('#ff0000')
    expect(html).not.toContain('#{color}')
  })

  it('renders markdown body inside each section', () => {
    const { html } = renderBlocksToHtml([
      { id: 'b1', content_md: '**bold** text' },
    ])
    expect(html).toMatch(/<section[^>]*data-block-id="b1"[^>]*>[\s\S]*<strong>bold<\/strong>[\s\S]*<\/section>/)
  })
})