/**
 * REQ-061 T142 — AIReleaseGovernance soft structure tests.
 */
import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { AIReleaseGovernance } from '../AIReleaseGovernance'

describe('AIReleaseGovernance page structure', () => {
  it('renders candidate/stable comparison and gate evidence sections', () => {
    render(<AIReleaseGovernance />)

    expect(screen.getByTestId('ai-release-governance')).toBeInTheDocument()
    expect(screen.getByTestId('release-candidate-stable')).toBeInTheDocument()
    expect(screen.getByTestId('release-gate-evidence')).toBeInTheDocument()
    expect(screen.getByTestId('release-cohort-status')).toBeInTheDocument()
    expect(screen.getByTestId('release-stop-reason')).toBeInTheDocument()
    expect(screen.getByTestId('release-rollback-target')).toBeInTheDocument()
    expect(screen.getByTestId('release-override-audit')).toBeInTheDocument()
  })
})
