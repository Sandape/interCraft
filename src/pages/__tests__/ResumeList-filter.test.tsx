/** 027 US6 T079 — ResumeList search/filter/sort toolbar behavior. */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import ResumeList from '@/pages/ResumeList'
import { useAuthStore } from '@/stores/useAuthStore'

const mockNavigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return { ...actual, useNavigate: () => mockNavigate }
})

const branchesMock = vi.fn()
vi.mock('@/hooks/queries/useResumeBranches', () => ({
  useResumeBranches: (query?: { search?: string; status_filter?: string; sort?: string }) => ({
    data: branchesMock(query),
    isLoading: false,
  }),
}))

vi.mock('@/hooks/queries/useJobs', () => ({
  useJob: () => ({ data: undefined }),
}))

vi.mock('@/hooks/mutations/useBranchMutations', () => ({
  useCreateBranch: () => ({ mutate: vi.fn(), isPending: false }),
  useDeleteBranch: () => ({ mutate: vi.fn(), isPending: false }),
  usePatchBranch: () => ({ mutate: vi.fn(), isPending: false }),
}))

vi.mock('@/hooks/mutations/useJobMutations', () => ({
  useBindBranchToJob: () => ({ mutate: vi.fn() }),
}))

vi.mock('@/modules/resume/import/ImportModal', () => ({
  default: () => <div data-testid="import-modal-stub" />,
}))

beforeEach(() => {
  mockNavigate.mockReset()
  branchesMock.mockReset()
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

const mainBranch = {
  id: 'branch-main',
  name: '主简历',
  company: null,
  position: null,
  status: 'draft',
  is_main: true,
  is_pinned: false,
  parent_id: null,
  block_count: 0,
  version_count: 0,
  match_score: null,
  last_edited_at: '2026-06-01T00:00:00Z',
  theme_id: 'default',
  accent_color: '#39393a',
  avatar_url: null,
  avatar_size: null,
  avatar_position: null,
  avatar_shape: null,
  avatar_updated_at: null,
  created_at: '2026-06-01T00:00:00Z',
  updated_at: '2026-06-01T00:00:00Z',
}

const branches = [
  mainBranch,
  {
    ...mainBranch,
    id: 'branch-bytedance',
    name: '字节 · 前端',
    company: '字节跳动',
    position: '高级前端工程师',
    status: 'ready',
    is_main: false,
    match_score: 92,
  },
  {
    ...mainBranch,
    id: 'branch-alibaba',
    name: '阿里 · 后端',
    company: '阿里巴巴',
    position: '后端工程师',
    status: 'optimizing',
    is_main: false,
    match_score: 78,
  },
]

function renderList() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={['/resume']}>
        <Routes>
          <Route path="/resume" element={<ResumeList />} />
          <Route path="/resume/:id" element={<div data-testid="editor-stub" />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('ResumeList — search/filter/sort toolbar (US6 T079)', () => {
  it('renders toolbar with result count', async () => {
    branchesMock.mockReturnValue(branches)
    renderList()
    await waitFor(() => {
      expect(screen.getByTestId('resume-list-toolbar')).toBeInTheDocument()
    })
    expect(screen.getByText(/3 个分支/)).toBeInTheDocument()
  })

  it('passes search query to useResumeBranches after debounce', async () => {
    branchesMock.mockReturnValue(branches)
    renderList()
    await waitFor(() => {
      expect(screen.getByTestId('resume-list-search')).toBeInTheDocument()
    })
    fireEvent.change(screen.getByTestId('resume-list-search'), {
      target: { value: '字节' },
    })
    await waitFor(() => {
      expect(branchesMock).toHaveBeenCalledWith(expect.objectContaining({ search: '字节' }))
    })
  })

  it('opens status filter menu and toggles a status', async () => {
    branchesMock.mockReturnValue(branches)
    renderList()
    await waitFor(() => {
      expect(screen.getByTestId('resume-list-status-toggle')).toBeInTheDocument()
    })
    fireEvent.click(screen.getByTestId('resume-list-status-toggle'))
    expect(screen.getByTestId('resume-list-status-menu')).toBeInTheDocument()
    const labels = screen.getAllByText('就绪')
    fireEvent.click(labels[0].closest('label')!)
    await waitFor(() => {
      expect(branchesMock).toHaveBeenCalledWith(
        expect.objectContaining({ status_filter: 'ready' }),
      )
    })
  })

  it('supports multiple status filter (comma-separated)', async () => {
    branchesMock.mockReturnValue(branches)
    renderList()
    await waitFor(() => {
      expect(screen.getByTestId('resume-list-status-toggle')).toBeInTheDocument()
    })
    fireEvent.click(screen.getByTestId('resume-list-status-toggle'))
    fireEvent.click(screen.getAllByText('就绪')[0].closest('label')!)
    fireEvent.click(screen.getAllByText('优化中')[0].closest('label')!)
    await waitFor(() => {
      expect(branchesMock).toHaveBeenCalledWith(
        expect.objectContaining({ status_filter: 'ready,optimizing' }),
      )
    })
  })

  it('changes sort to "created"', async () => {
    branchesMock.mockReturnValue(branches)
    renderList()
    await waitFor(() => {
      expect(screen.getByTestId('resume-list-sort')).toBeInTheDocument()
    })
    fireEvent.change(screen.getByTestId('resume-list-sort'), {
      target: { value: 'created' },
    })
    await waitFor(() => {
      expect(branchesMock).toHaveBeenCalledWith(
        expect.objectContaining({ sort: 'created' }),
      )
    })
  })

  it('changes sort to "match_score"', async () => {
    branchesMock.mockReturnValue(branches)
    renderList()
    await waitFor(() => {
      expect(screen.getByTestId('resume-list-sort')).toBeInTheDocument()
    })
    fireEvent.change(screen.getByTestId('resume-list-sort'), {
      target: { value: 'match_score' },
    })
    await waitFor(() => {
      expect(branchesMock).toHaveBeenCalledWith(
        expect.objectContaining({ sort: 'match_score' }),
      )
    })
  })
})
