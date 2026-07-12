import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it } from 'vitest'
import { AppRoutes } from '@/App'
import { useAuthStore } from '@/stores/useAuthStore'

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

describe('public routes', () => {
  beforeEach(() => {
    window.sessionStorage.clear()
    useAuthStore.getState().clear()
  })

  it('renders the product homepage at / without authentication', () => {
    renderRoute('/')

    expect(
      screen.getByRole('heading', { name: /把一份根简历，变成每个目标岗位的完整准备/i }),
    ).toBeInTheDocument()
  })

  it('renders the read-only sample workspace at /demo without authentication', async () => {
    renderRoute('/demo')

    expect((await screen.findAllByText(/只读模式/i)).length).toBeGreaterThan(0)
  })

  it('keeps onboarding protected for unauthenticated visitors', async () => {
    renderRoute('/onboarding')

    expect(await screen.findByRole('heading', { name: '欢迎回来' })).toBeInTheDocument()
  })
})
