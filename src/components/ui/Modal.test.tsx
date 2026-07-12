import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { Modal } from './Modal'

describe('Modal focus behavior', () => {
  it('moves focus inside, traps Tab, and restores the opener on close', async () => {
    const onClose = vi.fn()
    const { rerender } = render(
      <>
        <button type="button">打开弹窗</button>
        <Modal open={false} onClose={onClose} title="测试弹窗">
          <button type="button">第一个操作</button>
          <button type="button">最后一个操作</button>
        </Modal>
      </>,
    )
    const opener = screen.getByRole('button', { name: '打开弹窗' })
    opener.focus()

    rerender(
      <>
        <button type="button">打开弹窗</button>
        <Modal open onClose={onClose} title="测试弹窗">
          <button type="button">第一个操作</button>
          <button type="button">最后一个操作</button>
        </Modal>
      </>,
    )

    await waitFor(() => expect(screen.getByRole('button', { name: '关闭' })).toHaveFocus())
    const last = screen.getByRole('button', { name: '最后一个操作' })
    last.focus()
    fireEvent.keyDown(document, { key: 'Tab' })
    expect(screen.getByRole('button', { name: '关闭' })).toHaveFocus()

    fireEvent.keyDown(window, { key: 'Escape' })
    expect(onClose).toHaveBeenCalledTimes(1)
    rerender(
      <>
        <button type="button">打开弹窗</button>
        <Modal open={false} onClose={onClose} title="测试弹窗"><span>内容</span></Modal>
      </>,
    )
    expect(screen.getByRole('button', { name: '打开弹窗' })).toHaveFocus()
  })
})
