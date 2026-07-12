import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AppRoutes } from '@/App'
import { setTokens, clearTokens } from '@/api/token-storage'
import { useAuthStore } from '@/stores/useAuthStore'

vi.mock('@/components/layout/AppShell', () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}))

vi.mock('@/admin/routes', () => ({
  AdminAppRoutes: () => <div>管理后台路由已挂载</div>,
}))

function renderRoute(path: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter
        initialEntries={[path]}
        future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
      >
        <AppRoutes />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('authenticated app routing', () => {
  beforeEach(() => {
    clearTokens()
    setTokens({ access_token: 'test-access', refresh_token: 'test-refresh' })
    useAuthStore.setState({
      status: 'authenticated',
      user: {
        id: 'user-1',
        email: 'admin@example.com',
        display_name: '管理员',
        title: null,
        years_of_experience: null,
        target_role: null,
        bio: null,
        subscription: 'free',
        is_admin: true,
        avatar_url: null,
        created_at: '2026-07-11T00:00:00Z',
        updated_at: '2026-07-11T00:00:00Z',
      },
    })
  })

  it('mounts the existing admin application at /admin-console/*', async () => {
    renderRoute('/admin-console/command-center')

    expect(await screen.findByText('管理后台路由已挂载')).toBeInTheDocument()
  })

  it('renders a recoverable 404 instead of silently redirecting to dashboard', async () => {
    renderRoute('/definitely-not-a-real-route')

    expect(await screen.findByRole('heading', { name: '页面不存在' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '返回工作台' })).toHaveAttribute('href', '/dashboard')
  })
})
