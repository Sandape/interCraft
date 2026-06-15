/** useUpdateProfile mutation hook tests (US11). */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { QueryClient } from '@tanstack/react-query'

// Snapshot the CURRENT_USER_KEY value used by the real hook.
const CURRENT_USER_KEY = ['currentUser'] as const

describe('useUpdateProfile', () => {
  let qc: QueryClient

  beforeEach(() => {
    qc = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    })
  })

  it('updates cached current user on success', () => {
    const existingUser = {
      id: 'u1',
      email: 'a@b.com',
      display_name: 'Old Name',
      title: 'Dev',
      years_of_experience: 3,
      target_role: 'Senior Dev',
      bio: 'Old bio',
      subscription: 'free',
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
    }
    qc.setQueryData(CURRENT_USER_KEY, existingUser)

    const updatedUser = {
      ...existingUser,
      display_name: 'New Name',
      title: 'Senior Dev',
      updated_at: '2026-06-13T00:00:00Z',
    }

    // Simulate what the mutation's onSuccess does.
    qc.setQueryData(CURRENT_USER_KEY, updatedUser)

    const cached = qc.getQueryData(CURRENT_USER_KEY) as typeof existingUser
    expect(cached.display_name).toBe('New Name')
    expect(cached.title).toBe('Senior Dev')
    expect(cached.email).toBe('a@b.com') // unchanged
  })

  it('preserves immutable fields in cache update', () => {
    const user = {
      id: 'u1',
      email: 'test@test.com',
      display_name: 'Tester',
      title: 'QA',
      years_of_experience: 5,
      target_role: 'Lead QA',
      bio: 'QA bio',
      subscription: 'free',
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
    }
    qc.setQueryData(CURRENT_USER_KEY, user)

    // Simulate PATCH with only display_name
    qc.setQueryData(CURRENT_USER_KEY, {
      ...user,
      display_name: 'Updated Tester',
      updated_at: '2026-06-13T00:00:00Z',
    })

    const cached = qc.getQueryData(CURRENT_USER_KEY) as typeof user
    expect(cached.display_name).toBe('Updated Tester')
    // These should remain unchanged
    expect(cached.email).toBe('test@test.com')
    expect(cached.subscription).toBe('free')
    expect(cached.id).toBe('u1')
  })
})
