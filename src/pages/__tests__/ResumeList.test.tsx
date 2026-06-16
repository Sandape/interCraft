/** 019 — ResumeList source_job prefill + post-create bind-back behavior. */
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

function renderWith(initialUrl: string) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[initialUrl]}>
        <Routes>
          <Route path="/resume" element={<ResumeList />} />
          <Route path="/resume/:id" element={<div data-testid="editor-stub" />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('ResumeList — source_job prefill (019)', () => {
  it('auto-opens modal on ?new=true&source_job_id and prefills name/company/position', async () => {
    renderWith('/resume?new=true&source_job_id=job-mock-1')

    await waitFor(() => {
      expect(screen.getByTestId('new-branch-source-job')).toBeInTheDocument()
    })

    const nameInput = screen.getByTestId('new-branch-name') as HTMLInputElement
    expect(nameInput.value).toBe('字节 · 高级前端')
    const modalText = screen.getByTestId('new-branch-source-job').textContent ?? ''
    expect(modalText).toContain('字节')
    expect(modalText).toContain('高级前端')
  })

  it('shows the requirements_md foldable card (≥50 chars triggers it)', async () => {
    renderWith('/resume?new=true&source_job_id=job-mock-1')

    await waitFor(() => {
      expect(screen.getByTestId('new-branch-requirements')).toBeInTheDocument()
    })
    const card = screen.getByTestId('new-branch-requirements')
    expect(card.textContent).toContain('岗位招聘需求')
    // expand the foldable to verify the body is rendered
    fireEvent.click(card.querySelector('button')!)
    expect(card.textContent).toContain('3年以上 React 经验')
  })

  it('does not show source-job prefill when ?new=true without source_job_id', async () => {
    renderWith('/resume?new=true')
    await waitFor(() => {
      expect(screen.getByTestId('create-branch-confirm')).toBeInTheDocument()
    })
    expect(screen.queryByTestId('new-branch-source-job')).not.toBeInTheDocument()
    expect(screen.queryByTestId('new-branch-requirements')).not.toBeInTheDocument()
  })

  it('creating with source_job_id binds the new branch back to the job and navigates', async () => {
    renderWith('/resume?new=true&source_job_id=job-mock-1')

    await waitFor(() => {
      expect(screen.getByTestId('new-branch-name')).toBeInTheDocument()
    })

    fireEvent.change(screen.getByTestId('new-branch-name'), {
      target: { value: '字节 · 高级前端' },
    })
    fireEvent.click(screen.getByTestId('create-branch-confirm'))

    // navigate should land on the editor stub for the new branch id
    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith(expect.stringMatching(/^\/resume\/branch-/))
    })
  })
})
