import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import DemoWorkspace from '../DemoWorkspace'

describe('DemoWorkspace', () => {
  it('is clearly marked as sample data and read-only', () => {
    render(
      <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <DemoWorkspace />
      </MemoryRouter>,
    )

    expect(screen.getAllByText(/示例数据/i).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/只读模式/i).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/示例候选人/i).length).toBeGreaterThan(0)
    expect(screen.getByRole('link', { name: /创建自己的工作台/i })).toHaveAttribute(
      'href',
      '/register',
    )
    expect(screen.getAllByRole('button', { name: /生成岗位定制简历/i })).toEqual(
      expect.arrayContaining([expect.objectContaining({ disabled: true })]),
    )
  })
})
