/** 019 — Topbar "新建简历" dropdown (blank + 基于岗位). */
import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Topbar } from '@/components/layout/Topbar'
import { ThemeProvider } from '@/contexts/ThemeContext'
import { useAuthStore } from '@/stores/useAuthStore'

const mockNavigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return { ...actual, useNavigate: () => mockNavigate }
})

beforeAll(() => {
  // matchMedia is referenced by ThemeContext; jsdom doesn't ship it.
  if (!window.matchMedia) {
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      value: vi.fn().mockImplementation((query: string) => ({
        matches: false,
        media: query,
        onchange: null,
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
      created_at: '2026-06-01T00:00:00Z',
      updated_at: '2026-06-12T00:00:00Z',
    },
  })
})

function renderTopbar() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <ThemeProvider>
        <MemoryRouter>
          <Topbar />
        </MemoryRouter>
      </ThemeProvider>
    </QueryClientProvider>,
  )
}

describe('Topbar — new-resume dropdown (019)', () => {
  it('opens the menu and renders blank + per-job items', async () => {
    renderTopbar()
    fireEvent.click(screen.getByTestId('topbar-new-resume-button'))

    await waitFor(() => {
      expect(screen.getByTestId('topbar-new-resume-menu')).toBeInTheDocument()
    })
    await waitFor(() => {
      expect(screen.getByTestId('topbar-new-resume-blank')).toHaveTextContent('空白创建')
    })
    // wait for useJobs() to resolve
    await waitFor(() => {
      expect(screen.getByTestId('topbar-new-resume-from-job-job-mock-1')).toBeInTheDocument()
    })
  })

  it('blank create navigates to /resume?new=true', async () => {
    renderTopbar()
    fireEvent.click(screen.getByTestId('topbar-new-resume-button'))
    await waitFor(() => screen.getByTestId('topbar-new-resume-blank'))
    fireEvent.click(screen.getByTestId('topbar-new-resume-blank'))
    expect(mockNavigate).toHaveBeenCalledWith('/resume?new=true')
  })

  it('job-based create navigates to /resume?new=true&source_job_id={id}', async () => {
    renderTopbar()
    fireEvent.click(screen.getByTestId('topbar-new-resume-button'))
    await waitFor(() => screen.getByTestId('topbar-new-resume-from-job-job-mock-1'))
    fireEvent.click(screen.getByTestId('topbar-new-resume-from-job-job-mock-1'))
    expect(mockNavigate).toHaveBeenCalledWith('/resume?new=true&source_job_id=job-mock-1')
  })

  it('clicking outside closes the menu', async () => {
    renderTopbar()
    fireEvent.click(screen.getByTestId('topbar-new-resume-button'))
    await waitFor(() => screen.getByTestId('topbar-new-resume-menu'))
    // The overlay is a sibling div with class "fixed inset-0 z-40"
    const overlay = document.querySelector('.fixed.inset-0.z-40') as HTMLElement
    expect(overlay).toBeInTheDocument()
    fireEvent.click(overlay)
    await waitFor(() => {
      expect(screen.queryByTestId('topbar-new-resume-menu')).not.toBeInTheDocument()
    })
  })
})
