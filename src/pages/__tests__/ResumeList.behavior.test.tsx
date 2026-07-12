import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ResumeList from '@/pages/ResumeList'

const mocks = vi.hoisted(() => ({
  resumes: [] as any[],
  galleryProps: null as null | { open: boolean; initialThemeId?: string },
}))

vi.mock('@/hooks/queries/useResumeV2List', () => ({
  useResumeV2List: () => ({ data: mocks.resumes, isLoading: false }),
}))

vi.mock('@/modules/resume/v2/api', () => ({
  duplicateResume: vi.fn(),
  deleteResume: vi.fn(),
  updateResume: vi.fn(),
}))

vi.mock('@/modules/resume/v2/components/TemplateGalleryModal', () => ({
  TemplateGalleryModal: (props: { open: boolean; initialThemeId?: string }) => {
    mocks.galleryProps = props
    return null
  },
}))

vi.mock('@/modules/resume/derive', () => ({
  RootResumeCard: () => <div data-testid="root-resume-card">根简历</div>,
  DerivedResumeList: () => <div data-testid="derived-resume-list">派生简历列表</div>,
  DeriveWizard: ({ open, initialJobId }: { open: boolean; initialJobId?: string }) =>
    open ? <div data-testid="derive-wizard-probe">{initialJobId || 'no-job'}</div> : null,
}))

function resume(id: string, kind: 'standard' | 'derived') {
  return {
    id,
    name: kind === 'standard' ? '独立产品简历' : '星河科技派生简历',
    slug: id,
    tags: [],
    is_public: false,
    is_locked: false,
    version: 1,
    created_at: null,
    updated_at: null,
    resume_kind: kind,
    job_id: kind === 'derived' ? 'job-1' : null,
  }
}

function renderPage(path = '/resume') {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <ResumeList />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('ResumeList interaction hierarchy', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.resumes = [resume('derived-1', 'derived'), resume('standard-1', 'standard')]
  })

  it('renders independent resumes before derived resumes', () => {
    renderPage()

    const independent = screen.getByTestId('independent-resume-section')
    const derived = screen.getByTestId('derived-resume-section')
    expect(independent.compareDocumentPosition(derived) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })

  it('exposes rename, duplicate and delete from a visible more menu', () => {
    renderPage()

    fireEvent.click(screen.getByRole('button', { name: '独立产品简历的更多操作' }))
    expect(screen.getByRole('menuitem', { name: '重命名' })).toBeInTheDocument()
    expect(screen.getByRole('menuitem', { name: '复制' })).toBeInTheDocument()
    expect(screen.getByRole('menuitem', { name: '删除' })).toBeInTheDocument()
  })

  it('opens the derive wizard and preselects the job from a deep link', () => {
    renderPage('/resume?derive=true&job_id=job-42')

    expect(screen.getByTestId('derive-wizard-probe')).toHaveTextContent('job-42')
  })

  it('keeps the old source_job_id deep link working as a derive alias', () => {
    renderPage('/resume?new=true&source_job_id=job-legacy')

    expect(screen.getByTestId('derive-wizard-probe')).toHaveTextContent('job-legacy')
  })

  it('uses the editor theme registry in the empty-state quick picks', () => {
    mocks.resumes = []
    renderPage()

    expect(screen.getAllByText('默认（秋风同款）')).toHaveLength(2)
    expect(screen.getAllByText('极简色')).toHaveLength(2)
    expect(screen.getAllByText('平面大气主题')).toHaveLength(2)
    expect(screen.queryByText('Pikachu')).not.toBeInTheDocument()

    fireEvent.click(screen.getByTestId('recommended-theme-muji-minimal-color'))
    expect(mocks.galleryProps).toMatchObject({ open: true, initialThemeId: 'muji-minimal-color' })
  })
})
