/**
 * ConfidenceBadge — REQ-044 US1 / FR-009.
 *
 * Visual distinction for the 4 confidence tiers:
 *
 *   - confirmed:  green check
 *   - sampled:    blue circle (sampled subset)
 *   - inferred:   yellow triangle (derived, indirect)
 *   - candidate:  gray dot, explicit "low confidence" label
 *
 * Phase-2 batch-2 may add a tooltip explaining the tier; for US1 we
 * keep the surface minimal so the visual is unambiguously distinct.
 */
import type { DecisionConfidenceTier } from '@/types/admin-decision-signals'

interface ConfidenceBadgeProps {
  tier: DecisionConfidenceTier
}

const TIER_LABEL: Record<DecisionConfidenceTier, string> = {
  confirmed: 'Confirmed',
  sampled: 'Sampled',
  inferred: 'Inferred',
  candidate: 'Candidate · low confidence',
}

const TIER_GLYPH: Record<DecisionConfidenceTier, string> = {
  confirmed: '✓', // ✓
  sampled: '●', // ●
  inferred: '▲', // ▲
  candidate: '◌', // ◌
}

export function ConfidenceBadge({ tier }: ConfidenceBadgeProps) {
  return (
    <span
      className={`ds-confidence ds-confidence--${tier}`}
      data-testid={`confidence-${tier}`}
      data-confidence={tier}
      title={TIER_LABEL[tier]}
    >
      <span className="ds-confidence__glyph" aria-hidden="true">
        {TIER_GLYPH[tier]}
      </span>
      <span className="ds-confidence__label">
        {tier === 'candidate' ? 'low confidence' : tier}
      </span>
    </span>
  )
}

export default ConfidenceBadge