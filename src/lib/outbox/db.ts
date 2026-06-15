/** Dexie.js Outbox database — single-table IndexedDB store for offline writes. */
import Dexie, { type EntityTable } from 'dexie'

/** Shape of each outbox entry (matches data-model-phase-3.md §3.3). */
export interface OutboxEntry {
  id?: number
  entity_type: 'error_question' | 'activity' | 'user_profile' | 'job' | 'task'
  operation: 'create' | 'update' | 'delete'
  entity_id: string
  payload: Record<string, unknown>
  entity_updated_at: string
  client_timestamp: number
  retry_count: number
  status: 'pending' | 'syncing' | 'synced' | 'conflict' | 'failed'
  error_message?: string
}

/** Dexie database instance for intercraft_outbox. */
export const outboxDb = new Dexie('intercraft_outbox') as Dexie & {
  outbox_entries: EntityTable<OutboxEntry, 'id'>
}

outboxDb.version(1).stores({
  outbox_entries: '++id, entity_type, status, client_timestamp',
})

/** Export the typed table for direct use if needed. */
export const outboxEntries = outboxDb.outbox_entries
