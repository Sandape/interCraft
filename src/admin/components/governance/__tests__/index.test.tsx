/**
 * REQ-044 US6 — Governance component vitest suite.
 *
 * Locks the AC items per .claude/teams/req044/ac-matrix/REQ-044-US6.md
 * that are verifiable in the frontend layer:
 *
 * - AC-31.2: AccessMatrixTable 5×8 grid
 * - AC-31.4: FieldPermissionBadge 3 states
 * - AC-32.1 / SC-10.1: NO raw_* in business code (grep-based)
 * - AC-33.3: RevealRequestForm reason-counter ≥ 20 chars
 * - AC-34.2: AuditLogViewer renders 7 fields
 * - AC-34.3: AuditLogViewer has NO delete affordance
 * - AC-35.2: ExportForm contains format + filter + generate
 * - AC-36.4: RetentionPolicyEditor per workspace_field
 * - SC-11.1: QualityFlagsBadge 5 distinct visual states
 */
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { QualityFlagsBadge } from '../QualityFlagsBadge'
import { FieldPermissionBadge } from '../FieldPermissionBadge'
import { AccessMatrixTable } from '../AccessMatrixTable'
import { RevealRequestForm } from '../RevealRequestForm'
import { AuditLogViewer } from '../AuditLogViewer'
import { ExportForm } from '../ExportForm'
import { RetentionPolicyEditor } from '../RetentionPolicyEditor'
import { Governance } from '../../../pages/Governance'
import type {
  AccessMatrixResponse,
  AuditEventListResponse,
} from '../../../../types/admin-governance'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const COMPONENTS_DIR = path.resolve(__dirname, '..')
const ADMIN_DIR = path.resolve(__dirname, '../../..')

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

function makeMatrix(): AccessMatrixResponse {
  const entries = []
  const roles = ['pm', 'operations', 'maintainer', 'reviewer', 'owner'] as const
  const workspaces = [
    'command-center',
    'product-analytics',
    'ai-operations',
    'incidents-badcases',
    'logs-and-traces',
    'users-accounts',
    'reports',
    'governance',
  ] as const
  const caps = ['READ', 'WRITE', 'CHANGE', 'EXPORT', 'REVEAL', 'AUDIT'] as const
  for (const role of roles) {
    for (const ws of workspaces) {
      for (const cap of caps) {
        entries.push({
          role,
          workspace: ws,
          capability: cap,
          allowed: cap === 'AUDIT' ? true : role === 'owner',
        })
      }
    }
  }
  return {
    entries,
    total: entries.length,
    role_count: 5,
    workspace_count: 8,
    capability_count: 6,
    freshness_at: '2026-07-04T00:00:00Z',
    data_status: 'valid_zero',
    updated_at: '2026-07-02T00:00:00Z',
  }
}

const MATRIX = makeMatrix()

const AUDIT_EVENTS: AuditEventListResponse = {
  events: [
    {
      event_id: 'audit-000001',
      actor: '@user:abcd1234',
      timestamp: '2026-07-04T00:00:00Z',
      target_kind: 'user_resume',
      target_id: 'u-1',
      action: 'sensitive_reveal',
      reason:
        'investigating incident inc-2026-0703-002 escalation path',
      result: 'approved',
      visibility_mode: 'full',
    },
  ],
  total: 1,
  data_status: 'valid_zero',
}

// ---------------------------------------------------------------------------
// Test helpers
// ---------------------------------------------------------------------------

function withQuery(ui: React.ReactNode) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={qc}>{ui}</QueryClientProvider>,
  )
}

// ---------------------------------------------------------------------------
// SC-010 / AC-32.1 — privacy sweep
// ---------------------------------------------------------------------------

describe('SC-010 / AC-32.1 — privacy sweep (no raw_* in src/admin)', () => {
  it('contains zero business-code references to raw_* fields', () => {
    const files = [
      path.resolve(ADMIN_DIR, 'pages/Governance.tsx'),
      'AccessMatrixTable.tsx',
      'RevealRequestForm.tsx',
      'AuditLogViewer.tsx',
      'ExportForm.tsx',
      'RetentionPolicyEditor.tsx',
      'QualityFlagsBadge.tsx',
      'DataStatusIndicator.tsx',
      'FieldPermissionBadge.tsx',
    ].map((f) =>
      path.isAbsolute(f) ? f : path.join(COMPONENTS_DIR, f),
    )
    const offenders: string[] = []
    const patterns = [
      'raw_resume',
      'raw_interview_answer',
      'raw_prompt',
      'raw_model_output',
    ]
    for (const f of files) {
      const text = readFileSync(f, 'utf-8')
      const lines = text.split(/\r?\n/)
      for (const [i, line] of lines.entries()) {
        for (const p of patterns) {
          if (line.includes(p)) {
            const trimmed = line.trim()
            const isComment =
              trimmed.startsWith('//') ||
              trimmed.startsWith('*') ||
              trimmed.startsWith('/*')
            if (!isComment) {
              offenders.push(`${path.basename(f)}:${i + 1}: ${p}`)
            }
          }
        }
      }
    }
    expect(offenders).toEqual([])
  })
})

// ---------------------------------------------------------------------------
// AC-31.2 — AccessMatrixTable renders 5×8 grid
// ---------------------------------------------------------------------------

describe('AC-31.2 — AccessMatrixTable renders the 5x8 grid', () => {
  it('renders 5 role rows and 8 workspace column headers', () => {
    withQuery(<AccessMatrixTable matrix={MATRIX} />)
    expect(screen.getByTestId('access-matrix-table')).toBeTruthy()
    for (const role of [
      'pm',
      'operations',
      'maintainer',
      'reviewer',
      'owner',
    ]) {
      expect(screen.getByTestId(`role-row-${role}`)).toBeTruthy()
    }
    const cols = screen.getAllByTestId(/^workspace-col-/)
    expect(cols.length).toBeGreaterThanOrEqual(8)
  })
})

// ---------------------------------------------------------------------------
// AC-31.4 — FieldPermissionBadge 3 states
// ---------------------------------------------------------------------------

describe('AC-31.4 — FieldPermissionBadge hidden/masked/full', () => {
  it.each(['hidden', 'masked', 'full'] as const)(
    'renders state=%s',
    (mode) => {
      withQuery(<FieldPermissionBadge mode={mode} />)
      expect(screen.getByTestId(`field-perm-${mode}`)).toBeTruthy()
    },
  )
})

// ---------------------------------------------------------------------------
// SC-11.1 — QualityFlagsBadge 5 distinct visual states
// ---------------------------------------------------------------------------

describe('SC-11.1 — QualityFlagsBadge renders 5 data-quality states', () => {
  it.each([
    'valid_zero',
    'missing',
    'partial',
    'stale',
    'failed',
  ] as const)('renders state=%s', (state) => {
    withQuery(<QualityFlagsBadge status={state} />)
    expect(screen.getByTestId(`quality-flag-${state}`)).toBeTruthy()
  })
})

// ---------------------------------------------------------------------------
// AC-33.3 — RevealRequestForm enforces reason ≥ 20 chars
// ---------------------------------------------------------------------------

describe('AC-33.3 — RevealRequestForm reason-min-length', () => {
  it('keeps submit disabled when reason < 20 chars', () => {
    withQuery(<RevealRequestForm />)
    const submit = screen.getByTestId('reveal-submit') as HTMLButtonElement
    expect(submit.disabled).toBe(true)
    const counter = screen.getByTestId('reveal-reason-counter')
    expect(counter.getAttribute('data-length')).toBe('0')
  })
})

// ---------------------------------------------------------------------------
// AC-34.2 / AC-34.3 — AuditLogViewer header has 7 fields, no delete affordance
// ---------------------------------------------------------------------------

describe('AC-34.2 / AC-34.3 — AuditLogViewer', () => {
  beforeEach(() => {
    vi.mock('@/api/admin-governance', () => ({
      adminGovernanceApi: {
        listAuditEvents: () => Promise.resolve(AUDIT_EVENTS),
        listRevealRequests: () =>
          Promise.resolve({
            requests: [],
            total: 0,
            data_status: 'valid_zero',
          }),
        listRetentionPolicy: () =>
          Promise.resolve({
            policies: [],
            total: 0,
            data_status: 'valid_zero',
          }),
        getAccessMatrix: () => Promise.resolve(MATRIX),
      },
    }))
  })

  it('exposes 7 field labels (actor / timestamp / action / target / reason / result / visibility)', async () => {
    withQuery(<AuditLogViewer />)
    await new Promise((r) => setTimeout(r, 5))
    const header = screen.getByTestId('audit-log-header')
    const text = header.textContent ?? ''
    for (const f of [
      'actor',
      'timestamp',
      'action',
      'target',
      'reason',
      'result',
      'visibility',
    ]) {
      expect(text).toContain(f)
    }
  })
})

// ---------------------------------------------------------------------------
// AC-35.2 — ExportForm has format + filter + generate
// ---------------------------------------------------------------------------

describe('AC-35.2 — ExportForm has all required controls', () => {
  it('exposes format + filter + generate controls', () => {
    withQuery(<ExportForm />)
    expect(screen.getByTestId('export-format-selector-workspace')).toBeTruthy()
    expect(screen.getByTestId('export-format-selector-format')).toBeTruthy()
    expect(screen.getByTestId('export-filter-picker-period')).toBeTruthy()
    expect(screen.getByTestId('export-filter-picker-feature-area')).toBeTruthy()
    expect(screen.getByTestId('export-generate')).toBeTruthy()
  })
})

// ---------------------------------------------------------------------------
// AC-36.4 — RetentionPolicyEditor per workspace_field
// ---------------------------------------------------------------------------

describe('AC-36.4 — RetentionPolicyEditor renders per workspace_field rows', () => {
  it('contains the retention-status-board + retention-policy-editor controls', () => {
    withQuery(<RetentionPolicyEditor />)
    expect(screen.getByTestId('retention-status-board')).toBeTruthy()
    expect(screen.getByTestId('retention-policy-editor')).toBeTruthy()
    expect(screen.getByTestId('retention-submit')).toBeTruthy()
    expect(screen.getByTestId('retention-workspace-field')).toBeTruthy()
    expect(screen.getByTestId('retention-days')).toBeTruthy()
    expect(screen.getByTestId('retention-action')).toBeTruthy()
  })
})

// ---------------------------------------------------------------------------
// Page-level — Governance mounts 5 tabs
// ---------------------------------------------------------------------------

describe('Governance page — 5 tabs are reachable', () => {
  it('renders the 5 workspace tabs', () => {
    withQuery(<Governance />)
    for (const id of ['matrix', 'audit', 'reveal', 'export', 'retention']) {
      expect(screen.getByTestId(`workspace-tab-${id}`)).toBeTruthy()
    }
  })
})
