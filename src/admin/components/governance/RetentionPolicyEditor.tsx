/**
 * RetentionPolicyEditor — REQ-044 FR-036 / AC-36.4.
 *
 * Lists all retention policies (per workspace_field) with:
 *   workspace_field / retention_days / action (block | warn | redact) /
 *   last_reconciled_at / updated_by
 *
 * Edit form for inline updates: writes trigger an audit event
 * ("review_snapshot" with target_kind=governance) + cache
 * invalidation (EC-3) per FR-036 + EC-4.
 */
import { useState } from 'react'
import type {
  RetentionAction,
  RetentionPolicy,
  WorkspaceId,
} from '@/types/admin-governance'
import {
  useRetentionPolicy,
  useUpdateRetentionPolicy,
} from '@/admin/hooks/queries/useGovernance'

const ACTIONS: RetentionAction[] = ['block', 'warn', 'redact']
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

export function RetentionPolicyEditor() {
  const q = useRetentionPolicy()
  const updateMutation = useUpdateRetentionPolicy()

  const policies = q.data?.policies ?? []

  return (
    <div data-testid="retention-policy-editor-shell">
      <h3 style={{ fontSize: 13, margin: '4px 0' }}>
        Retention status board (per workspace_field)
      </h3>
      <div
        className="ac-gov-matrix"
        data-testid="retention-status-board"
        data-policy-count={policies.length}
      >
        <div className="ac-gov-retention__grid ac-gov-retention__grid--header">
          <span>workspace_field</span>
          <span>retention_days</span>
          <span>action</span>
          <span>last_reconciled_at</span>
          <span>updated_by</span>
        </div>
        {policies.length === 0 ? (
          <div
            data-testid="retention-policies-empty"
            style={{ padding: 12, fontSize: 12 }}
          >
            No retention policies configured.
          </div>
        ) : (
          policies.map((p: RetentionPolicy) => (
            <div
              key={p.workspace_field}
              className="ac-gov-retention__grid"
              data-testid={`retention-row-${p.workspace_field}`}
              data-workspace-field={p.workspace_field}
            >
              <span>{p.workspace_field}</span>
              <span>{p.retention_days}d</span>
              <span>{p.action}</span>
              <span>{p.last_reconciled_at}</span>
              <span>{p.updated_by}</span>
            </div>
          ))
        )}
      </div>

      <h3 style={{ fontSize: 13, margin: '16px 0 4px' }}>Edit policy</h3>
      <RetentionEditor
        onSubmit={(body) => updateMutation.mutate(body)}
        isPending={updateMutation.isPending}
      />
      {updateMutation.isError ? (
        <div
          className="ac-error-banner"
          data-testid="retention-update-error"
          role="alert"
          style={{ marginTop: 8 }}
        >
          {String((updateMutation.error as Error)?.message ?? 'update failed')}
        </div>
      ) : null}
      {updateMutation.isSuccess ? (
        <div
          data-testid="retention-update-success"
          style={{
            marginTop: 8,
            fontSize: 12,
            padding: 8,
            background: 'rgba(22, 163, 74, 0.08)',
            color: '#15803d',
            borderRadius: 4,
          }}
        >
          Policy updated. Cache invalidated + audit event recorded (EC-3 + EC-4).
        </div>
      ) : null}
    </div>
  )
}

function RetentionEditor({
  onSubmit,
  isPending,
}: {
  onSubmit: (body: {
    workspace_field: WorkspaceId
    retention_days: number
    action: RetentionAction
  }) => void
  isPending: boolean
}) {
  const [workspace, setWorkspace] = useState<WorkspaceId>('governance')
  const [retentionDays, setRetentionDays] = useState<number>(90)
  const [action, setAction] = useState<RetentionAction>('warn')

  return (
    <form
      className="ac-gov-retention__editor"
      data-testid="retention-policy-editor"
      onSubmit={(e) => {
        e.preventDefault()
        if (retentionDays < 1 || retentionDays > 3650) return
        onSubmit({
          workspace_field: workspace,
          retention_days: retentionDays,
          action,
        })
      }}
    >
      <select
        data-testid="retention-workspace-field"
        value={workspace}
        onChange={(e) => setWorkspace(e.target.value as WorkspaceId)}
      >
        {WORKSPACES.map((w) => (
          <option key={w} value={w}>
            {w}
          </option>
        ))}
      </select>
      <input
        type="number"
        min={1}
        max={3650}
        data-testid="retention-days"
        value={retentionDays}
        onChange={(e) => setRetentionDays(parseInt(e.target.value, 10) || 0)}
      />
      <select
        data-testid="retention-action"
        value={action}
        onChange={(e) => setAction(e.target.value as RetentionAction)}
      >
        {ACTIONS.map((a) => (
          <option key={a} value={a}>
            {a}
          </option>
        ))}
      </select>
      <button
        type="submit"
        className="ac-gov-reveal__submit"
        data-testid="retention-submit"
        disabled={isPending || retentionDays < 1 || retentionDays > 3650}
      >
        {isPending ? 'Updating…' : 'Update policy'}
      </button>
    </form>
  )
}

export default RetentionPolicyEditor
