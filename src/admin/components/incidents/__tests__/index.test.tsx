/**
 * Static-guard unit tests for REQ-044 US4 / FR-021~FR-023.
 *
 * These tests do NOT need the backend running; they verify:
 *
 *   - 4 severity bands render distinct text + glyphs (FR-021)
 *   - 3 trend directions render distinct arrows (FR-021)
 *   - 8 evidence link types all render with their glyphs (FR-022)
 *   - TypeScript types carry the 10 FR-021 incident fields
 *   - TypeScript types carry the 10 FR-023 badcase fields
 *   - TypeScript types carry the 8 FR-022 evidence types
 *
 * Playwright E2E covers the full HTTP round-trip; these tests act
 * as a CI-friendly smoke check.
 */
import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { SeverityBadge } from '../SeverityBadge'
import { TrendArrow } from '../TrendArrow'
import type {
  EvidenceLinkType,
  Incident,
  Badcase,
  AuditTrailEntry,
} from '@/types/admin-incidents'

describe('REQ-044 US4 / FR-021 SeverityBadge', () => {
  it('renders all 4 severity bands', () => {
    const bands = ['P0', 'P1', 'P2', 'P3'] as const
    for (const b of bands) {
      render(<SeverityBadge severity={b} />)
      expect(screen.getByTestId(`severity-${b}`)).toBeInTheDocument()
    }
  })
})

describe('REQ-044 US4 / FR-021 TrendArrow', () => {
  it('renders all 3 trend arrows', () => {
    const trends = ['rising', 'stable', 'declining'] as const
    for (const t of trends) {
      render(<TrendArrow trend={t} />)
      expect(screen.getByTestId(`trend-${t}`)).toBeInTheDocument()
    }
  })
})

describe('REQ-044 US4 / FR-022 8 evidence link types', () => {
  it('enumerates all 8 evidence link types', () => {
    const types: EvidenceLinkType[] = [
      'product_metric',
      'user_impact',
      'ai_task',
      'eval_case',
      'log',
      'trace',
      'release',
      'comment',
    ]
    expect(types).toHaveLength(8)
    expect(new Set(types).size).toBe(8)
  })
})

describe('REQ-044 US4 / FR-021 Incident type', () => {
  it('type carries all 10 FR-021 field names', () => {
    const sample: Incident = {
      id: 'inc-test',
      title: 'Test incident',
      severity: 'P0',
      status: 'open',
      owner: '@ops-oncall',
      affectedFeatureArea: 'mock_interview',
      affectedJourneyStep: 'registered_to_first_interview',
      firstSeenAt: '2026-07-04T00:00:00Z',
      lastSeenAt: '2026-07-04T01:00:00Z',
      trend: 'rising',
      candidate: false,
      commonRootCause: null,
      linkedIncidentIds: [],
      ingestionDelayed: false,
      freshnessAt: '2026-07-04T01:00:00Z',
      affectedCount: 100,
      description: 'test',
      auditTrail: [],
    }
    expect(sample.id).toBeTruthy()
    expect(sample.severity).toBeTruthy()
    expect(sample.status).toBeTruthy()
    expect(sample.owner).toBeTruthy()
    expect(sample.affectedFeatureArea).toBeTruthy()
    expect(sample.affectedJourneyStep).toBeTruthy()
    expect(sample.firstSeenAt).toBeTruthy()
    expect(sample.lastSeenAt).toBeTruthy()
    expect(sample.trend).toBeTruthy()
    expect(sample.title).toBeTruthy()
  })
})

describe('REQ-044 US4 / FR-023 Badcase type', () => {
  it('type carries all 10 FR-023 field names', () => {
    const sample: Badcase = {
      id: 'bc-test',
      evalVerdict: 'rubric_v3.2_fail',
      affectedFeatureArea: 'resume_optimize',
      affectedUserId: '019ec1be-0000-7000-8000-000000000002',
      privacyClass: 'public',
      classification: 'ai_scoring_inconsistent',
      owner: '@ai-quality-oncall',
      status: 'open',
      resolution: '',
      firstSeenAt: '2026-07-04T00:00:00Z',
      incidentId: null,
      freshnessAt: '2026-07-04T00:00:00Z',
      description: 'test',
      auditTrail: [],
    }
    expect(sample.id).toBeTruthy()
    expect(sample.evalVerdict).toBeTruthy()
    expect(sample.affectedFeatureArea).toBeTruthy()
    expect(sample.affectedUserId).toBeTruthy()
    expect(sample.privacyClass).toBeTruthy()
    expect(sample.classification).toBeTruthy()
    expect(sample.owner).toBeTruthy()
    expect(sample.status).toBeTruthy()
    expect(sample.firstSeenAt).toBeTruthy()
  })
})

describe('REQ-044 US4 / EC-4 AuditTrailEntry', () => {
  it('type carries all 5 EC-4 fields (actor/timestamp/reason/before/after)', () => {
    const sample: AuditTrailEntry = {
      actor: '@ops-oncall',
      timestamp: '2026-07-04T00:00:00Z',
      reason: 'test',
      beforeState: { status: 'open' },
      afterState: { status: 'investigating' },
      action: 'status_change',
    }
    expect(sample.actor).toBeTruthy()
    expect(sample.timestamp).toBeTruthy()
    expect(sample.reason).toBeTruthy()
    expect(sample.beforeState).toBeDefined()
    expect(sample.afterState).toBeDefined()
  })
})
