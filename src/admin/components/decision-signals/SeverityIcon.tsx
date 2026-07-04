/**
 * SeverityIcon — REQ-044 US1 / FR-008.
 *
 * Visual differentiation for the 5 severity bands:
 *
 *   - critical: filled red octagon + glow
 *   - high:     solid red diamond
 *   - medium:   solid amber square
 *   - low:      solid blue circle
 *   - info:     hollow gray circle
 */
import type { DecisionSignalSeverity } from '@/types/admin-decision-signals'

interface SeverityIconProps {
  severity: DecisionSignalSeverity
}

const SEVERITY_GLYPH: Record<DecisionSignalSeverity, string> = {
  critical: '⬢', // hex stop sign
  high: '◆', // diamond
  medium: '■', // square
  low: '●', // circle
  info: '○', // hollow circle
}

const SEVERITY_LABEL: Record<DecisionSignalSeverity, string> = {
  critical: 'Critical',
  high: 'High',
  medium: 'Medium',
  low: 'Low',
  info: 'Info',
}

export function SeverityIcon({ severity }: SeverityIconProps) {
  return (
    <span
      className={`ds-severity ds-severity--${severity}`}
      data-testid={`severity-${severity}`}
      data-severity={severity}
      title={`Severity: ${SEVERITY_LABEL[severity]}`}
      aria-label={`Severity ${SEVERITY_LABEL[severity]}`}
    >
      <span className="ds-severity__glyph" aria-hidden="true">
        {SEVERITY_GLYPH[severity]}
      </span>
    </span>
  )
}

export default SeverityIcon