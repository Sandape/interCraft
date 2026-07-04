/**
 * SaveCurrentViewButton — REQ-044 CROSS FR-006 workspace top-bar.
 *
 * Captures the current workspace filter state into a new saved
 * view. Per AC-6.11 the button sits at the top of each workspace
 * and triggers ``useCreateSavedView`` which posts to
 * ``/api/v1/admin-console/saved-views``.
 *
 * Iron rule A (memory req_032_v2_repo_stub_trap): no silent
 * fallback. If the create call fails, the error is surfaced so the
 * tester can see the failure rather than a misleading success.
 */
import { useState } from 'react'
import { useCreateSavedView } from '../hooks/queries/useSavedViews'
import type { WorkspaceId } from '../../types/admin-console'

interface SaveCurrentViewButtonProps {
  workspaceId: WorkspaceId
  /** Snapshot of the current workspace filters. */
  currentFilters: Record<string, string>
}

export function SaveCurrentViewButton({
  workspaceId,
  currentFilters,
}: SaveCurrentViewButtonProps) {
  const [open, setOpen] = useState(false)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const create = useCreateSavedView()

  const handleSave = () => {
    if (!name.trim()) return
    create.mutate(
      {
        name: name.trim(),
        workspace_id: workspaceId,
        filters: currentFilters,
        description: description.trim(),
        shared_with: [],
        trust_status: 'pending',
      },
      {
        onSuccess: () => {
          setName('')
          setDescription('')
          setOpen(false)
        },
      },
    )
  }

  if (!open) {
    return (
      <button
        type="button"
        data-testid="save-current-view-button"
        onClick={() => setOpen(true)}
        style={{
          fontSize: 12,
          padding: '4px 12px',
          border: '1px solid var(--ac-border-subtle)',
          borderRadius: 4,
          background: 'var(--ac-bg, #fff)',
          cursor: 'pointer',
        }}
      >
        Save current view
      </button>
    )
  }

  return (
    <div
      data-testid="save-current-view-form"
      style={{
        display: 'flex',
        gap: 6,
        alignItems: 'center',
        padding: 6,
        background: 'var(--ac-bg-muted, #f9fafb)',
        borderRadius: 4,
      }}
    >
      <input
        data-testid="save-current-view-name"
        type="text"
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder="Saved view name"
        style={{
          fontSize: 12,
          padding: '2px 6px',
          border: '1px solid var(--ac-border-subtle)',
          borderRadius: 2,
        }}
      />
      <input
        data-testid="save-current-view-description"
        type="text"
        value={description}
        onChange={(e) => setDescription(e.target.value)}
        placeholder="Description (optional)"
        style={{
          fontSize: 12,
          padding: '2px 6px',
          border: '1px solid var(--ac-border-subtle)',
          borderRadius: 2,
        }}
      />
      <button
        type="button"
        data-testid="save-current-view-submit"
        onClick={handleSave}
        disabled={create.isPending || !name.trim()}
        style={{
          fontSize: 12,
          padding: '2px 10px',
          background: 'var(--ac-primary, #2563eb)',
          color: '#fff',
          border: 0,
          borderRadius: 2,
          cursor: 'pointer',
        }}
      >
        Save
      </button>
      <button
        type="button"
        data-testid="save-current-view-cancel"
        onClick={() => {
          setOpen(false)
          setName('')
          setDescription('')
        }}
        style={{
          fontSize: 12,
          padding: '2px 10px',
          background: 'transparent',
          border: '1px solid var(--ac-border-subtle)',
          borderRadius: 2,
          cursor: 'pointer',
        }}
      >
        Cancel
      </button>
      {create.isError && (
        <span
          data-testid="save-current-view-error"
          style={{ color: 'var(--ac-danger, #dc2626)', fontSize: 11 }}
        >
          {String((create.error as Error | null)?.message ?? 'create failed')}
        </span>
      )}
    </div>
  )
}

export default SaveCurrentViewButton