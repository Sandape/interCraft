/**
 * 036 REQ-036 US4 T056 — Topbar 新建流程 unit tests.
 *
 * The "new resume" flow has two surfaces:
 *   1. The Topbar "+" button (data-testid="topbar-new-resume-button").
 *      It ONLY navigates to /resume?new=true (the previous-dropdown split
 *      was retired in Phase A.2).
 *   2. The TemplateGalleryModal inside ResumeList. ?new=true triggers
 *      `setGalleryOpen(true)` and strips the param so a refresh does
 *      not re-open the modal.
 *
 * Success path: pick template → `createResume()` → navigate to
 * /resume/{newId}.
 * Cancel path: close modal → no createResume call → no navigation.
 */

import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Topbar } from '@/components/layout/Topbar'
import { ThemeProvider } from '@/contexts/ThemeContext'
import ResumeList from '@/pages/ResumeList'
import { useAuthStore } from '@/stores/useAuthStore'

// ── mocks ───────────────────────────────────────────────────────────────

const mockNavigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return { ...actual, useNavigate: () => mockNavigate }
})

const v2ListMock = vi.fn().mockResolvedValue({ data: [] })
const createResumeMock = vi.fn()
vi.mock('@/modules/resume/v2/api', () => ({
  listResumes: (...args: unknown[]) => v2ListMock(...args),
  createResume: (...args: unknown[]) => createResumeMock(...args),
}))

beforeAll(() => {
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
  v2ListMock.mockReset()
  v2ListMock.mockResolvedValue({ data: [] })
  createResumeMock.mockReset()
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

function renderWithRouter(initialPath: string) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <ThemeProvider>
        <MemoryRouter initialEntries={[initialPath]}>
          <Routes>
            <Route path="/resume" element={<ResumeList />} />
            <Route path="/resume/:id" element={<div data-testid="editor-stub" />} />
          </Routes>
        </MemoryRouter>
      </ThemeProvider>
    </QueryClientProvider>,
  )
}

function renderTopbarOnly() {
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

// ── Tests ───────────────────────────────────────────────────────────────

describe('US4 T056 — Topbar 新建简历 flow (036 Phase B)', () => {
  it('Topbar + 按钮 navigate 到 /resume?new=true', () => {
    renderTopbarOnly()
    fireEvent.click(screen.getByTestId('topbar-new-resume-button'))
    expect(mockNavigate).toHaveBeenCalledWith('/resume?new=true')
  })

  it('Topbar 单按钮不存在 v1/v2 下拉菜单项', () => {
    renderTopbarOnly()
    expect(screen.queryByTestId('topbar-new-resume-menu')).not.toBeInTheDocument()
    expect(screen.queryByTestId('topbar-new-resume-blank')).not.toBeInTheDocument()
    expect(screen.queryByTestId('topbar-new-resume-v2')).not.toBeInTheDocument()
  })

  it('?new=true 自动打开 Template Gallery modal', async () => {
    renderWithRouter('/resume?new=true')
    await waitFor(() => {
      expect(screen.getByTestId('template-gallery-grid')).toBeInTheDocument()
    })
    expect(screen.getByTestId('template-gallery-confirm')).toBeInTheDocument()
    expect(screen.getByTestId('template-gallery-cancel')).toBeInTheDocument()
  })

  it('Template Gallery 含 10 个精选模板 + 1 个空白模板 (11 个选项)', async () => {
    renderWithRouter('/resume?new=true')
    await waitFor(() => {
      expect(screen.getByTestId('template-gallery-grid')).toBeInTheDocument()
    })
    // 10 templates + 1 blank
    expect(screen.getByTestId('template-thumbnail-blank')).toBeInTheDocument()
    for (const id of [
      'onyx',
      'azurill',
      'kakuna',
      'chikorita',
      'ditgar',
      'bronzor',
      'pikachu',
      'lapras',
      'scizor',
      'rhyhorn',
    ]) {
      expect(screen.getByTestId(`template-thumbnail-${id}`)).toBeInTheDocument()
    }
  })

  it('选 Pikachu + 确认 → createResume 调 + 跳 /resume/{newId}', async () => {
    createResumeMock.mockResolvedValueOnce({
      id: 'new-resume-id-1',
      name: 'Pikachu',
      slug: 'pikachu',
    })

    renderWithRouter('/resume?new=true')
    await waitFor(() => {
      expect(screen.getByTestId('template-thumbnail-pikachu')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByTestId('template-thumbnail-pikachu'))
    fireEvent.click(screen.getByTestId('template-gallery-confirm'))

    await waitFor(() => {
      expect(createResumeMock).toHaveBeenCalledWith(
        expect.objectContaining({
          name: 'Pikachu',
          template: 'pikachu',
        }),
      )
    })
    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/resume/new-resume-id-1')
    })
  })

  it('选"空白模板" → createResume 用 onyx 作为模板', async () => {
    createResumeMock.mockResolvedValueOnce({
      id: 'new-resume-id-2',
      name: '未命名简历',
      slug: 'untitled',
    })

    renderWithRouter('/resume?new=true')
    await waitFor(() => {
      expect(screen.getByTestId('template-thumbnail-blank')).toBeInTheDocument()
    })
    fireEvent.click(screen.getByTestId('template-thumbnail-blank'))
    fireEvent.click(screen.getByTestId('template-gallery-confirm'))

    await waitFor(() => {
      expect(createResumeMock).toHaveBeenCalledWith(
        expect.objectContaining({
          name: '未命名简历',
          template: 'onyx',
        }),
      )
    })
  })

  it('createResume 失败 → 不跳 + 停留 modal', async () => {
    createResumeMock.mockRejectedValueOnce(new Error('server 500'))

    renderWithRouter('/resume?new=true')
    await waitFor(() => {
      expect(screen.getByTestId('template-thumbnail-pikachu')).toBeInTheDocument()
    })
    fireEvent.click(screen.getByTestId('template-thumbnail-pikachu'))
    fireEvent.click(screen.getByTestId('template-gallery-confirm'))

    // Wait for the failure to settle.
    await waitFor(() => {
      expect(createResumeMock).toHaveBeenCalled()
    })
    // The modal stays open + no navigation.
    expect(screen.getByTestId('template-gallery-confirm')).toBeInTheDocument()
    expect(mockNavigate).not.toHaveBeenCalledWith(expect.stringMatching(/^\/resume\/[^/]+$/))
  })

  it('取消 modal → 不创建任何简历', async () => {
    renderWithRouter('/resume?new=true')
    await waitFor(() => {
      expect(screen.getByTestId('template-gallery-grid')).toBeInTheDocument()
    })
    fireEvent.click(screen.getByTestId('template-gallery-cancel'))

    await waitFor(() => {
      expect(screen.queryByTestId('template-gallery-grid')).not.toBeInTheDocument()
    })
    expect(createResumeMock).not.toHaveBeenCalled()
    expect(mockNavigate).not.toHaveBeenCalledWith(expect.stringMatching(/^\/resume\/[^/]+$/))
  })
})