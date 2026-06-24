/** 027 Phase B B5 — Square marketplace smoke tests. */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import Square from '../Square'

const mockNavigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return { ...actual, useNavigate: () => mockNavigate }
})

const mockCreateBranch = vi.fn()
const mockBlockCreate = vi.fn()
vi.mock('@/hooks/mutations/useBranchMutations', () => ({
  useCreateBranch: () => ({
    mutateAsync: mockCreateBranch,
    isPending: false,
  }),
}))

vi.mock('@/repositories/types', () => ({
  getResumeBlockRepository: () => ({
    create: mockBlockCreate,
  }),
}))

// Stub fetch — return 2 fake templates
const mockTemplates = [
  {
    id: 1,
    title: '带证件照的简历模板',
    thumbnail: 'https://example.com/1.jpg',
    template: '# 秋风\n\n## 介绍\n\n前端工程师',
    author: '秋风',
    avatar: 'https://example.com/avatar1.png',
    theme: 'blue',
    collect: 9999,
    updateTime: 1586908800000,
  },
  {
    id: 2,
    title: '简洁模板',
    thumbnail: 'https://example.com/2.jpg',
    template: '# 张三\n\n## 工作\n\n某公司',
    author: '张三',
    avatar: 'https://example.com/avatar2.png',
    theme: 'default',
    collect: 100,
    updateTime: 1586908800000,
  },
]

function renderSquare() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={['/resume/marketplace']}>
        <Routes>
          <Route path="/resume/marketplace" element={<Square />} />
          <Route path="/resume" element={<div data-testid="resume-list-stub" />} />
          <Route path="/resume/:id" element={<div data-testid="editor-stub" />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  mockNavigate.mockReset()
  mockCreateBranch.mockReset()
  mockBlockCreate.mockReset()
  global.fetch = vi.fn().mockResolvedValue({
    json: () => Promise.resolve(mockTemplates),
  }) as unknown as typeof global.fetch
})

describe('Square marketplace (Phase B B5)', () => {
  it('renders template cards after loading', async () => {
    renderSquare()
    await waitFor(() => {
      expect(screen.getByText('带证件照的简历模板')).toBeInTheDocument()
    })
    expect(screen.getByText('简洁模板')).toBeInTheDocument()
  })

  it('back button navigates to /resume', async () => {
    renderSquare()
    await waitFor(() => screen.getByText('带证件照的简历模板'))
    fireEvent.click(screen.getByText('返回简历中心'))
    expect(mockNavigate).toHaveBeenCalledWith('/resume')
  })

  it('download button creates a blob and triggers a download', async () => {
    // jsdom lacks URL.createObjectURL — stub it
    const createUrlStub = vi.fn().mockReturnValue('blob:mock')
    const revokeUrlStub = vi.fn()
    const origCreate = URL.createObjectURL
    const origRevoke = URL.revokeObjectURL
    // @ts-expect-error — jsdom lacks these
    URL.createObjectURL = createUrlStub
    // @ts-expect-error — jsdom lacks these
    URL.revokeObjectURL = revokeUrlStub

    renderSquare()
    await waitFor(() => screen.getByText('带证件照的简历模板'))
    const downloadButtons = screen.getAllByText('下载')
    fireEvent.click(downloadButtons[0])
    expect(createUrlStub).toHaveBeenCalled()
    expect(revokeUrlStub).toHaveBeenCalled()

    URL.createObjectURL = origCreate
    URL.revokeObjectURL = origRevoke
  })

  it('preview button opens the modal with template details', async () => {
    renderSquare()
    await waitFor(() => screen.getByText('带证件照的简历模板'))
    const previewButtons = screen.getAllByText('预览')
    fireEvent.click(previewButtons[0])
    await waitFor(() => {
      expect(screen.getByText('作者：秋风')).toBeInTheDocument()
    })
  })

  it('"使用此模板" creates a branch + writes blocks + navigates to editor', async () => {
    mockCreateBranch.mockResolvedValue({ id: 'branch-new-1' })
    mockBlockCreate.mockResolvedValue({})
    renderSquare()
    await waitFor(() => screen.getByText('带证件照的简历模板'))
    // Click the card's "使用此模板" button
    const useButtons = screen.getAllByText('使用此模板')
    fireEvent.click(useButtons[0])
    await waitFor(() => {
      expect(screen.getByText('决定了')).toBeInTheDocument()
    })
    fireEvent.click(screen.getByText('决定了'))
    await waitFor(() => {
      expect(mockCreateBranch).toHaveBeenCalledWith(
        expect.objectContaining({ name: '带证件照的简历模板' }),
      )
    })
    // blocks should have been written
    await waitFor(() => {
      expect(mockBlockCreate.mock.calls.length).toBeGreaterThan(0)
    })
    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/resume/branch-new-1')
    })
  })
})
