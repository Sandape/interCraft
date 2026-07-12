import { act, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import Onboarding from '../Onboarding'

function renderOnboarding(initialEntry = '/onboarding') {
  return render(
    <MemoryRouter initialEntries={[initialEntry]} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <Routes>
        <Route path="/onboarding" element={<Onboarding />} />
        <Route path="/dashboard" element={<div>Dashboard destination</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('Onboarding', () => {
  beforeEach(() => window.localStorage.clear())

  it('validates the goal before moving forward and autosaves valid input', () => {
    renderOnboarding()

    fireEvent.click(screen.getByRole('button', { name: /下一步/i }))
    expect(screen.getByRole('alert')).toHaveTextContent(/选择求职阶段并填写目标方向/i)

    fireEvent.click(screen.getByRole('button', { name: '转行' }))
    fireEvent.change(screen.getByLabelText(/目标岗位或方向/i), {
      target: { value: '产品经理' },
    })
    fireEvent.click(screen.getByRole('button', { name: /下一步/i }))

    expect(screen.getByRole('heading', { name: /创建根简历草稿/i })).toBeInTheDocument()
    expect(window.localStorage.getItem('intercraft:onboarding:v1')).toContain('产品经理')
  })

  it('keeps skipped progress and exposes it as resumable', () => {
    renderOnboarding()

    fireEvent.click(screen.getByRole('button', { name: /暂时跳过/i }))

    expect(screen.getByText('Dashboard destination')).toBeInTheDocument()
    expect(window.localStorage.getItem('intercraft:onboarding:v1')).toContain('skipped')
  })

  it('announces when a saved draft is resumed', () => {
    window.localStorage.setItem(
      'intercraft:onboarding:v1',
      JSON.stringify({
        version: 1,
        status: 'skipped',
        currentStep: 2,
        goal: { stage: 'campus', targetRole: '数据分析师', city: '' },
        baseline: { entryMode: 'paste', content: '' },
        target: { mode: '', jd: '', templateId: '' },
        analysis: null,
        savedAt: '2026-07-11T00:00:00.000Z',
        activatedAt: null,
      }),
    )

    renderOnboarding('/onboarding?resume=1')

    expect(screen.getByText(/已恢复上次进度/i)).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /创建根简历草稿/i })).toBeInTheDocument()
  })

  it('shows a disabled loading state before activating the demo analysis', async () => {
    vi.useFakeTimers()
    try {
      renderOnboarding()

      fireEvent.click(screen.getByRole('button', { name: '校招' }))
      fireEvent.change(screen.getByLabelText(/目标岗位或方向/i), {
        target: { value: '产品经理' },
      })
      fireEvent.click(screen.getByRole('button', { name: /下一步/i }))
      fireEvent.click(screen.getByRole('button', { name: /从空白草稿开始/i }))
      fireEvent.click(screen.getByRole('button', { name: /下一步/i }))
      fireEvent.click(screen.getByRole('button', { name: /先选岗位模板/i }))
      fireEvent.click(screen.getByRole('button', { name: '产品经理' }))
      fireEvent.click(screen.getByRole('button', { name: /检查并生成/i }))

      const generate = screen.getByRole('button', { name: /生成 Demo 岗位定制简历/i })
      fireEvent.click(generate)
      expect(screen.getByRole('button', { name: /正在生成 Demo/i })).toBeDisabled()

      await act(async () => vi.advanceTimersByTimeAsync(850))

      expect(screen.getByRole('heading', { name: /第一份岗位定制简历已就绪/i })).toBeInTheDocument()
      expect(screen.queryByRole('button', { name: /暂时跳过/i })).not.toBeInTheDocument()
    } finally {
      vi.useRealTimers()
    }
  })
})
