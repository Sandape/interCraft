/**
 * T023 — color-token plugin unit tests.
 *
 * Verifies that `#{color}` in markdown is replaced with the accentColor
 * hex value after rendering (post-render regex replace).
 */
import { describe, it, expect } from 'vitest'
import { renderMarkdown } from '../index'

describe('color-token plugin', () => {
  it('replaces #{color} with the provided accentColor', () => {
    const md = '<span style="color: #{color}">highlighted</span>'
    const { html } = renderMarkdown(md, { accentColor: '#2563eb' })
    expect(html).toContain('color: #2563eb')
    expect(html).not.toContain('#{color}')
  })

  it('replaces multiple #{color} occurrences', () => {
    const md = '<span style="color: #{color}">a</span>\n<span style="color: #{color}">b</span>'
    const { html } = renderMarkdown(md, { accentColor: '#ff0000' })
    const count = (html.match(/color: #ff0000/g) || []).length
    expect(count).toBe(2)
  })

  it('falls back to default accent color when accentColor not provided', () => {
    const md = '<span style="color: #{color}">x</span>'
    const { html } = renderMarkdown(md)
    // Default accent color is '#39393a' (see index.ts DEFAULT_ACCENT_COLOR)
    expect(html).toContain('color: #39393a')
    expect(html).not.toContain('#{color}')
  })
})
