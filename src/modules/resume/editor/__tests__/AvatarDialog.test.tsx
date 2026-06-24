/**
 * AvatarDialog — smoke test for the upload + adjust UI (spec 027 US9).
 *
 * The mutation hooks themselves are covered by `useBranchAvatar.test.tsx`;
 * here we only verify that the dialog renders the right slots per branch
 * state (no avatar / has avatar / has parent) and wires the buttons to the
 * mutation action stubs.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'

const mockUpload = vi.fn()
const mockDelete = vi.fn()
const mockInherit = vi.fn()

vi.mock('@/modules/resume/hooks/useBranchAvatar', () => ({
  useUploadBranchAvatar: () => ({
    mutateAsync: mockUpload,
    isPending: false,
    error: null,
  }),
  useDeleteBranchAvatar: () => ({
    mutateAsync: mockDelete,
    isPending: false,
    error: null,
  }),
  useInheritBranchAvatar: () => ({
    mutateAsync: mockInherit,
    isPending: false,
    error: null,
  }),
}))

import AvatarDialog from '../AvatarDialog'
import type { ResumeBranch } from '../../api/types'

function makeBranch(overrides: Partial<ResumeBranch> = {}): ResumeBranch {
  return {
    id: 'b1',
    parent_id: null,
    name: '主简历',
    company: null,
    position: null,
    status: 'draft',
    match_score: null,
    is_main: true,
    is_pinned: false,
    style_preference: null,
    theme_id: 'default',
    accent_color: '#39393a',
    avatar_url: null,
    avatar_size: null,
    avatar_position: null,
    avatar_shape: null,
    avatar_updated_at: null,
    last_edited_at: '2026-06-23T00:00:00Z',
    created_at: '2026-06-23T00:00:00Z',
    updated_at: '2026-06-23T00:00:00Z',
    version_count: 0,
    block_count: 0,
    ...overrides,
  }
}

const onSave = vi.fn().mockResolvedValue(undefined)
const onClose = vi.fn()

beforeEach(() => {
  vi.clearAllMocks()
})

describe('AvatarDialog — empty branch', () => {
  it('shows the upload CTA when the branch has no avatar', () => {
    render(
      <AvatarDialog
        open
        onClose={onClose}
        branch={makeBranch()}
        onSave={onSave}
      />,
    )
    expect(screen.getByTestId('avatar-pick-empty')).toBeInTheDocument()
    // The size slider is disabled because no avatar yet.
    const slider = screen.getByTestId('avatar-size-slider') as HTMLInputElement
    expect(slider.disabled).toBe(true)
  })

  it('hides inherit-from-parent button when branch has no parent', () => {
    render(
      <AvatarDialog
        open
        onClose={onClose}
        branch={makeBranch()}
        onSave={onSave}
      />,
    )
    expect(screen.queryByTestId('avatar-inherit')).not.toBeInTheDocument()
  })

  it('save button is disabled when no avatar and nothing to save', () => {
    render(
      <AvatarDialog
        open
        onClose={onClose}
        branch={makeBranch()}
        onSave={onSave}
      />,
    )
    const save = screen.getByTestId('avatar-save') as HTMLButtonElement
    expect(save.disabled).toBe(true)
  })
})

describe('AvatarDialog — branch with avatar', () => {
  const branch = makeBranch({
    avatar_url: '/api/v1/resume-branches/b1/avatar',
    avatar_size: 100,
    avatar_position: 'right',
    avatar_shape: 'circle',
  })

  it('shows the controls (replace + delete), enables slider', () => {
    render(
      <AvatarDialog
        open
        onClose={onClose}
        branch={branch}
        onSave={onSave}
      />,
    )
    expect(screen.getByTestId('avatar-replace')).toBeInTheDocument()
    expect(screen.getByTestId('avatar-delete')).toBeInTheDocument()
    expect((screen.getByTestId('avatar-size-slider') as HTMLInputElement).disabled).toBe(false)
  })

  it('shows inherit-from-parent button when branch has a parent', () => {
    render(
      <AvatarDialog
        open
        onClose={onClose}
        branch={makeBranch({
          parent_id: 'parent-1',
          avatar_url: '/api/v1/resume-branches/b1/avatar',
        })}
        onSave={onSave}
      />,
    )
    expect(screen.getByTestId('avatar-inherit')).toBeInTheDocument()
  })

  it('clicking delete calls the delete mutation', async () => {
    mockDelete.mockResolvedValueOnce({ ok: true })
    render(
      <AvatarDialog
        open
        onClose={onClose}
        branch={branch}
        onSave={onSave}
      />,
    )
    fireEvent.click(screen.getByTestId('avatar-delete'))
    await vi.waitFor(() => expect(mockDelete).toHaveBeenCalled())
  })

  it('selecting a different position marks the save button enabled when branch.avatar_position differs from draft', () => {
    // Draft starts at 'right' (matches branch); change to 'left' → dirty → enable.
    render(
      <AvatarDialog
        open
        onClose={onClose}
        branch={branch}
        onSave={onSave}
      />,
    )
    fireEvent.click(screen.getByTestId('avatar-position-left'))
    const save = screen.getByTestId('avatar-save') as HTMLButtonElement
    expect(save.disabled).toBe(false)
  })
})