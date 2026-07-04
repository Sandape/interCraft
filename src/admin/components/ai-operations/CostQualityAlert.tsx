/**
 * CostQualityAlert — REQ-044 US3 / FR-019 + AC-19.1/19.2/19.3.
 *
 * Red banner at the top of the workspace that surfaces the
 * cost-quality tradeoff flag (cost up + quality down).
 *
 * The whole banner is clickable; clicking opens the matching
 * quality issue drawer (AC-19.3).
 */
import type { AIQualityIssue, CostQualityFlag } from '@/types/admin-ai-operations'

interface CostQualityAlertProps {
  flag: CostQualityFlag
  onOpenQualityIssue: (issue: AIQualityIssue) => void
  fallbackIssue?: AIQualityIssue | null
}

export function CostQualityAlert({
  flag,
  onOpenQualityIssue,
  fallbackIssue,
}: CostQualityAlertProps) {
  if (!flag.flagged) {
    return null
  }

  const handleClick = () => {
    if (fallbackIssue) {
      onOpenQualityIssue(fallbackIssue)
    }
  }

  return (
    <div
      className="ac-ao-alert ac-ao-alert--cost-quality ac-ao-alert--critical"
      data-testid="cost-quality-alert"
      role="alert"
      onClick={handleClick}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          handleClick()
        }
      }}
      tabIndex={0}
    >
      <div className="ac-ao-alert__severity" data-testid="alert-severity">
        {flag.severity.toUpperCase()}
      </div>
      <div
        className="ac-ao-alert__message"
        data-testid="alert-message"
      >
        {flag.message}
      </div>
      <div
        className="ac-ao-alert__linked"
        data-testid="alert-linked"
      >
        linked · model <code data-testid="alert-linked-model">{flag.linkedModel}</code>{' '}
        · prompt <code data-testid="alert-linked-prompt">{flag.linkedPrompt}</code>{' '}
        · feature <code data-testid="alert-linked-feature">{flag.linkedFeatureArea}</code>{' '}
        · cohort <code data-testid="alert-linked-cohort">{flag.linkedCohort}</code>
      </div>
    </div>
  )
}

export default CostQualityAlert
