/* 020 (FIX-008, D-009) — ErrorBook page must have a source filter UI
   and a per-row source badge.

Round-1 evidence: backend `?source=auto|manual|all` filter works (T5),
but `src/pages/ErrorBook.tsx` lacks:
  1. A `data-testid="error-source-filter"` segmented control
     (全部 / 来自面试 / 手动录入).
  2. A per-row `data-testid="error-source-badge"` for sourced items.

This test asserts the fix by:
  - rendering the page with 2 mock items (one with source_question_id,
    one without);
  - clicking each filter tab and asserting the visible rows.
*/
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import ErrorBook from '@/pages/ErrorBook'
import type { ErrorQuestion } from '@/repositories/ErrorQuestionRepository'

vi.mock('@/components/lock/OfflineBanner', () => ({
  OfflineBanner: () => null,
}))

vi.mock('@/hooks/mutations/useErrorQuestionMutations', () => ({
  useCreateErrorQuestion: () => ({ mutate: vi.fn(), isPending: false, error: null }),
  useArchiveErrorQuestion: () => ({ mutate: vi.fn(), isPending: false }),
  useRecallErrorQuestion: () => ({ mutate: vi.fn(), isPending: false }),
  useResetErrorQuestion: () => ({ mutate: vi.fn(), isPending: false }),
  useClearErrorQuestionSource: () => ({ mutate: vi.fn(), isPending: false }),
}))

const sourcedItem: ErrorQuestion = {
  id: 'eq-sourced',
  source_session_id: 'sess-1',
  source_question_id: 'q-1',
  dimension: 'algorithm',
  question_text: 'from interview',
  answer_text: null,
  reference_answer_md: null,
  status: 'fresh',
  frequency: 3,
  score: null,
  tags: null,
  archived_at: null,
  last_practiced_at: null,
  created_at: '2026-06-17T00:00:00Z',
  updated_at: '2026-06-17T00:00:00Z',
}

const manualItem: ErrorQuestion = {
  id: 'eq-manual',
  source_session_id: null,
  source_question_id: null,
  dimension: 'algorithm',
  question_text: 'manually added',
  answer_text: null,
  reference_answer_md: null,
  status: 'fresh',
  frequency: 3,
  score: null,
  tags: null,
  archived_at: null,
  last_practiced_at: null,
  created_at: '2026-06-17T00:00:00Z',
  updated_at: '2026-06-17T00:00:00Z',
}

const setupMocks = (allItems: ErrorQuestion[]) => {
  vi.doMock('@/hooks/queries/useErrorQuestions', () => ({
    useErrorQuestions: (params?: { source?: string }) => {
      const filtered = params?.source === 'auto'
        ? allItems.filter((i) => i.source_question_id != null)
        : params?.source === 'manual'
        ? allItems.filter((i) => i.source_question_id == null)
        : allItems
      return {
        data: { data: filtered, next_cursor: null, has_more: false },
        isLoading: false,
        error: null,
      }
    },
  }))
}

function renderWithProviders() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <ErrorBook />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  vi.resetModules()
  vi.clearAllMocks()
})

describe('ErrorBook page — source filter UI (020 D-009)', () => {
  it('renders the source filter segmented control', async () => {
    setupMocks([sourcedItem, manualItem])
    const { default: ErrorBookFresh } = await import('@/pages/ErrorBook')
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={qc}>
        <MemoryRouter>
          <ErrorBookFresh />
        </MemoryRouter>
      </QueryClientProvider>,
    )
    expect(screen.getByTestId('error-source-filter')).toBeInTheDocument()
  })

  it('shows a per-row source badge for sourced items', async () => {
    setupMocks([sourcedItem, manualItem])
    const { default: ErrorBookFresh } = await import('@/pages/ErrorBook')
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={qc}>
        <MemoryRouter>
          <ErrorBookFresh />
        </MemoryRouter>
      </QueryClientProvider>,
    )
    const row = screen.getByTestId('error-question-eq-sourced')
    expect(within(row).getByTestId('error-source-badge')).toBeInTheDocument()
    // Manual item row should NOT have a source badge
    const manualRow = screen.getByTestId('error-question-eq-manual')
    expect(within(manualRow).queryByTestId('error-source-badge')).not.toBeInTheDocument()
  })

  it('source filter "来自面试" shows only sourced items', async () => {
    setupMocks([sourcedItem, manualItem])
    const { default: ErrorBookFresh } = await import('@/pages/ErrorBook')
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={qc}>
        <MemoryRouter>
          <ErrorBookFresh />
        </MemoryRouter>
      </QueryClientProvider>,
    )
    const filter = screen.getByTestId('error-source-filter')
    fireEvent.click(within(filter).getByTestId('error-source-filter-auto'))
    expect(screen.getByTestId('error-question-eq-sourced')).toBeInTheDocument()
    expect(screen.queryByTestId('error-question-eq-manual')).not.toBeInTheDocument()
  })

  it('source filter "手动录入" shows only manual items', async () => {
    setupMocks([sourcedItem, manualItem])
    const { default: ErrorBookFresh } = await import('@/pages/ErrorBook')
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={qc}>
        <MemoryRouter>
          <ErrorBookFresh />
        </MemoryRouter>
      </QueryClientProvider>,
    )
    const filter = screen.getByTestId('error-source-filter')
    fireEvent.click(within(filter).getByTestId('error-source-filter-manual'))
    expect(screen.queryByTestId('error-question-eq-sourced')).not.toBeInTheDocument()
    expect(screen.getByTestId('error-question-eq-manual')).toBeInTheDocument()
  })
})
