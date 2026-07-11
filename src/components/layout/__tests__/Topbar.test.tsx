import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Topbar } from '@/components/layout/Topbar'
import { ThemeProvider } from '@/contexts/ThemeContext'
import { useAuthStore } from '@/stores/useAuthStore'

const mockNavigate = vi.fn()
const notificationMocks = vi.hoisted(() => ({
  get: vi.fn(),
  markRead: vi.fn(),
}))

vi.mock('@/api/account', () => ({
  accountApi: {
    getNotificationCenter: notificationMocks.get,
    markNotificationRead: notificationMocks.markRead,
  },
}))
vi.mock('@/hooks/queries/useAIPoints', () => ({
  useAIPointAccount: () => ({
    data: {
      plan_label: 'Pro',
      experience_badge: '新用户体验',
      is_paid: false,
      available: 2000,
      reserved: 0,
      buckets: [],
      next_expiry: null,
      daily_grant_amount: 2000,
      parallel_ai_task_limit: 2,
      history_days: 90,
      business_date: '2026-07-11',
      timezone: 'Asia/Shanghai',
      grant_config_version: 'v1',
    },
    isPending: false,
    isError: false,
    isFetching: false,
    refetch: vi.fn(),
  }),
}))
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return { ...actual, useNavigate: () => mockNavigate }
})

beforeAll(() => {
  if (!window.matchMedia) {
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      value: vi.fn().mockImplementation((query: string) => ({
        matches: false,
        media: query,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    })
  }
})

beforeEach(() => {
  mockNavigate.mockReset()
  notificationMocks.get.mockReset()
  notificationMocks.get.mockResolvedValue({ notifications: [], unread_count: 0 })
  notificationMocks.markRead.mockReset()
  notificationMocks.markRead.mockResolvedValue(undefined)
  useAuthStore.setState({
    user: {
      id: '01900000-0000-7000-8000-000000000001',
      email: 'demo@intercraft.io',
      display_name: 'Demo',
      title: '前端工程师',
      years_of_experience: 3,
      target_role: '高级前端',
      bio: null,
      avatar_url: null,
      subscription: 'free',
      is_admin: true,
      created_at: '2026-06-01T00:00:00Z',
      updated_at: '2026-06-12T00:00:00Z',
    },
  })
})

function renderTopbar(onOpenSearch = vi.fn()) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <ThemeProvider>
        <MemoryRouter>
          <Topbar onOpenSearch={onOpenSearch} />
        </MemoryRouter>
      </ThemeProvider>
    </QueryClientProvider>,
  )
  return { onOpenSearch }
}

describe('Topbar current interaction contract', () => {
  it('routes the single create action to the unified three-theme flow', () => {
    renderTopbar()

    fireEvent.click(screen.getByTestId('topbar-new-resume-button'))
    expect(mockNavigate).toHaveBeenCalledWith('/resume?new=true')
    expect(screen.queryByTestId('topbar-new-resume-menu')).not.toBeInTheDocument()
  })

  it('opens the shared command palette from search', () => {
    const { onOpenSearch } = renderTopbar()

    fireEvent.click(screen.getByTestId('topbar-search-input'))
    expect(onOpenSearch).toHaveBeenCalledTimes(1)
  })

  it('shows a truthful empty notification state without a fake unread dot', async () => {
    renderTopbar()

    const button = screen.getByTestId('topbar-notifications-button')
    expect(button.querySelector('.bg-brand-500')).toBeNull()
    fireEvent.click(button)
    expect(await screen.findByText('暂无新的待处理通知')).toBeInTheDocument()
    expect(screen.getByText('0 条未读')).toBeInTheDocument()
  })

  it('renders the real unread count and marks one notification as read', async () => {
    notificationMocks.get.mockResolvedValue({
      unread_count: 1,
      notifications: [
        {
          id: 'notice-1',
          type: 'report_ready',
          title: '面试报告已生成',
          message: '点击通知后会标记为已读。',
          related_task_id: null,
          is_read: false,
          created_at: '2026-07-11T00:00:00Z',
        },
      ],
    })
    renderTopbar()

    expect(await screen.findByTestId('topbar-unread-count')).toHaveTextContent('1')
    fireEvent.click(screen.getByTestId('topbar-notifications-button'))
    fireEvent.click(await screen.findByRole('button', { name: /面试报告已生成/ }))

    await waitFor(() => expect(notificationMocks.markRead).toHaveBeenCalledWith('notice-1'))
  })

  it('keeps the admin entry routed to the mounted admin application', () => {
    renderTopbar()

    fireEvent.click(screen.getByTestId('topbar-admin-console-button'))
    expect(mockNavigate).toHaveBeenCalledWith('/admin-console/command-center')
  })
})
