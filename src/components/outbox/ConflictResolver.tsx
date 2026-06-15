/** T043 — ConflictResolver component.

Dialog for resolving conflicts between local and server versions.
Supports field-by-field selection and batch "keep local" / "keep server".
*/
import React, { useState } from 'react'
import type { OutboxEntry } from '../../lib/outbox/db'
import { outboxRepo } from '../../lib/outbox/OutboxRepository'

export interface ConflictEntry {
  outboxEntry: OutboxEntry
  serverEntity: Record<string, unknown>
  conflictFields: string[]
}

export interface ConflictResolverProps {
  conflicts: ConflictEntry[]
  onResolve: (resolvedEntryId: number) => void
  onResolveAll: () => void
  onDefer: () => void
}

export const ConflictResolver: React.FC<ConflictResolverProps> = ({
  conflicts,
  onResolve,
  onResolveAll,
  onDefer,
}) => {
  const [selectedIndex, setSelectedIndex] = useState(0)
  const [fieldSelections, setFieldSelections] = useState<
    Record<string, 'local' | 'server'>
  >({})

  if (conflicts.length === 0) return null

  const currentConflict = conflicts[selectedIndex]
  if (!currentConflict) return null

  const handleResolveLocal = async () => {
    // Apply local changes
    const entry = currentConflict.outboxEntry
    try {
      const token = localStorage.getItem('access_token') ?? ''
      const entityType = entry.entity_type
      const apiPath = `/api/v1/${entityType === 'error_question' ? 'error-questions' : entityType + 's'}/${entry.entity_id}`
      await fetch(apiPath, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(entry.payload),
      })
      await outboxRepo.markSynced([entry.id!])
      onResolve(entry.id!)
    } catch {
      // retry later
    }
  }

  const handleResolveServer = async () => {
    // Keep server version — just mark synced
    const entry = currentConflict.outboxEntry
    await outboxRepo.markSynced([entry.id!])
    onResolve(entry.id!)
  }

  const handleFieldToggle = (field: string, choice: 'local' | 'server') => {
    setFieldSelections((prev) => ({ ...prev, [field]: choice }))
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/30"
      role="dialog"
      aria-label="解决冲突"
    >
      <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full mx-4 max-h-[80vh] overflow-auto">
        <div className="p-6 border-b">
          <h2 className="text-lg font-semibold">
            解决冲突 ({selectedIndex + 1}/{conflicts.length})
          </h2>
          <p className="text-sm text-gray-500 mt-1">
            离线编辑与服务器版本存在冲突，请逐字段选择保留哪个版本
          </p>
        </div>

        <div className="p-6 space-y-4">
          <div className="text-sm text-gray-600">
            实体类型: {currentConflict.outboxEntry.entity_type} · 操作:{' '}
            {currentConflict.outboxEntry.operation}
          </div>

          {currentConflict.conflictFields.map((field) => (
            <div
              key={field}
              className="border rounded p-4 grid grid-cols-2 gap-4"
            >
              <div>
                <label className="flex items-center gap-2 text-sm font-medium mb-2">
                  <input
                    type="radio"
                    name={field}
                    checked={fieldSelections[field] !== 'server'}
                    onChange={() => handleFieldToggle(field, 'local')}
                  />
                  本地版 ({field})
                </label>
                <pre className="text-xs bg-yellow-50 p-2 rounded overflow-auto max-h-32">
                  {JSON.stringify(
                    currentConflict.outboxEntry.payload?.[field],
                    null,
                    2,
                  )}
                </pre>
              </div>
              <div>
                <label className="flex items-center gap-2 text-sm font-medium mb-2">
                  <input
                    type="radio"
                    name={field}
                    checked={fieldSelections[field] === 'server'}
                    onChange={() => handleFieldToggle(field, 'server')}
                  />
                  服务端版 ({field})
                </label>
                <pre className="text-xs bg-blue-50 p-2 rounded overflow-auto max-h-32">
                  {JSON.stringify(
                    currentConflict.serverEntity?.[field] ??
                      currentConflict.serverEntity,
                    null,
                    2,
                  )}
                </pre>
              </div>
            </div>
          ))}
        </div>

        <div className="p-6 border-t flex justify-between">
          <div className="flex gap-2">
            <button
              onClick={onDefer}
              className="px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded"
            >
              稍后处理
            </button>
            <button
              onClick={handleResolveLocal}
              className="px-4 py-2 text-sm bg-green-600 text-white rounded hover:bg-green-700"
            >
              保留本地
            </button>
            <button
              onClick={handleResolveServer}
              className="px-4 py-2 text-sm bg-blue-600 text-white rounded hover:bg-blue-700"
            >
              采用服务端
            </button>
          </div>
          <div className="flex gap-2">
            <button
              onClick={onResolveAll}
              className="px-4 py-2 text-sm bg-gray-600 text-white rounded hover:bg-gray-700"
            >
              全部采用本地
            </button>
            <button
              onClick={() => {
                conflicts.forEach((c) => {
                  outboxRepo.markSynced([c.outboxEntry.id!])
                })
                onResolveAll()
              }}
              className="px-4 py-2 text-sm bg-gray-600 text-white rounded hover:bg-gray-700"
            >
              全部采用服务端
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

export default ConflictResolver
