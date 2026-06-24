/**
 * T020 — render engine parser unit tests.
 *
 * Verifies the markdown-it instance renders standard Markdown features
 * (headings, lists, bold, links, images, GFM tables, code blocks).
 *
 * The render engine library is pre-built (Phase 2). These tests verify the
 * contract before US1 wires it into ResumePreview + PDF export.
 */
import { describe, it, expect } from 'vitest'
import { renderToHtml } from '../parser'

describe('renderToHtml — standard Markdown', () => {
  it('renders H1 heading', () => {
    const html = renderToHtml('# Hello')
    expect(html).toContain('<h1>Hello</h1>')
  })

  it('renders unordered list', () => {
    const html = renderToHtml('- a\n- b')
    expect(html).toContain('<ul>')
    expect(html).toContain('<li>a</li>')
    expect(html).toContain('<li>b</li>')
    expect(html).toContain('</ul>')
  })

  it('renders bold text', () => {
    const html = renderToHtml('**bold**')
    expect(html).toContain('<strong>bold</strong>')
  })

  it('renders links', () => {
    const html = renderToHtml('[text](url)')
    expect(html).toContain('<a href="url">text</a>')
  })

  it('renders images', () => {
    const html = renderToHtml('![alt](url)')
    expect(html).toContain('<img src="url" alt="alt"')
  })

  it('renders GFM tables', () => {
    const html = renderToHtml('| a | b |\n|---|---|\n| 1 | 2 |')
    expect(html).toContain('<table>')
    expect(html).toContain('<th>a</th>')
    expect(html).toContain('<th>b</th>')
    expect(html).toContain('<td>1</td>')
    expect(html).toContain('<td>2</td>')
  })

  it('renders fenced code blocks', () => {
    const html = renderToHtml('```\ncode\n```')
    expect(html).toContain('<pre>')
    expect(html).toContain('<code>')
    expect(html).toContain('code')
  })
})
