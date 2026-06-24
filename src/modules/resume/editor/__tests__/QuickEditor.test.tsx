/**
 * US8 — QuickEditor bidirectional locator wiring tests.
 *
 * Verifies the editor-side plumbing for the bidirectional locator:
 * - Clicking a block header fires onPreviewLocate with the block id (forward).
 * - Setting `highlighted` applies the rs-editor-block-flash class (reverse).
 * - Collapse-toggle and action buttons stop propagation so they don't
 *   accidentally trigger the locate path.
 */
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { QuickEditor } from '../QuickEditor'
import type { ResumeBlock } from '../../api/types'

const fakeBlocks: ResumeBlock[] = [
  {
    id: 'b1',
    branch_id: '',
    type: 'experience',
    title: '字节跳动',
    content_md: '前端开发',
    content_html: null,
    meta: null,
    order_index: '0',
    collapsed: false,
    created_at: '',
    updated_at: '',
  },
  {
    id: 'b2',
    branch_id: '',
    type: 'skill',
    title: null,
    content_md: 'TypeScript / React',
    content_html: null,
    meta: null,
    order_index: '1',
    collapsed: false,
    created_at: '',
    updated_at: '',
  },
]

describe('QuickEditor — US8 forward-locate (block → preview)', () => {
  it('calls onPreviewLocate(b1) when the block-1 header is clicked', () => {
    const onPreviewLocate = vi.fn()
    render(
      <QuickEditor
        blocks={fakeBlocks}
        collapsedBlockIds={new Set()}
        onToggleCollapse={() => {}}
        onAutoSave={() => {}}
        onDelete={() => {}}
        onMoveUp={() => {}}
        onMoveDown={() => {}}
        onPatchMeta={() => {}}
        onPreviewLocate={onPreviewLocate}
      />,
    )
    fireEvent.click(screen.getByTestId('block-header-b1'))
    expect(onPreviewLocate).toHaveBeenCalledWith('b1')
  })

  it('does not call onPreviewLocate when the collapse-toggle button is clicked', () => {
    const onPreviewLocate = vi.fn()
    const onToggleCollapse = vi.fn()
    render(
      <QuickEditor
        blocks={fakeBlocks}
        collapsedBlockIds={new Set()}
        onToggleCollapse={onToggleCollapse}
        onAutoSave={() => {}}
        onDelete={() => {}}
        onMoveUp={() => {}}
        onMoveDown={() => {}}
        onPatchMeta={() => {}}
        onPreviewLocate={onPreviewLocate}
      />,
    )
    // The collapse button has aria-label="折叠" when expanded.
    fireEvent.click(screen.getAllByLabelText('折叠')[0])
    expect(onToggleCollapse).toHaveBeenCalled()
    expect(onPreviewLocate).not.toHaveBeenCalled()
  })

  it('does not call onPreviewLocate when the delete button is clicked', () => {
    const onPreviewLocate = vi.fn()
    const onDelete = vi.fn()
    render(
      <QuickEditor
        blocks={fakeBlocks}
        collapsedBlockIds={new Set()}
        onToggleCollapse={() => {}}
        onAutoSave={() => {}}
        onDelete={onDelete}
        onMoveUp={() => {}}
        onMoveDown={() => {}}
        onPatchMeta={() => {}}
        onPreviewLocate={onPreviewLocate}
      />,
    )
    fireEvent.click(screen.getAllByLabelText('删除')[0])
    expect(onDelete).toHaveBeenCalledWith('b1')
    expect(onPreviewLocate).not.toHaveBeenCalled()
  })

  it('keyboard Enter on the header triggers onPreviewLocate', () => {
    const onPreviewLocate = vi.fn()
    render(
      <QuickEditor
        blocks={fakeBlocks}
        collapsedBlockIds={new Set()}
        onToggleCollapse={() => {}}
        onAutoSave={() => {}}
        onDelete={() => {}}
        onMoveUp={() => {}}
        onMoveDown={() => {}}
        onPatchMeta={() => {}}
        onPreviewLocate={onPreviewLocate}
      />,
    )
    fireEvent.keyDown(screen.getByTestId('block-header-b1'), { key: 'Enter' })
    expect(onPreviewLocate).toHaveBeenCalledWith('b1')
  })
})

describe('QuickEditor — US8 reverse-locate (preview → editor)', () => {
  it('applies rs-editor-block-flash class to the highlighted block', () => {
    render(
      <QuickEditor
        blocks={fakeBlocks}
        collapsedBlockIds={new Set()}
        onToggleCollapse={() => {}}
        onAutoSave={() => {}}
        onDelete={() => {}}
        onMoveUp={() => {}}
        onMoveDown={() => {}}
        onPatchMeta={() => {}}
        highlightedBlockId="b2"
      />,
    )
    const b2 = screen.getByTestId('block-b2')
    expect(b2.className).toContain('rs-editor-block-flash')
    const b1 = screen.getByTestId('block-b1')
    expect(b1.className).not.toContain('rs-editor-block-flash')
  })

  it('does not apply flash class when highlightedBlockId is null', () => {
    render(
      <QuickEditor
        blocks={fakeBlocks}
        collapsedBlockIds={new Set()}
        onToggleCollapse={() => {}}
        onAutoSave={() => {}}
        onDelete={() => {}}
        onMoveUp={() => {}}
        onMoveDown={() => {}}
        onPatchMeta={() => {}}
      />,
    )
    expect(screen.getByTestId('block-b1').className).not.toContain('rs-editor-block-flash')
    expect(screen.getByTestId('block-b2').className).not.toContain('rs-editor-block-flash')
  })
})