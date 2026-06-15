/** T031 — Dexie CRUD wrapper for outbox_entries table.

Exposes a singleton `outboxRepo` with typed async methods.
*/
import { outboxDb, type OutboxEntry } from './db'

export const outboxRepo = {
  async add(entry: OutboxEntry): Promise<number> {
    return outboxDb.outbox_entries.add(entry) as Promise<number>
  },

  async getPending(limit = 30): Promise<OutboxEntry[]> {
    return outboxDb.outbox_entries
      .where({ status: 'pending' })
      .sortBy('client_timestamp')
      .then((rows) => rows.slice(0, limit))
  },

  async markSyncing(ids: number[]): Promise<void> {
    await outboxDb.outbox_entries.bulkUpdate(
      ids.map((id) => ({ key: id, changes: { status: 'syncing' as const } })),
    )
  },

  async markSynced(ids: number[]): Promise<void> {
    await outboxDb.outbox_entries.bulkUpdate(
      ids.map((id) => ({ key: id, changes: { status: 'synced' as const } })),
    )
  },

  async markConflict(
    id: number,
    serverEntity: Record<string, unknown>,
  ): Promise<void> {
    await outboxDb.outbox_entries.update(id, {
      status: 'conflict',
      payload: { ...(await outboxDb.outbox_entries.get(id))?.payload, _server_entity: serverEntity },
    })
  },

  async markFailed(id: number, error: string): Promise<void> {
    await outboxDb.outbox_entries.update(id, {
      status: 'failed',
      error_message: error,
    })
  },

  async incrementRetry(id: number): Promise<void> {
    const entry = await outboxDb.outbox_entries.get(id)
    if (entry) {
      await outboxDb.outbox_entries.update(id, {
        retry_count: (entry.retry_count ?? 0) + 1,
      })
    }
  },

  async countPending(): Promise<number> {
    return outboxDb.outbox_entries.where({ status: 'pending' }).count()
  },

  async countByStatus(
    status: OutboxEntry['status'],
  ): Promise<number> {
    return outboxDb.outbox_entries.where({ status }).count()
  },

  async cleanup(retain = 50): Promise<void> {
    const synced = await outboxDb.outbox_entries
      .where({ status: 'synced' })
      .sortBy('client_timestamp')
    if (synced.length > retain) {
      const toDelete = synced.slice(0, synced.length - retain)
      await outboxDb.outbox_entries.bulkDelete(toDelete.map((e) => e.id!))
    }
  },
}
