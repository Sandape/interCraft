import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import AgentSettings from '../AgentSettings'

const repository = vi.hoisted(() => ({
  fetchBindingStatus: vi.fn(),
  fetchPreferences: vi.fn(),
  fetchConsumerStatus: vi.fn(),
  fetchTasks: vi.fn(),
  fetchQrcode: vi.fn(),
  pollQrcodeStatus: vi.fn(),
  unbindWechat: vi.fn(),
  updatePreferences: vi.fn(),
  cancelTask: vi.fn(),
  resumeTask: vi.fn(),
}))

vi.mock('@/repositories/AgentRepository', () => ({
  AgentRepository: repository,
  resolveQrcodeSrc: vi.fn(),
}))

function renderPage() {
  const qc = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  })
  return render(
    <QueryClientProvider client={qc}>
      <AgentSettings />
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  repository.fetchPreferences.mockResolvedValue({
    display_name: '我的求职助手',
    quiet_hours_start: null,
    quiet_hours_end: null,
    notification_mode: 'realtime',
  })
  repository.fetchConsumerStatus.mockResolvedValue({ enabled: false, state: 'disabled' })
  repository.fetchTasks.mockResolvedValue({ items: [] })
})

describe('AgentSettings binding state', () => {
  it('does not represent an API failure as an unbound account', async () => {
    repository.fetchBindingStatus.mockRejectedValueOnce(new Error('database unavailable'))

    renderPage()

    expect(await screen.findByRole('alert')).toHaveTextContent('暂时无法读取微信绑定状态')
    expect(screen.queryByRole('button', { name: '获取绑定二维码' })).not.toBeInTheDocument()

    repository.fetchBindingStatus.mockResolvedValueOnce({
      bound: false,
      agent_status: 'dormant',
    })
    fireEvent.click(screen.getByRole('button', { name: '重试' }))

    await waitFor(() => {
      expect(screen.getByRole('button', { name: '获取绑定二维码' })).toBeInTheDocument()
    })
  })

  it('renders the persisted bound state returned by the API', async () => {
    repository.fetchBindingStatus.mockResolvedValue({
      bound: true,
      agent_status: 'active',
      bound_at: '2026-07-11T00:00:00Z',
    })

    renderPage()

    expect(await screen.findByText('已绑定微信')).toBeInTheDocument()
    expect(screen.getByText('状态：在线')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '获取绑定二维码' })).not.toBeInTheDocument()
  })
})
