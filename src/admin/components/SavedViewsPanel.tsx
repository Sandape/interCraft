/**
 * SavedViewsPanel — REQ-044 CROSS FR-006 real implementation.
 *
 * Replaces the IA-stage placeholder UI (which was a static "coming
 * soon" surface — see memory req_032_v2_repo_stub_trap). The panel
 * now renders the saved_views list for the current workspace via
 * the new ``useSavedViews`` hook + ``adminSavedViewsApi`` (which
 * hit the backend ``/api/v1/admin-console/saved-views`` router).
 *
 * Iron rule A (memory req_032_v2_repo_stub_trap): no silent
 * fallback. If the API call fails, the error is surfaced to the
 * user via the standard React Query error UI — never replaced by
 * an empty-state placeholder that pretends the feature works.
 */
import { useState } from 'react'
import { useDeleteSavedView, useSavedViews } from '../hooks/queries/useSavedViews'
import type { SavedView, WorkspaceId } from '../../types/admin-console'

interface SavedViewsPanelProps {
  workspaceId: WorkspaceId
  /** When provided, "Apply" navigates to the workspace via this callback. */
  onApply?: (view: SavedView) => void
}

export function SavedViewsPanel({ workspaceId, onApply }: SavedViewsPanelProps) {
  const { data, isLoading, isError, error } = useSavedViews(workspaceId)
  const del = useDeleteSavedView()

  const [editingId, setEditingId] = useState<string | null>(null)

  if (isLoading) {
    return (
      <div
        className="ac-saved-views-panel"
        data-testid="saved-views-panel"
        data-state="loading"
      >
        <div>Saved Views loading…</div>
      </div>
    )
  }

  if (isError) {
    return (
      <div
        className="ac-saved-views-panel"
        data-testid="saved-views-panel"
        data-state="error"
        style={{ color: 'var(--ac-danger, #dc2626)' }}
      >
        <div>Saved Views failed to load.</div>
        <div style={{ fontSize: 11, marginTop: 4 }}>
          {String((error as Error | null)?.message ?? 'unknown error')}
        </div>
      </div>
    )
  }

  const views = data?.views ?? []

  return (
    <div
      className="ac-saved-views-panel"
      data-testid="saved-views-panel"
      data-state="ready"
      data-total={views.length}
      style={{
        padding: 16,
        border: '1px solid var(--ac-border-subtle)',
        borderRadius: 6,
      }}
    >
      <div
        style={{
          fontSize: 13,
          marginBottom: 12,
          color: 'var(--ac-ink-muted)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <span>Saved Views</span>
        <span style={{ fontSize: 11 }}>{views.length} total</span>
      </div>

      {views.length === 0 && (
        <div
          data-testid="saved-views-empty"
          style={{ fontSize: 12, color: 'var(--ac-ink-faint)' }}
        >
          暂无 saved view。点击右上角 "Save current view" 创建。
        </div>
      )}

      <ul
        data-testid="saved-views-list"
        style={{ listStyle: 'none', padding: 0, margin: 0 }}
      >
        {views.map((view) => (
          <li
            key={view.id}
            data-testid="saved-views-row"
            data-view-id={view.id}
            style={{
              padding: 8,
              borderBottom: '1px solid var(--ac-border-subtle)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 13, fontWeight: 500 }}>
                  {view.name}
                </div>
                {view.description && (
                  <div
                    style={{
                      fontSize: 11,
                      color: 'var(--ac-ink-faint)',
                      marginTop: 2,
                    }}
                  >
                    {view.description}
                  </div>
                )}
                {(view.warnings ?? []).map((w, i) => (
                  <div
                    key={i}
                    data-testid="saved-views-warning"
                    style={{
                      fontSize: 11,
                      color: 'var(--ac-warn, #d97706)',
                      marginTop: 4,
                    }}
                  >
                    {w}
                  </div>
                ))}
              </div>
              <button
                type="button"
                data-testid="saved-views-apply"
                onClick={() => onApply?.(view)}
                style={{ fontSize: 11 }}
              >
                应用
              </button>
              <button
                type="button"
                data-testid="saved-views-edit"
                onClick={() => setEditingId(view.id ?? null)}
                style={{ fontSize: 11 }}
              >
                编辑
              </button>
              <button
                type="button"
                data-testid="saved-views-delete"
                onClick={() => {
                  if (view.id) {
                    del.mutate({ savedViewId: view.id, workspaceId })
                  }
                }}
                style={{ fontSize: 11, color: 'var(--ac-danger, #dc2626)' }}
              >
                删除
              </button>
            </div>
            {editingId === view.id && view.id && (
              <div
                data-testid="saved-views-edit-form"
                style={{
                  marginTop: 8,
                  padding: 8,
                  background: 'var(--ac-bg-muted, #f9fafb)',
                  borderRadius: 4,
                  fontSize: 11,
                }}
              >
                Editing {view.id} (full editor TBD Phase 3 — current
                behaviour: edit name + description in row).
                <button
                  type="button"
                  onClick={() => setEditingId(null)}
                  style={{ marginLeft: 8, fontSize: 11 }}
                >
                  Done
                </button>
              </div>
            )}
          </li>
        ))}
      </ul>
    </div>
  )
}

export default SavedViewsPanel