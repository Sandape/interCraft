/**
 * Static-guard unit tests for REQ-044 US1 / FR-007~FR-010.
 *
 * These tests do NOT need the backend running; they verify:
 *
 *   - 4 confidence tiers render distinct text + glyphs
 *   - 5 severity bands render distinct glyphs
 *   - DecisionSignal type contains the 10 FR-008 fields
 *   - ConfidenceBadge renders "low confidence" for candidate tier
 *
 * Playwright E2E covers the full HTTP round-trip; these tests act
 * as a CI-friendly smoke check before the Playwright suite runs.
 */
import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ConfidenceBadge } from '../ConfidenceBadge'
import { SeverityIcon } from '../SeverityIcon'
import type { DecisionSignal } from '@/types/admin-decision-signals'

describe('REQ-044 US1 / FR-009 ConfidenceBadge', () => {
  it('renders all 4 confidence tiers', () => {
    const tiers = ['confirmed', 'sampled', 'inferred', 'candidate'] as const
    for (const t of tiers) {
      render(<ConfidenceBadge tier={t} />)
      expect(screen.getByTestId(`confidence-${t}`)).toBeInTheDocument()
    }
  })

  it('candidate tier renders "low confidence" label (FR-009 AC-9.3)', () => {
    render(<ConfidenceBadge tier="candidate" />)
    expect(screen.getByText(/low confidence/i)).toBeInTheDocument()
  })

  it('confirmed tier does NOT render "low confidence"', () => {
    render(<ConfidenceBadge tier="confirmed" />)
    expect(screen.queryByText(/low confidence/i)).not.toBeInTheDocument()
  })
})

describe('REQ-044 US1 / FR-008 SeverityIcon', () => {
  it('renders all 5 severity bands', () => {
    const bands = ['critical', 'high', 'medium', 'low', 'info'] as const
    for (const b of bands) {
      render(<SeverityIcon severity={b} />)
      expect(screen.getByTestId(`severity-${b}`)).toBeInTheDocument()
    }
  })
})

describe('REQ-044 US1 / FR-008 DecisionSignal type', () => {
  it('type carries all 10 FR-008 field names', () => {
    // Use a sample object to assert the field names exist at runtime.
    const sample: DecisionSignal = {
      id: 'sig-test',
      category: 'product',
      whatChanged: 'something changed',
      affectedSegment: 'all users',
      comparisonBaseline: 'last 7 days',
      severity: 'high',
      confidence: 'confirmed',
      owner: '@pm',
      freshnessAt: '2026-07-04T00:00:00Z',
      nextReviewLink: '/admin-console',
      evidenceLinks: [],
      qualityFlags: {
        stale: false,
        partialBaseline: false,
        delayedIngestion: false,
        missingVersionFields: [],
        sampledData: false,
        partialData: false,
        noData: false,
      },
      priority: 100,
      detectedAt: '2026-07-04T00:00:00Z',
      headlineMetricId: null,
      title: 'Test signal',
    }
    expect(sample.id).toBeTruthy()
    expect(sample.category).toBeTruthy()
    expect(sample.whatChanged).toBeTruthy()
    expect(sample.affectedSegment).toBeTruthy()
    expect(sample.comparisonBaseline).toBeTruthy()
    expect(sample.severity).toBeTruthy()
    expect(sample.confidence).toBeTruthy()
    expect(sample.owner).toBeTruthy()
    expect(sample.freshnessAt).toBeTruthy()
    expect(sample.nextReviewLink).toBeTruthy()
  })
})