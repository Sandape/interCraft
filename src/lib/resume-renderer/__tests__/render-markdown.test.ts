/**
 * T024 — renderMarkdown + sanitizeHtml unit tests.
 *
 * Verifies:
 * - renderMarkdown is a pure function (same input → same output)
 * - sanitizeHtml strips dangerous tags/attributes (XSS defense in depth)
 */
import { describe, it, expect } from 'vitest'
import { renderMarkdown, sanitizeHtml } from '../index'

describe('renderMarkdown — purity', () => {
  it('returns byte-identical output for the same input (call twice)', () => {
    const md = '# Title\n\n## Section\n\n- item 1\n- item 2\n\n**bold** and *italic*'
    const r1 = renderMarkdown(md, { accentColor: '#abc123' })
    const r2 = renderMarkdown(md, { accentColor: '#abc123' })
    expect(r1.html).toBe(r2.html)
  })

  it('returns byte-identical output for complex input (tables + html + color tokens)', () => {
    const md = [
      '# Resume',
      '',
      '<span style="color: #{color}">accent</span>',
      '',
      '| a | b |',
      '|---|---|',
      '| 1 | 2 |',
      '',
      '![alt](url)',
      '',
      '[link](https://example.com)',
    ].join('\n')
    const r1 = renderMarkdown(md, { accentColor: '#2563eb' })
    const r2 = renderMarkdown(md, { accentColor: '#2563eb' })
    expect(r1.html).toBe(r2.html)
  })

  it('includes html field in result', () => {
    const r = renderMarkdown('# Hello', {})
    expect(typeof r.html).toBe('string')
    expect(r.html.length).toBeGreaterThan(0)
  })
})

describe('sanitizeHtml — XSS defense', () => {
  it('strips <script> tags', () => {
    const html = '<p>safe</p><script>alert(1)</script><p>after</p>'
    const cleaned = sanitizeHtml(html)
    expect(cleaned).not.toContain('<script')
    expect(cleaned).not.toContain('alert(1)')
    expect(cleaned).toContain('<p>safe</p>')
    expect(cleaned).toContain('<p>after</p>')
  })

  it('strips <iframe> tags', () => {
    const html = '<iframe src="evil.com"></iframe><p>ok</p>'
    const cleaned = sanitizeHtml(html)
    expect(cleaned.toLowerCase()).not.toContain('<iframe')
    expect(cleaned).toContain('<p>ok</p>')
  })

  it('strips <object> tags', () => {
    const html = '<object data="evil.swf"></object><p>ok</p>'
    const cleaned = sanitizeHtml(html)
    expect(cleaned.toLowerCase()).not.toContain('<object')
  })

  it('strips <embed> tags', () => {
    const html = '<embed src="evil.swf"><p>ok</p>'
    const cleaned = sanitizeHtml(html)
    expect(cleaned.toLowerCase()).not.toContain('<embed')
  })

  it('strips on* event attributes (double-quoted)', () => {
    const html = '<p onclick="alert(1)">text</p>'
    const cleaned = sanitizeHtml(html)
    expect(cleaned.toLowerCase()).not.toContain('onclick')
  })

  it('strips on* event attributes (single-quoted)', () => {
    const html = "<p onclick='alert(1)'>text</p>"
    const cleaned = sanitizeHtml(html)
    expect(cleaned.toLowerCase()).not.toContain('onclick')
  })

  it('strips on* event attributes (unquoted)', () => {
    const html = '<p onclick=alert(1)>text</p>'
    const cleaned = sanitizeHtml(html)
    expect(cleaned.toLowerCase()).not.toContain('onclick')
  })

  it('strips javascript: protocol URIs', () => {
    const html = '<a href="javascript:alert(1)">click</a>'
    const cleaned = sanitizeHtml(html)
    expect(cleaned.toLowerCase()).not.toContain('javascript:')
  })
})
