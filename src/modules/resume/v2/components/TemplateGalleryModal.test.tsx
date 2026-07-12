import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { TemplateGalleryModal } from './TemplateGalleryModal'
import { createResume } from '@/modules/resume/v2/api'

vi.mock('@/modules/resume/v2/api', () => ({ createResume: vi.fn() }))
vi.mock('@/modules/resume/v2/editor/center/toast', () => ({ fireToast: vi.fn() }))

const createResumeMock = vi.mocked(createResume)

describe('TemplateGalleryModal v3 theme contract', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.spyOn(Date, 'now').mockReturnValue(1)
    createResumeMock.mockResolvedValue({
      id: 'resume-1',
      name: '产品经理简历',
      slug: 'resume-1',
    } as Awaited<ReturnType<typeof createResume>>)
  })

  it('shows exactly the same three themes as the editor', () => {
    render(<TemplateGalleryModal open onClose={vi.fn()} onCreated={vi.fn()} />)

    expect(screen.getAllByTestId(/^resume-theme-/)).toHaveLength(3)
    expect(screen.getByText('默认（秋风同款）')).toBeInTheDocument()
    expect(screen.getByText('极简色')).toBeInTheDocument()
    expect(screen.getByText('平面大气主题')).toBeInTheDocument()
    expect(screen.queryByText('Pikachu')).not.toBeInTheDocument()
    expect(screen.queryByText('Onyx')).not.toBeInTheDocument()
  })

  it('sends the selected v3 theme through the additive create contract', async () => {
    const onCreated = vi.fn()
    render(<TemplateGalleryModal open onClose={vi.fn()} onCreated={onCreated} />)

    fireEvent.click(screen.getByTestId('resume-theme-muji-minimal-color'))
    fireEvent.change(screen.getByLabelText('简历名称'), { target: { value: '产品经理简历' } })
    fireEvent.click(screen.getByTestId('template-gallery-confirm'))

    await waitFor(() => {
      expect(createResumeMock).toHaveBeenCalledWith({
        name: '产品经理简历',
        slug: 'resume-1',
        template: 'onyx',
        theme_id: 'muji-minimal-color',
        from_sample: false,
      })
    })
    expect(onCreated).toHaveBeenCalledWith({ id: 'resume-1', name: '产品经理简历', slug: 'resume-1' })
  })

  it('can open with a theme preselected by another create entry', () => {
    render(
      <TemplateGalleryModal
        open
        initialThemeId="muji-flat-atmospheric"
        onClose={vi.fn()}
        onCreated={vi.fn()}
      />,
    )

    expect(screen.getByTestId('resume-theme-muji-flat-atmospheric')).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByTestId('resume-theme-muji-default-autumn')).toHaveAttribute('aria-pressed', 'false')
  })
})
