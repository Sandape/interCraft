/** 027 US4 T080 / US6 FR-046 — IconPicker component tests. */
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import IconPicker from '../IconPicker'

describe('IconPicker', () => {
  it('renders nothing when open=false', () => {
    const onInsert = vi.fn()
    const onClose = vi.fn()
    const { container } = render(
      <IconPicker open={false} onClose={onClose} onInsert={onInsert} />,
    )
    expect(container.querySelector('[data-testid="icon-picker-grid"]')).toBeNull()
  })

  it('renders all 14 icons when open', () => {
    const onInsert = vi.fn()
    const onClose = vi.fn()
    render(<IconPicker open onClose={onClose} onInsert={onInsert} />)
    const grid = screen.getByTestId('icon-picker-grid')
    expect(grid).toBeInTheDocument()
    expect(screen.getByTestId('icon-picker-github')).toBeInTheDocument()
    expect(screen.getByTestId('icon-picker-email')).toBeInTheDocument()
    expect(screen.getByTestId('icon-picker-juejin')).toBeInTheDocument()
    expect(screen.getByTestId('icon-picker-zhihu')).toBeInTheDocument()
    // 14 icons total
    const buttons = grid.querySelectorAll('button')
    expect(buttons.length).toBe(14)
  })

  it('inserts icon:<name> syntax when an icon is clicked', () => {
    const onInsert = vi.fn()
    const onClose = vi.fn()
    render(<IconPicker open onClose={onClose} onInsert={onInsert} />)
    fireEvent.click(screen.getByTestId('icon-picker-github'))
    expect(onInsert).toHaveBeenCalledWith('icon:github ')
    expect(onClose).toHaveBeenCalled()
  })

  it('inserts correct syntax for each icon name', () => {
    const onInsert = vi.fn()
    const onClose = vi.fn()
    render(<IconPicker open onClose={onClose} onInsert={onInsert} />)
    for (const name of ['email', 'phone', 'blog', 'weixin']) {
      fireEvent.click(screen.getByTestId(`icon-picker-${name}`))
      expect(onInsert).toHaveBeenCalledWith(`icon:${name} `)
      onInsert.mockClear()
      onClose.mockClear()
    }
  })
})
