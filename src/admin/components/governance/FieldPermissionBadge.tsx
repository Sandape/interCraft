/**
 * FieldPermissionBadge — REQ-044 FR-031 (field-level RBAC).
 *
 * 3-state field-level permission badge:
 * - hidden: field is not rendered in the response
 * - masked: field is rendered but value replaced by '***REDACTED***'
 * - full:   field is rendered as-is (REVEAL-grant required)
 */
import type { VisibilityMode } from '@/types/admin-governance'

interface Props {
  mode: VisibilityMode
  fieldName?: string
  'data-testid'?: string
}

const LABELS: Record<VisibilityMode, string> = {
  hidden: 'hidden',
  masked: 'masked',
  full: 'full',
}

export function FieldPermissionBadge({
  mode,
  fieldName,
  'data-testid': testId,
}: Props) {
  return (
    <span
      className={`ac-field-perm ac-field-perm--${mode}`}
      data-testid={testId ?? `field-perm-${mode}`}
      data-visibility-mode={mode}
      data-field-name={fieldName}
      aria-label={`visibility ${LABELS[mode]}${fieldName ? ` for ${fieldName}` : ''}`}
    >
      {LABELS[mode]}
    </span>
  )
}

export default FieldPermissionBadge
