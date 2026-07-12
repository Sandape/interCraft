import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import PublicHome from '../PublicHome'

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('PublicHome', () => {
  it('leads with the job-search workspace promise and both conversion paths', () => {
    render(
      <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <PublicHome />
      </MemoryRouter>,
    )

    expect(
      screen.getByRole('heading', { name: /把一份根简历，变成每个目标岗位的完整准备/i }),
    ).toBeInTheDocument()
    expect(screen.getAllByRole('link', { name: /免费开始/i })[0]).toHaveAttribute(
      'href',
      '/register',
    )
    expect(screen.getAllByRole('link', { name: /查看只读示例工作台/i })[0]).toHaveAttribute(
      'href',
      '/demo',
    )
  })

  it('shows one continuous six-stage loop and anonymized product proof', () => {
    render(
      <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <PublicHome />
      </MemoryRouter>,
    )

    for (const label of ['根简历', '目标岗位', '派生简历', '模拟面试', '错题本', '能力画像']) {
      expect(screen.getAllByText(label).length).toBeGreaterThan(0)
    }
    expect(screen.getAllByText(/示例候选人/i).length).toBeGreaterThan(0)
    expect(document.body).not.toHaveTextContent(/qingfeng@|13800000000/i)
  })

  it('organizes the desktop story as five animated, directly navigable slides', async () => {
    render(
      <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <PublicHome />
      </MemoryRouter>,
    )

    const slides = document.querySelectorAll('[data-home-slide]')
    expect(slides).toHaveLength(5)

    const chapterNavigation = screen.getByRole('navigation', { name: '首页章节' })
    const chapterLinks = chapterNavigation.querySelectorAll('a')
    expect(chapterLinks).toHaveLength(5)
    expect(chapterLinks[0]).toHaveAttribute('aria-current', 'step')
    expect(Array.from(chapterLinks, (link) => link.getAttribute('href'))).toEqual([
      '#hero',
      '#workflow',
      '#product-proof',
      '#retention',
      '#scenarios',
    ])

    await waitFor(() => {
      expect(document.querySelectorAll('[data-home-slide].is-visible')).toHaveLength(5)
    })
  })

  it('updates the fixed header from the presentation scroll container', async () => {
    render(
      <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <PublicHome />
      </MemoryRouter>,
    )

    const deck = document.querySelector<HTMLElement>('.public-product')
    expect(deck).not.toBeNull()
    Object.defineProperty(deck, 'scrollTop', { configurable: true, value: 24 })
    fireEvent.scroll(deck!)

    await waitFor(() => {
      expect(document.querySelector('.public-header')).toHaveClass('bg-surface/95')
    })
  })

  it('advances exactly one slide for a desktop wheel gesture', () => {
    vi.stubGlobal('matchMedia', (query: string) => ({
      matches: query.includes('min-width'),
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }))

    render(
      <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <PublicHome />
      </MemoryRouter>,
    )

    const deck = document.querySelector<HTMLElement>('.public-product')!
    Object.defineProperty(deck, 'clientHeight', { configurable: true, value: 900 })
    Object.defineProperty(deck, 'scrollTop', { configurable: true, value: 0, writable: true })
    const scrollTo = vi.fn()
    deck.scrollTo = scrollTo

    fireEvent.wheel(deck, { deltaX: 0, deltaY: 100 })

    expect(scrollTo).toHaveBeenCalledWith({ top: 900, behavior: 'smooth' })
  })
})
