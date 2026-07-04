/**
 * SeverityBadge — REQ-044 US4 / FR-021.
 *
 * Visual differentiation for the 4 incident severity bands:
 *
 *   - P0: filled red — most urgent
 *   - P1: solid red — significant
 *   - P2: solid amber — partial
 *   - P3: solid blue — minor
 */
import type { IncidentSeverity } from '@/types/admin-incidents'

interface SeverityBadgeProps {
  severity: IncidentSeverity
}

const SEVERITY_LABEL: Record<IncidentSeverity, string> = {
  P0: 'P0 · Critical',
  P1: 'P1 · High',
  P2: 'P2 · Medium',
  P3: 'P3 · Low',
}

const SEVERITY_GLYPH: Record<IncidentSeverity, string> = {
  P0: '⛔',
  P1: '◆',
  P2: '■',
  P3: '●',
}

export function SeverityBadge({ severity }: SeverityBadgeProps) {
  return (
    <span
      className={`ic-severity ic-severity--${severity}`}
      data-testid={`severity-${severity}`}
      data-severity={severity}
      title={SEVERITY_LABEL[severity]}
      aria-label={`Severity ${SEVERITY_LABEL[severity]}`}
    >
      <span className="ic-severity__glyph" aria-hidden="true">
        {SEVERITY_GLYPH[severity]}
      </span>
      <span className="ic-severity__label">{severity}</span>
    </span>
  )
}

export default SeverityBadge
