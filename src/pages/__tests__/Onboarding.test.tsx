import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import Onboarding from '../Onboarding'
import { ApiError } from '@/api/errors'

const createRootResumeMock = vi.fn()
const getRootResumeMock = vi.fn()

vi.mock('@/modules/resume/derive/api', () => ({
  createRootResume: (...args: unknown[]) => createRootResumeMock(...args),
  getRootResume: (...args: unknown[]) => getRootResumeMock(...args),
}))

vi.mock('@/stores/useAuthStore', () => ({
  useAuthStore: (selector: (s: { user: { id: string } | null }) => unknown) =>
    selector({ user: { id: 'test-user-id' } }),
}))

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

const STORAGE_KEY = 'intercraft:onboarding:v1:test-user-id'

describe('Onboarding', () => {
  beforeEach(() => {
    window.localStorage.clear()
    createRootResumeMock.mockReset()
    getRootResumeMock.mockReset()
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

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
    expect(window.localStorage.getItem(STORAGE_KEY)).toContain('产品经理')
  })

  it('keeps skipped progress and exposes it as resumable', () => {
    renderOnboarding()

    fireEvent.click(screen.getByRole('button', { name: /暂时跳过/i }))

    expect(screen.getByText('Dashboard destination')).toBeInTheDocument()
    expect(window.localStorage.getItem(STORAGE_KEY)).toContain('skipped')
  })

  it('announces when a saved draft is resumed', () => {
    window.localStorage.setItem(
      STORAGE_KEY,
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
    // Mock the root create so Step 2 advances without touching real network.
    createRootResumeMock.mockResolvedValue({
      id: 'root-1',
      data: { metadata: { markdown: { sourceMarkdown: '' } } },
    })

    renderOnboarding()

    fireEvent.click(screen.getByRole('button', { name: '校招' }))
    fireEvent.change(screen.getByLabelText(/目标岗位或方向/i), {
      target: { value: '产品经理' },
    })
    fireEvent.click(screen.getByRole('button', { name: /下一步/i }))
    fireEvent.click(screen.getByRole('button', { name: /从空白草稿开始/i }))
    fireEvent.click(screen.getByRole('button', { name: /下一步/i }))
    await waitFor(() => expect(createRootResumeMock).toHaveBeenCalled())
    fireEvent.click(screen.getByRole('button', { name: /先选岗位模板/i }))
    fireEvent.click(screen.getByRole('button', { name: '产品经理' }))
    fireEvent.click(screen.getByRole('button', { name: /检查并生成/i }))

    const generate = screen.getByRole('button', { name: /生成 Demo 岗位定制简历/i })
    fireEvent.click(generate)
    expect(screen.getByRole('button', { name: /生成 Demo 岗位定制简历/i })).toBeDisabled()

    // The demo generator uses setTimeout(..., 850). With real timers we wait
    // for the heading to appear; no fake-timer juggling needed.
    expect(
      await screen.findByRole('heading', { name: /第一份岗位定制简历已就绪/i }, { timeout: 5_000 }),
    ).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /暂时跳过/i })).not.toBeInTheDocument()
  })

  it('awaits real createRootResume on Step 2 before advancing (blank mode)', async () => {
    createRootResumeMock.mockResolvedValue({
      id: 'root-blank-1',
      data: { metadata: { markdown: { sourceMarkdown: '' } } },
    })

    renderOnboarding()
    fireEvent.click(screen.getByRole('button', { name: '校招' }))
    fireEvent.change(screen.getByLabelText(/目标岗位或方向/i), {
      target: { value: '产品经理' },
    })
    fireEvent.click(screen.getByRole('button', { name: /下一步/i }))
    fireEvent.click(screen.getByRole('button', { name: /从空白草稿开始/i }))
    fireEvent.click(screen.getByRole('button', { name: /下一步/i }))

    await waitFor(() => expect(createRootResumeMock).toHaveBeenCalledTimes(1))
    const payload = createRootResumeMock.mock.calls[0]?.[0] as {
      name: string
      slug: string
      data: Record<string, unknown> & {
        metadata: { markdown: { sourceMarkdown: string } }
        basics: { name: string; email: string }
        summary: { content: string }
      }
    }
    expect(payload.name).toBe('根简历')
    expect(payload.slug).toBe('root-resume')
    expect(payload.data.metadata.markdown.sourceMarkdown).toBe('')
    // No demo identity leaked into basics/summary.
    expect(payload.data.basics.name).toBe('')
    expect(payload.data.basics.email).toBe('')
    expect(payload.data.summary.content).toBe('')

    // After persistence resolves, Step 3 (target job) is rendered.
    expect(screen.getByRole('heading', { name: /添加一个目标岗位/i })).toBeInTheDocument()
  })

  it('preserves the user marker byte-for-byte in paste/structured mode', async () => {
    createRootResumeMock.mockResolvedValue({
      id: 'root-paste-1',
      data: { metadata: { markdown: { sourceMarkdown: '我的真实经历' } } },
    })

    renderOnboarding()
    fireEvent.click(screen.getByRole('button', { name: '校招' }))
    fireEvent.change(screen.getByLabelText(/目标岗位或方向/i), {
      target: { value: '产品经理' },
    })
    fireEvent.click(screen.getByRole('button', { name: /下一步/i }))
    fireEvent.click(screen.getByRole('button', { name: /粘贴现有内容/i }))
    const textarea = screen.getByPlaceholderText(/负责某项产品/i) as HTMLTextAreaElement
    const marker = '  我有十年的用户研究与产品规划经验，主导多次上线。  '
    fireEvent.change(textarea, { target: { value: marker } })
    fireEvent.click(screen.getByRole('button', { name: /下一步/i }))

    await waitFor(() => expect(createRootResumeMock).toHaveBeenCalledTimes(1))
    const payload = createRootResumeMock.mock.calls[0]?.[0] as {
      data: { metadata: { markdown: { sourceMarkdown: string } } }
    }
    expect(payload.data.metadata.markdown.sourceMarkdown).toBe(marker)
  })

  it('keeps the user on Step 2 with a retryable error when the POST fails', async () => {
    createRootResumeMock.mockRejectedValueOnce(new Error('网络异常，请稍后重试。'))

    renderOnboarding()
    fireEvent.click(screen.getByRole('button', { name: '校招' }))
    fireEvent.change(screen.getByLabelText(/目标岗位或方向/i), {
      target: { value: '产品经理' },
    })
    fireEvent.click(screen.getByRole('button', { name: /下一步/i }))
    fireEvent.click(screen.getByRole('button', { name: /从空白草稿开始/i }))
    fireEvent.click(screen.getByRole('button', { name: /下一步/i }))

    await waitFor(() =>
      expect(screen.getByRole('alert')).toHaveTextContent(/网络异常/i),
    )
    // Still on Step 2 — must not advance after failure.
    expect(screen.getByRole('heading', { name: /创建根简历草稿/i })).toBeInTheDocument()
    // Retry button is rendered.
    expect(screen.getByTestId('onboarding-baseline-retry')).toBeInTheDocument()
  })

  it('rapid clicks fire only one createRootResume call (single-flight guard)', async () => {
    let resolveCreate: ((value: unknown) => void) | null = null
    createRootResumeMock.mockImplementation(
      () =>
        new Promise<unknown>((resolve) => {
          resolveCreate = resolve
        }),
    )

    renderOnboarding()
    fireEvent.click(screen.getByRole('button', { name: '校招' }))
    fireEvent.change(screen.getByLabelText(/目标岗位或方向/i), {
      target: { value: '产品经理' },
    })
    fireEvent.click(screen.getByRole('button', { name: /下一步/i }))
    fireEvent.click(screen.getByRole('button', { name: /从空白草稿开始/i }))

    const next = screen.getByRole('button', { name: /下一步/i })
    fireEvent.click(next)
    fireEvent.click(next)
    fireEvent.click(next)

    // Only one in-flight POST should have been issued despite rapid clicks.
    expect(createRootResumeMock).toHaveBeenCalledTimes(1)
    expect(next).toBeDisabled()

    // Skip button must be disabled while the POST is in flight.
    expect(screen.getByTestId('onboarding-skip')).toBeDisabled()

    // Resolve the promise and confirm the page advances.
    await act(async () => {
      resolveCreate?.({
        id: 'root-1',
        data: { metadata: { markdown: { sourceMarkdown: '' } } },
      })
    })
    await waitFor(() =>
      expect(screen.getByRole('heading', { name: /添加一个目标岗位/i })).toBeInTheDocument(),
    )
  })

  it('treats 409 ROOT_EXISTS as success and reuses the existing root path', async () => {
    createRootResumeMock.mockRejectedValueOnce(
      new ApiError({
        status: 409,
        code: 'ROOT_EXISTS',
        message: 'User already has a root resume.',
        requestId: 'req-test',
      }),
    )
    getRootResumeMock.mockResolvedValue({ id: 'root-existing' })

    renderOnboarding()
    fireEvent.click(screen.getByRole('button', { name: '校招' }))
    fireEvent.change(screen.getByLabelText(/目标岗位或方向/i), {
      target: { value: '产品经理' },
    })
    fireEvent.click(screen.getByRole('button', { name: /下一步/i }))
    fireEvent.click(screen.getByRole('button', { name: /从空白草稿开始/i }))
    fireEvent.click(screen.getByRole('button', { name: /下一步/i }))

    await waitFor(() => expect(createRootResumeMock).toHaveBeenCalledTimes(1))
    await waitFor(() => expect(getRootResumeMock).toHaveBeenCalledTimes(1))
    expect(screen.getByRole('heading', { name: /添加一个目标岗位/i })).toBeInTheDocument()
  })

  it('does not advance when 409 reuse GET fails — retryable error stays on Step 2', async () => {
    createRootResumeMock.mockRejectedValueOnce(
      new ApiError({
        status: 409,
        code: 'ROOT_EXISTS',
        message: 'User already has a root resume.',
        requestId: 'req-test',
      }),
    )
    getRootResumeMock.mockRejectedValueOnce(new Error('读取已有根简历失败'))

    renderOnboarding()
    fireEvent.click(screen.getByRole('button', { name: '校招' }))
    fireEvent.change(screen.getByLabelText(/目标岗位或方向/i), {
      target: { value: '产品经理' },
    })
    fireEvent.click(screen.getByRole('button', { name: /下一步/i }))
    fireEvent.click(screen.getByRole('button', { name: /从空白草稿开始/i }))
    fireEvent.click(screen.getByRole('button', { name: /下一步/i }))

    await waitFor(() =>
      expect(screen.getByRole('alert')).toHaveTextContent(/读取已有根简历失败/i),
    )
    expect(screen.getByRole('heading', { name: /创建根简历草稿/i })).toBeInTheDocument()
  })
})