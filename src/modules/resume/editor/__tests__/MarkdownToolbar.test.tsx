/** 027 US6 T080 — MarkdownToolbar button behavior. */
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import MarkdownToolbar from '../MarkdownToolbar'

function makeMockEditor() {
  const calls: { range: unknown; text: string }[] = []
  let selection = { startLineNumber: 1, startColumn: 1, endLineNumber: 1, endColumn: 1 }
  return {
    calls,
    editor: {
      getSelection: () => selection,
      setSelection: (s: typeof selection) => {
        selection = s
      },
      getModel: () => ({
        getValueInRange: () => 'hello',
      }),
      executeEdits: (_src: string, edits: { range: unknown; text: string }[]) => {
        calls.push(...edits)
      },
      focus: vi.fn(),
    } as unknown as Parameters<typeof MarkdownToolbar>[0]['editor'],
  }
}

describe('MarkdownToolbar', () => {
  it('renders all format buttons (bold/italic/H1/H2/H3/list/link/icon)', () => {
    render(<MarkdownToolbar editor={null} />)
    expect(screen.getByTitle('加粗 (Ctrl+B)')).toBeInTheDocument()
    expect(screen.getByTitle('斜体 (Ctrl+I)')).toBeInTheDocument()
    expect(screen.getByTitle('标题 1')).toBeInTheDocument()
    expect(screen.getByTitle('标题 2')).toBeInTheDocument()
    expect(screen.getByTitle('标题 3')).toBeInTheDocument()
    expect(screen.getByTitle('无序列表')).toBeInTheDocument()
    expect(screen.getByTitle('链接')).toBeInTheDocument()
    expect(screen.getByTitle('插入图标')).toBeInTheDocument()
  })

  it('disables buttons when editor is null', () => {
    render(<MarkdownToolbar editor={null} />)
    expect(screen.getByTitle('加粗 (Ctrl+B)')).toBeDisabled()
  })

  it('bold button wraps selection in **', () => {
    const { calls, editor } = makeMockEditor()
    render(<MarkdownToolbar editor={editor} />)
    fireEvent.click(screen.getByTitle('加粗 (Ctrl+B)'))
    expect(calls.length).toBe(1)
    expect(calls[0].text).toBe('**hello**')
  })

  it('italic button wraps selection in *', () => {
    const { calls, editor } = makeMockEditor()
    render(<MarkdownToolbar editor={editor} />)
    fireEvent.click(screen.getByTitle('斜体 (Ctrl+I)'))
    expect(calls.length).toBe(1)
    expect(calls[0].text).toBe('*hello*')
  })

  it('H1 button inserts `# ` at line start', () => {
    const { calls, editor } = makeMockEditor()
    render(<MarkdownToolbar editor={editor} />)
    fireEvent.click(screen.getByTitle('标题 1'))
    expect(calls.length).toBe(1)
    expect(calls[0].text).toBe('# ')
  })

  it('unordered-list button inserts `- `', () => {
    const { calls, editor } = makeMockEditor()
    render(<MarkdownToolbar editor={editor} />)
    fireEvent.click(screen.getByTitle('无序列表'))
    expect(calls[0].text).toBe('- ')
  })

  it('link button wraps selection as [text](url)', () => {
    const { calls, editor } = makeMockEditor()
    render(<MarkdownToolbar editor={editor} />)
    fireEvent.click(screen.getByTitle('链接'))
    expect(calls[0].text).toBe('[hello](url)')
  })

  it('icon button triggers onOpenIconPicker callback', () => {
    const onOpenIconPicker = vi.fn()
    const { editor } = makeMockEditor()
    render(<MarkdownToolbar editor={editor} onOpenIconPicker={onOpenIconPicker} />)
    fireEvent.click(screen.getByTitle('插入图标'))
    expect(onOpenIconPicker).toHaveBeenCalledTimes(1)
  })
})
