import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, within } from '@testing-library/react'
import { UsersAccounts } from '../UsersAccounts'

const mockProfile = vi.hoisted(() => ({
  userId: '019ec1be-0000-7000-8000-000000000001',
  fields: [
    { name: 'email', visibility: 'masked', value: 'demo***@intercraft.io' },
    { name: 'role', visibility: 'full', value: 'pm' },
    { name: 'journey_summary', visibility: 'full', value: 'registered' },
    { name: 'incidents_count', visibility: 'full', value: '0' },
    { name: 'quality_score', visibility: 'full', value: '0.91' },
    { name: 'created_at', visibility: 'full', value: '2026-05-12T09:21:00Z' },
    { name: 'last_active_at', visibility: 'full', value: '2026-07-04T08:00:00Z' },
  ],
  cohortPopulation: 5234,
  lastComputedAt: '2026-07-04T10:00:00Z',
  freshnessAt: '2026-07-04T10:00:00Z',
}))

vi.mock('@/admin/hooks/queries/useUserSafe', () => ({
  useUserSafe: (userId: string | null) => ({
    isLoading: false,
    isError: false,
    error: null,
    data: userId ? mockProfile : null,
  }),
}))

describe('UsersAccounts page interactions', () => {
  it('opens the privacy-safe drawer when a seed user is selected', () => {
    render(<UsersAccounts />)

    expect(screen.getByTestId('user-drawer-empty')).toBeInTheDocument()

    const firstResult = screen.getByTestId(
      'user-search-result-019ec1be-0000-7000-8000-000000000001',
    )
    fireEvent.click(within(firstResult).getByRole('button'))

    expect(screen.getByTestId('user-drawer')).toBeInTheDocument()
    expect(screen.getByTestId('user-drawer-user-id').textContent).toContain(
      '019ec1be-0000-7000-8000-000000000001',
    )
    expect(screen.getByTestId('user-drawer-row-email')).toBeInTheDocument()
  })
})
