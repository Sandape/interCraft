/**
 * REQ-044 CROSS + REQ-051 — Saved Views vitest suite.
 *
 * REQ-051: ConsoleRole union removed, role model simplified to is_admin boolean.
 * Old AC-2.3(role-aware matrix), AC-2.4(RoleBadgeDropdown), AC-2.5(ConsoleRole)
 * tests have been removed.
 *
 * Retained:
 * - AC-6.8: savedViewRepository 5 methods do NOT throw NotImplementedError.
 * - AC-6.9: SavedViewsPanel renders list + apply/edit/delete buttons.
 * - AC-6.10: SavedViewsPanel renders whatever subset the backend returns.
 * - AC-6.11: SaveCurrentViewButton captures current filter state.
 * - SC-010 / privacy sweep: NO raw_* in saved-views frontend code.
 */
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { SavedViewsPanel } from '../../SavedViewsPanel'
import { SaveCurrentViewButton } from '../../SaveCurrentViewButton'
import { HttpSavedViewRepository } from '../../../../repositories/savedViewRepository'
import type { SavedView } from '../../../../types/admin-console'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const ADMIN_DIR = path.resolve(__dirname, '../../..')

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

function makeView(overrides: Partial<SavedView> = {}): SavedView {
  return {
    id: 'sv-test-001',
    name: 'PM 默认 test view',
    filters: { since: '7d' },
    owner: '@user:test',
    description: 'cross test view',
    trustStatus: 'verified',
    workspace_id: 'command-center',
    owner_user_id: '019ec1be-0000-0000-0000-000000000001',
    shared_with: ['admin'],
    version: 1,
    warnings: [],
    ...overrides,
  }
}

function withQuery(ui: React.ReactNode) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={qc}>{ui}</QueryClientProvider>,
  )
}

// Mock the API client so we don't need a live backend.
vi.mock('../../../../api/client', () => ({
  apiClient: {
    request: vi.fn(async (opts: { method: string; path: string; body?: unknown; query?: Record<string, string> }) => {
      if (opts.method === 'GET' && opts.path === '/api/v1/admin-console/saved-views') {
        return {
          views: [
            makeView({ id: 'sv-001', name: 'Default PM view' }),
            makeView({
              id: 'sv-002',
              name: 'Operations triage',
              shared_with: ['admin'],
              warnings: ['permission revoked — shared_with no longer includes your role'],
            }),
          ],
          total: 2,
          workspace_id: opts.query?.workspace_id ?? 'command-center',
          role_view: 'admin',
          warnings: [],
        }
      }
      if (opts.method === 'POST') {
        return { view: makeView({ id: 'sv-003' }), audit_event_id: 'audit-001' }
      }
      if (opts.method === 'PATCH') {
        return makeView({ ...(opts.body as Partial<SavedView>), id: 'sv-001' })
      }
      if (opts.method === 'DELETE') {
        return undefined
      }
      if (opts.method === 'GET' && opts.path.startsWith('/api/v1/admin-console/saved-views/')) {
        return {
          view: makeView({ id: opts.path.split('/').pop() ?? 'sv-001' }),
          permission_revoked: false,
          warnings: [],
        }
      }
      return null
    }),
  },
}))

// ---------------------------------------------------------------------------
// AC-6.8 — savedViewRepository 5 methods do NOT throw NotImplementedError
// ---------------------------------------------------------------------------

describe('AC-6.8 savedViewRepository real implementation', () => {
  it('does NOT throw NotImplementedError on any of the 5 methods', async () => {
    const repo = new HttpSavedViewRepository()

    // list
    await expect(repo.list('command-center')).resolves.toBeDefined()
    // get
    await expect(repo.get('sv-001')).resolves.toBeDefined()
    // create
    await expect(
      repo.create('command-center', {
        name: 'test',
        filters: {},
        owner: '@user:t',
        description: '',
        trustStatus: 'verified',
      }),
    ).resolves.toBeDefined()
    // update
    await expect(
      repo.update('sv-001', { name: 'renamed' }),
    ).resolves.toBeDefined()
    // delete
    await expect(repo.delete('sv-001')).resolves.toBeUndefined()
  })

  it('keeps the legacy trustStatus mapping (verified → trusted)', async () => {
    const repo = new HttpSavedViewRepository()
    const resp = await repo.list('command-center')
    expect(resp.views.length).toBeGreaterThan(0)
    // 'verified' from backend → 'trusted' for legacy callers.
    expect(resp.views[0].trustStatus).toBe('trusted')
  })
})

// ---------------------------------------------------------------------------
// AC-6.9 — SavedViewsPanel renders list + 3 action buttons
// ---------------------------------------------------------------------------

describe('AC-6.9 SavedViewsPanel renders list + apply/edit/delete', () => {
  it('renders the saved-views list with 3 action buttons per row', async () => {
    withQuery(<SavedViewsPanel workspaceId="command-center" />)
    await waitFor(() => {
      expect(screen.getAllByTestId('saved-views-row').length).toBeGreaterThan(
        0,
      )
    })
    const rows = screen.getAllByTestId('saved-views-row')
    expect(rows.length).toBe(2)
    expect(screen.getAllByTestId('saved-views-apply').length).toBe(2)
    expect(screen.getAllByTestId('saved-views-edit').length).toBe(2)
    expect(screen.getAllByTestId('saved-views-delete').length).toBe(2)
  })

  it('shows the warning banner for views with warnings', async () => {
    withQuery(<SavedViewsPanel workspaceId="command-center" />)
    await waitFor(() => {
      expect(
        screen.getByText(/permission revoked/),
      ).toBeInTheDocument()
    })
  })
})

// ---------------------------------------------------------------------------
// AC-6.10 — SavedViewsPanel renders whatever subset the backend returns
// ---------------------------------------------------------------------------

describe('AC-6.10 SavedViewsPanel renders whatever subset the backend returns', () => {
  it('renders 0 views when backend returns empty list', async () => {
    const { apiClient } = await import('../../../../api/client')
    ;(apiClient.request as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      views: [],
      total: 0,
      workspace_id: 'command-center',
      role_view: 'admin',
      warnings: [],
    })

    withQuery(<SavedViewsPanel workspaceId="command-center" />)
    await waitFor(() => {
      expect(screen.getByTestId('saved-views-empty')).toBeInTheDocument()
    })
  })
})

// ---------------------------------------------------------------------------
// AC-6.11 — SaveCurrentViewButton captures current filter state
// ---------------------------------------------------------------------------

describe('AC-6.11 SaveCurrentViewButton triggers POST with current filter state', () => {
  it('expands form on click + submits POST with name + filters', async () => {
    const filters = { since: '7d', cohort: 'all-active' }
    withQuery(
      <SaveCurrentViewButton
        workspaceId="command-center"
        currentFilters={filters}
      />,
    )
    expect(
      screen.getByTestId('save-current-view-button'),
    ).toBeInTheDocument()
    fireEvent.click(screen.getByTestId('save-current-view-button'))
    expect(
      screen.getByTestId('save-current-view-form'),
    ).toBeInTheDocument()
    fireEvent.change(screen.getByTestId('save-current-view-name'), {
      target: { value: '我的 saved view' },
    })
    fireEvent.click(screen.getByTestId('save-current-view-submit'))
    await waitFor(() => {
      expect(
        screen.queryByTestId('save-current-view-form'),
      ).not.toBeInTheDocument()
    })
  })
})

// ---------------------------------------------------------------------------
// SC-010 — Privacy sweep: NO raw_* in the new saved_views frontend code
// ---------------------------------------------------------------------------

describe('SC-010 / privacy sweep (no raw_* in saved_views frontend)', () => {
  it('contains zero references to raw_* in savedViewRepository / SavedViewsPanel / SaveCurrentViewButton', () => {
    const root = path.resolve(ADMIN_DIR, '../..')
    const files = [
      path.join(root, 'src/repositories/savedViewRepository.ts'),
      path.join(root, 'src/admin/components/SavedViewsPanel.tsx'),
      path.join(root, 'src/admin/components/SaveCurrentViewButton.tsx'),
      path.join(root, 'src/admin/hooks/queries/useSavedViews.ts'),
      path.join(root, 'src/api/admin-saved-views.ts'),
    ]
    for (const f of files) {
      const src = readFileSync(f, 'utf-8')
      expect(src).not.toMatch(/raw_resume|raw_interview|raw_prompt|raw_model_output/)
    }
  })
})
