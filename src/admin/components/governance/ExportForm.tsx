/**
 * ExportForm — REQ-044 FR-035 / AC-35.2.
 *
 * Form for generating a workspace export:
 * - workspace: target workspace (8 stable names).
 * - format: json / csv / markdown.
 * - filters: free-form key/value pairs (period, feature_area, ...).
 *
 * On submit, calls the export API and shows:
 * - fields_included (allowed whitelist)
 * - fields_redacted (raw_* never leaked)
 * - freshness_warnings (when period overlaps stale window)
 * - audit_metadata (actor / timestamp / filters / fields lists)
 */
import { useState } from 'react'
import type {
  ExportFormat,
  ExportResponse,
  WorkspaceId,
} from '@/types/admin-governance'
import { useCreateExport } from '@/admin/hooks/queries/useGovernance'

const WORKSPACES: WorkspaceId[] = [
  'command-center',
  'product-analytics',
  'ai-operations',
  'incidents-badcases',
  'logs-and-traces',
  'users-accounts',
  'reports',
  'governance',
]
const FORMATS: ExportFormat[] = ['json', 'csv', 'markdown']

export function ExportForm() {
  const [workspace, setWorkspace] = useState<WorkspaceId>('command-center')
  const [format, setFormat] = useState<ExportFormat>('json')
  const [period, setPeriod] = useState<string>('2026-Q2')
  const [featureArea, setFeatureArea] = useState<string>('')
  const [result, setResult] = useState<ExportResponse | null>(null)

  const createMutation = useCreateExport()

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    createMutation.mutate(
      {
        workspace,
        format,
        filters: { period, feature_area: featureArea || undefined },
      },
      {
        onSuccess: (resp: ExportResponse) => {
          setResult(resp)
        },
      },
    )
  }

  return (
    <div data-testid="export-form-shell">
      <form
        className="ac-gov-export__form"
        onSubmit={handleSubmit}
        data-testid="export-form"
      >
        <div className="ac-gov-export__field">
          <label className="ac-gov-reveal__label" htmlFor="export-workspace">
            Workspace
          </label>
          <select
            id="export-workspace"
            data-testid="export-format-selector-workspace"
            className="ac-gov-reveal__select"
            value={workspace}
            onChange={(e) => setWorkspace(e.target.value as WorkspaceId)}
          >
            {WORKSPACES.map((w) => (
              <option key={w} value={w}>
                {w}
              </option>
            ))}
          </select>
        </div>

        <div className="ac-gov-export__field">
          <label className="ac-gov-reveal__label" htmlFor="export-format">
            Format
          </label>
          <select
            id="export-format"
            data-testid="export-format-selector-format"
            className="ac-gov-reveal__select"
            value={format}
            onChange={(e) => setFormat(e.target.value as ExportFormat)}
          >
            {FORMATS.map((f) => (
              <option key={f} value={f}>
                {f}
              </option>
            ))}
          </select>
        </div>

        <div className="ac-gov-export__field">
          <label className="ac-gov-reveal__label" htmlFor="export-period">
            Period / feature_area
          </label>
          <div style={{ display: 'flex', gap: 6 }}>
            <input
              id="export-period"
              data-testid="export-filter-picker-period"
              className="ac-gov-reveal__input"
              type="text"
              value={period}
              onChange={(e) => setPeriod(e.target.value)}
              placeholder="2026-Q2 / 2026-07 / ..."
            />
            <input
              data-testid="export-filter-picker-feature-area"
              className="ac-gov-reveal__input"
              type="text"
              value={featureArea}
              onChange={(e) => setFeatureArea(e.target.value)}
              placeholder="feature_area (optional)"
            />
          </div>
        </div>

        <button
          type="submit"
          className="ac-gov-reveal__submit"
          data-testid="export-generate"
          style={{ gridColumn: '1 / -1', justifySelf: 'start' }}
          disabled={createMutation.isPending}
        >
          {createMutation.isPending ? 'Generating…' : 'Generate export'}
        </button>
      </form>

      {createMutation.isError ? (
        <div
          className="ac-error-banner"
          data-testid="export-error-banner"
          role="alert"
          style={{ marginTop: 12 }}
        >
          {(() => {
            const err = createMutation.error as
              | { response?: { data?: { detail?: { message?: string; expired_record_ids?: string[] } } } }
              | undefined
            const detail = err?.response?.data?.detail
            if (detail && Array.isArray(detail.expired_record_ids)) {
              return `Export blocked (EC-2): period contains ${detail.expired_record_ids.length} expired record(s) — ${detail.message ?? ''}`
            }
            return String(err ?? 'export failed')
          })()}
        </div>
      ) : null}

      {result ? (
        <div
          className="ac-gov-export__result"
          data-testid="export-result"
          data-export-id={result.export_id}
        >
          <div style={{ fontSize: 13, marginBottom: 6 }}>
            Export <code data-testid="export-result-id">{result.export_id}</code>{' '}
            ready —{' '}
            <a
              href={result.download_url}
              data-testid="export-download-link"
              onClick={(e) => e.preventDefault()}
            >
              download ({result.format})
            </a>{' '}
            · expires {result.expires_at}
          </div>
          <div
            data-testid="export-fields-included"
            style={{ fontSize: 11, marginTop: 6 }}
          >
            <strong>fields_included ({result.fields_included.length}):</strong>{' '}
            <span className="ac-gov-export__field-list">
              {result.fields_included.map((f) => (
                <span
                  key={f}
                  className="ac-gov-export__field-chip"
                  data-field={f}
                >
                  {f}
                </span>
              ))}
            </span>
          </div>
          {result.fields_redacted.length > 0 ? (
            <div
              data-testid="export-fields-redacted"
              style={{ fontSize: 11, marginTop: 6 }}
            >
              <strong>fields_redacted ({result.fields_redacted.length}):</strong>{' '}
              <span className="ac-gov-export__field-list">
                {result.fields_redacted.map((f) => (
                  <span
                    key={f}
                    className="ac-gov-export__field-chip ac-gov-export__field-chip--redacted"
                    data-redacted-field={f}
                  >
                    {f}
                  </span>
                ))}
              </span>
            </div>
          ) : null}
          {result.freshness_warnings.length > 0 ? (
            <div
              data-testid="export-freshness-warnings"
              style={{ fontSize: 11, marginTop: 6 }}
            >
              <strong>freshness_warnings:</strong>{' '}
              <span style={{ color: '#b91c1c' }}>
                {result.freshness_warnings.join('; ')}
              </span>
            </div>
          ) : null}
          <details style={{ marginTop: 8 }}>
            <summary
              style={{ fontSize: 11, cursor: 'pointer', color: 'var(--ac-ink-muted)' }}
            >
              audit_metadata
            </summary>
            <pre
              data-testid="export-audit-metadata"
              style={{
                fontSize: 11,
                background: 'white',
                padding: 8,
                borderRadius: 4,
                marginTop: 4,
                overflow: 'auto',
              }}
            >
              {JSON.stringify(result.audit_metadata, null, 2)}
            </pre>
          </details>
        </div>
      ) : null}
    </div>
  )
}

export default ExportForm
