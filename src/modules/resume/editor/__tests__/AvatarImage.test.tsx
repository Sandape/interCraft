/**
 * AvatarImage — pure render component for a branch avatar (spec 027 US9).
 *
 * Verifies:
 * - Returns null when avatarUrl is missing
 * - Renders <img> with the given url and shape class
 * - Exposes --avatar-size CSS variable matching size prop
 * - Marks data-avatar-position on the wrapper
 * - Clamps size into [50, 200]
 */
import { describe, expect, it } from 'vitest'
import { render } from '@testing-library/react'
import AvatarImage from '../AvatarImage'

describe('AvatarImage', () => {
  it('renders null when avatarUrl is missing', () => {
    const { container } = render(<AvatarImage avatarUrl={null} />)
    expect(container.firstChild).toBeNull()
  })

  it('renders null when avatarUrl is empty string', () => {
    const { container } = render(<AvatarImage avatarUrl="" />)
    expect(container.firstChild).toBeNull()
  })

  it('renders <img> with the provided url and default size', () => {
    const { getByRole } = render(<AvatarImage avatarUrl="/avatar.png" />)
    const img = getByRole('img') as HTMLImageElement
    expect(img).toHaveAttribute('src', '/avatar.png')
    expect(img).toHaveAttribute('alt', '头像')
    expect(img.className).toContain('rounded-full')
  })

  it('applies shape class for circle / rounded / square', () => {
    const cases = [
      { shape: 'circle' as const, expected: 'rounded-full' },
      { shape: 'rounded' as const, expected: 'rounded-lg' },
      { shape: 'square' as const, expected: 'rounded-none' },
    ]
    for (const { shape, expected } of cases) {
      const { getByRole, unmount } = render(
        <AvatarImage avatarUrl="/avatar.png" shape={shape} />,
      )
      expect(getByRole('img').className).toContain(expected)
      unmount()
    }
  })

  it('exposes data-avatar-position on the wrapper', () => {
    const { container } = render(
      <AvatarImage avatarUrl="/a.png" position="left" />,
    )
    const wrapper = container.firstElementChild!
    expect(wrapper.getAttribute('data-avatar-position')).toBe('left')
  })

  it('exposes --avatar-size CSS variable equal to size prop', () => {
    const { container } = render(
      <AvatarImage avatarUrl="/a.png" size={120} />,
    )
    const wrapper = container.firstElementChild as HTMLElement
    expect(wrapper.style.getPropertyValue('--avatar-size')).toBe('120px')
    expect(wrapper.style.width).toBe('120px')
    expect(wrapper.style.height).toBe('120px')
  })

  it('clamps size below the minimum to 50', () => {
    const { container } = render(
      <AvatarImage avatarUrl="/a.png" size={10} />,
    )
    const wrapper = container.firstElementChild as HTMLElement
    expect(wrapper.style.getPropertyValue('--avatar-size')).toBe('50px')
  })

  it('clamps size above the maximum to 200', () => {
    const { container } = render(
      <AvatarImage avatarUrl="/a.png" size={999} />,
    )
    const wrapper = container.firstElementChild as HTMLElement
    expect(wrapper.style.getPropertyValue('--avatar-size')).toBe('200px')
  })
})