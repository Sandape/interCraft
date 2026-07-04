/**
 * QualityIssueDrawer — REQ-044 US3 / FR-018 + AC-18.2/18.3.
 *
 * Drawer that surfaces the 8 FR-018 link fields for a single
 * AI quality issue (eval_verdict + badcase_id + affected_feature_area
 * + affected_journey_step + owner + status + recommended_action +
 * feature_area_dimension) plus deep-links.
 *
 * The "View badcase" button links to ``badcaseDetailHref`` (US4
 * badcase detail page — the seed supplies a placeholder URL).
 */
import type { AIQualityIssue } from '@/types/admin-ai-operations'

interface QualityIssueDrawerProps {
  issue: AIQualityIssue | null
  onClose: () => void
  open: boolean
}

export function QualityIssueDrawer({
  issue,
  onClose,
  open,
}: QualityIssueDrawerProps) {
  if (!open || !issue) {
    return (
      <div
        className="ac-ao-drawer ac-ao-drawer--closed"
        data-testid="ai-operations-quality-drawer-closed"
      />
    )
  }
  return (
    <div
      className="ac-ao-drawer ac-ao-drawer--quality-issue"
      data-testid="ai-operations-quality-drawer"
      role="dialog"
      aria-label="AI quality issue detail"
    >
      <header className="ac-ao-drawer__header">
        <h3 className="ac-ao-drawer__title" data-testid="drawer-title">
          {issue.title}
        </h3>
        <button
          type="button"
          onClick={onClose}
          data-testid="drawer-close"
          aria-label="Close drawer"
        >
          ×
        </button>
      </header>

      <ul className="ac-ao-drawer__fields">
        {/* FR-018 8 link fields */}
        <li className="ac-ao-drawer__field" data-testid="drawer-field-eval-verdict">
          <span className="ac-ao-drawer__field-label">Eval verdict</span>
          <span className="ac-ao-drawer__field-value">{issue.evalVerdict}</span>
        </li>
        <li className="ac-ao-drawer__field" data-testid="drawer-field-badcase-id">
          <span className="ac-ao-drawer__field-label">Badcase ID</span>
          <span className="ac-ao-drawer__field-value">{issue.badcaseId}</span>
        </li>
        <li
          className="ac-ao-drawer__field"
          data-testid="drawer-field-affected-feature-area"
        >
          <span className="ac-ao-drawer__field-label">Affected feature area</span>
          <span className="ac-ao-drawer__field-value">
            {issue.affectedFeatureArea}
          </span>
        </li>
        <li
          className="ac-ao-drawer__field"
          data-testid="drawer-field-affected-journey-step"
        >
          <span className="ac-ao-drawer__field-label">Affected journey step</span>
          <span className="ac-ao-drawer__field-value">
            {issue.affectedJourneyStep}
          </span>
        </li>
        <li className="ac-ao-drawer__field" data-testid="drawer-field-owner">
          <span className="ac-ao-drawer__field-label">Owner</span>
          <span className="ac-ao-drawer__field-value">{issue.owner}</span>
        </li>
        <li className="ac-ao-drawer__field" data-testid="drawer-field-status">
          <span className="ac-ao-drawer__field-label">Status</span>
          <span className="ac-ao-drawer__field-value">{issue.status}</span>
        </li>
        <li
          className="ac-ao-drawer__field"
          data-testid="drawer-field-recommended-action"
        >
          <span className="ac-ao-drawer__field-label">Recommended action</span>
          <span className="ac-ao-drawer__field-value">
            {issue.recommendedAction}
          </span>
        </li>
        <li
          className="ac-ao-drawer__field"
          data-testid="drawer-field-feature-area-dimension"
        >
          <span className="ac-ao-drawer__field-label">Feature area dimension</span>
          <span className="ac-ao-drawer__field-value">
            {issue.featureAreaDimension}
          </span>
        </li>
      </ul>

      <footer className="ac-ao-drawer__footer">
        {issue.badcaseDetailHref && (
          <a
            href={issue.badcaseDetailHref}
            className="ac-ao-drawer__action"
            data-testid="drawer-view-badcase"
          >
            View badcase (US4 placeholder)
          </a>
        )}
        {issue.evalDetailHref && (
          <a
            href={issue.evalDetailHref}
            className="ac-ao-drawer__action"
            data-testid="drawer-view-eval"
          >
            View eval result
          </a>
        )}
      </footer>
    </div>
  )
}

export default QualityIssueDrawer
