/* 020 (FIX-009, D-016) — Protected routes must redirect unauthenticated
   visitors to /login.

Round-1 evidence: `/jobs`, `/resumes`, `/error-book`, `/interview`,
`/profile` did not redirect. The AuthGuard wrapper used
  `!hasTokens() && status === 'unknown'`
which let through the case where `hasTokens()` was true but the token was
stale (401 → React Query spins forever).

The fix:
  - Extract a pure `requireAuth({ hasTokens, status })` decision into
    `src/lib/requireAuth.ts` so the routing logic is testable.
  - App.tsx's `AuthGuard` uses the function and renders a neutral loading
    state while `status === 'unknown'` so the protected page never mounts
    until the user is confirmed.
*/
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'

// jsdom polyfills — ThemeProvider + useCurrentUser + ResumeEditor transitively
// touch browser APIs that jsdom does not provide.
if (typeof window !== 'undefined' && !window.matchMedia) {
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
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { ThemeProvider } from '@/contexts/ThemeContext'
import { requireAuth } from '@/lib/requireAuth'
import { AppRoutes } from '@/App'

vi.mock('@/api/token-storage', () => ({
  hasTokens: vi.fn(() => false),
  setTokens: vi.fn(),
  clearTokens: vi.fn(),
  getAccessToken: vi.fn(() => null),
  getRefreshToken: vi.fn(() => null),
}))

vi.mock('@monaco-editor/react', () => ({
  default: () => null,
  Editor: () => null,
}))

// Heavy page mocks to avoid pulling monaco-editor into the jsdom env.
vi.mock('@/components/resume/editor/MarkdownEditor', () => ({
  MarkdownEditor: () => null,
}))
vi.mock('@/pages/ResumeEditor', () => ({ default: () => null }))
vi.mock('@/pages/ResumeList', () => ({ default: () => null }))
vi.mock('@/pages/Jobs', () => ({ default: () => null }))
vi.mock('@/pages/ErrorBook', () => ({ default: () => null }))
vi.mock('@/pages/InterviewList', () => ({ default: () => null }))
vi.mock('@/pages/InterviewLive', () => ({ default: () => null }))
vi.mock('@/pages/InterviewReport', () => ({ default: () => null }))
vi.mock('@/pages/Dashboard', () => ({ default: () => null }))
vi.mock('@/pages/Profile', () => ({ default: () => null }))
vi.mock('@/pages/Settings', () => ({ default: () => null }))
vi.mock('@/pages/GeneralCoach', () => ({ default: () => null }))
vi.mock('@/pages/Help', () => ({ default: () => null }))
vi.mock('@/pages/AbilityProfile', () => ({ default: () => null }))
vi.mock('@/pages/AbilityProfileDetail', () => ({ default: () => null }))
vi.mock('@/pages/SharedAbilityProfile', () => ({ default: () => null }))
vi.mock('@/components/layout/AppShell', () => ({ AppShell: ({ children }: { children: React.ReactNode }) => <>{children}</> }))

vi.mock('@/hooks/queries/useCurrentUser', () => ({
  useCurrentUser: () => ({ data: null, isLoading: false, error: null }),
}))

function renderAppAt(initialEntry: string) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <ThemeProvider>
      <QueryClientProvider client={qc}>
        <MemoryRouter initialEntries={[initialEntry]}>
          <Routes>
            <Route path="/*" element={<AppRoutes />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    </ThemeProvider>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  sessionStorage.clear()
})

describe('requireAuth — pure decision function (020 D-016)', () => {
  it('redirects to /login when no tokens and status unknown', () => {
    const result = requireAuth({ hasTokens: false, status: 'unknown' })
    expect(result.kind).toBe('redirect')
    if (result.kind === 'redirect') {
      expect(result.to).toBe('/login')
    }
  })

  it('redirects to /login when no tokens and status unauthenticated', () => {
    const result = requireAuth({ hasTokens: false, status: 'unauthenticated' })
    expect(result.kind).toBe('redirect')
  })

  it('returns loading when status is unknown but tokens present (stale token check pending)', () => {
    const result = requireAuth({ hasTokens: true, status: 'unknown' })
    expect(result.kind).toBe('loading')
  })

  it('returns ok when authenticated', () => {
    const result = requireAuth({ hasTokens: true, status: 'authenticated' })
    expect(result.kind).toBe('ok')
  })

  it('redirects when status is unauthenticated regardless of tokens', () => {
    const result = requireAuth({ hasTokens: true, status: 'unauthenticated' })
    expect(result.kind).toBe('redirect')
  })
})

describe('AppRoutes — integration auth guard (020 D-016)', () => {
  it('redirects /jobs to /login when no tokens are present', async () => {
    const { hasTokens } = await import('@/api/token-storage')
    ;(hasTokens as ReturnType<typeof vi.fn>).mockReturnValue(false)
    renderAppAt('/jobs')
    await waitFor(() => {
      // The Login page renders an "Sign in" / "登录" heading or button
      expect(screen.queryByText(/登录|sign in/i)).toBeInTheDocument()
    }, { timeout: 1000 })
  })

  it('redirects /error-book to /login when no tokens are present', async () => {
    const { hasTokens } = await import('@/api/token-storage')
    ;(hasTokens as ReturnType<typeof vi.fn>).mockReturnValue(false)
    renderAppAt('/error-book')
    await waitFor(() => {
      expect(screen.queryByText(/登录|sign in/i)).toBeInTheDocument()
    }, { timeout: 1000 })
  })
})
