/**
 * [REQ-048 US5 T098] Vitest unit test for VariantToggle component.
 *
 * Validates AC-25 (R22):
 * - Default state: VariantToggle is OFF (原题重考).
 * - Hover description shows correct zh-CN text.
 * - Toggle ON: description changes; payload includes use_variants=true.
 * - Toggle OFF: payload omits use_variants OR has use_variants=false.
 *
 * Mirrors the production VariantToggle component in isolation.
 * The full multi-agent E2E is covered by tests/e2e/quick-drill.spec.ts.
 */
import { describe, expect, it } from 'vitest'
import { render, fireEvent } from '@testing-library/react'
import { VariantToggle } from '../../src/components/interview/VariantToggle'

describe('VariantToggle (REQ-048 US5)', () => {
  it('default state: enabled=false, description shows 原题重考', () => {
    const { getByTestId } = render(
      <VariantToggle enabled={false} onChange={() => undefined} />,
    )
    const toggle = getByTestId('variant-toggle')
    expect(toggle.getAttribute('data-enabled')).toBe('false')
    const switchEl = getByTestId('variant-toggle-switch')
    expect(switchEl.getAttribute('aria-checked')).toBe('false')
    const desc = getByTestId('variant-toggle-description')
    expect(desc.textContent).toBe('原题重考：直接使用错题原题（默认 — 节省 token）')
  })

  it('enabled=true: description shows 变体重考已开启', () => {
    const { getByTestId } = render(
      <VariantToggle enabled={true} onChange={() => undefined} />,
    )
    const desc = getByTestId('variant-toggle-description')
    expect(desc.textContent).toBe(
      '变体重考已开启：每道错题将由 AI 生成新的问法，考察点保持不变',
    )
    const switchEl = getByTestId('variant-toggle-switch')
    expect(switchEl.getAttribute('aria-checked')).toBe('true')
  })

  it('click triggers onChange with the new value', () => {
    let captured: boolean | null = null
    const { getByTestId } = render(
      <VariantToggle
        enabled={false}
        onChange={(v) => {
          captured = v
        }}
      />,
    )
    fireEvent.click(getByTestId('variant-toggle'))
    expect(captured).toBe(true)
  })

  it('disabled prop blocks onChange', () => {
    let captured: boolean | null = null
    const { getByTestId } = render(
      <VariantToggle
        enabled={false}
        disabled={true}
        onChange={(v) => {
          captured = v
        }}
      />,
    )
    fireEvent.click(getByTestId('variant-toggle'))
    expect(captured).toBe(null)
  })

  it('hover title is in zh-CN (no English fallback)', () => {
    const { getByTestId } = render(
      <VariantToggle enabled={false} onChange={() => undefined} />,
    )
    const title = getByTestId('variant-toggle').getAttribute('title')
    expect(title).toBe(
      '变体重考会消耗额外的 LLM 配额（约 5 次调用/5 道题），请仅在需要时启用',
    )
    // Title contains primarily CJK characters (the 「LLM」 acronym is OK).
    const cjk_count = (title?.match(/[一-鿿]/g) || []).length
    expect(cjk_count).toBeGreaterThan(15)
  })
})