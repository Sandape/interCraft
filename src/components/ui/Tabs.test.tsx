import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { Tabs } from './Tabs'

describe('Tabs responsive behavior', () => {
  it('keeps each tab on one line so narrow parents can scroll horizontally', () => {
    render(
      <Tabs
        value="all"
        onChange={vi.fn()}
        items={[
          { key: 'all', label: '全部职位' },
          { key: 'interview', label: '面试中' },
        ]}
      />,
    )

    expect(screen.getByRole('tablist')).toHaveClass('w-max')
    for (const tab of screen.getAllByRole('tab')) {
      expect(tab).toHaveClass('flex-none', 'whitespace-nowrap')
    }
  })
})
