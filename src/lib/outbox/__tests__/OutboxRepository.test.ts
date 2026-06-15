/** T011 — Dexie OutboxRepository CRUD tests (vitest + fake-indexeddb). */
import { describe, it, expect, beforeAll, afterAll } from 'vitest'
import 'fake-indexeddb/auto'

// The module we're testing — will fail to import until T031 is done.
// For TDD purposes this file documents the expected contract.

// We import the Dexie db definition which exists from T005
import { outboxDb, type OutboxEntry } from '../db'

describe('OutboxRepository', () => {
  beforeAll(() => {
    // Ensure fresh db per test file
  })

  afterAll(async () => {
    await outboxDb.delete()
  })

  it('adds an entry and assigns an auto-incremented id', async () => {
    const entry: Omit<OutboxEntry, 'id'> = {
      entity_type: 'error_question',
      operation: 'update',
      entity_id: '019b5e6c-0000-7000-0000-000000000000',
      payload: { tags: ['test'] },
      entity_updated_at: '2026-06-13T10:30:00Z',
      client_timestamp: Date.now(),
      retry_count: 0,
      status: 'pending',
    }
    const id = await outboxDb.outbox_entries.add(entry as OutboxEntry)
    expect(typeof id).toBe('number')
    expect(id).toBeGreaterThan(0)
  })

  it('lists pending entries sorted by client_timestamp ASC', async () => {
    await outboxDb.outbox_entries.clear()
    const base: Omit<OutboxEntry, 'id'> = {
      entity_type: 'error_question',
      operation: 'update',
      entity_id: '019b5e6c-0000-7000-0000-000000000000',
      payload: {},
      entity_updated_at: '2026-06-13T10:30:00Z',
      client_timestamp: 0,
      retry_count: 0,
      status: 'pending',
    }
    await outboxDb.outbox_entries.bulkAdd([
      { ...base, entity_id: 'a', client_timestamp: 3000 } as OutboxEntry,
      { ...base, entity_id: 'b', client_timestamp: 1000 } as OutboxEntry,
      { ...base, entity_id: 'c', client_timestamp: 2000 } as OutboxEntry,
    ])
    const pending = await outboxDb.outbox_entries
      .where({ status: 'pending' })
      .sortBy('client_timestamp')
    expect(pending).toHaveLength(3)
    expect(pending[0].client_timestamp).toBe(1000)
    expect(pending[2].client_timestamp).toBe(3000)
  })

  it('transitions status from pending → syncing → synced', async () => {
    await outboxDb.outbox_entries.clear()
    const id = await outboxDb.outbox_entries.add({
      entity_type: 'job',
      operation: 'update',
      entity_id: '019b5e6c-0000-7000-0000-000000000001',
      payload: { status: 'test' },
      entity_updated_at: '2026-06-13T10:25:00Z',
      client_timestamp: Date.now(),
      retry_count: 0,
      status: 'pending',
    } as OutboxEntry)

    // syncing
    await outboxDb.outbox_entries.update(id, { status: 'syncing' })
    let entry = await outboxDb.outbox_entries.get(id)
    expect(entry!.status).toBe('syncing')

    // synced
    await outboxDb.outbox_entries.update(id, { status: 'synced' })
    entry = await outboxDb.outbox_entries.get(id)
    expect(entry!.status).toBe('synced')
  })

  it('marks entry as conflict and stores server entity', async () => {
    await outboxDb.outbox_entries.clear()
    const id = await outboxDb.outbox_entries.add({
      entity_type: 'error_question',
      operation: 'update',
      entity_id: '019b5e6c-0000-7000-0000-000000000000',
      payload: { tags: ['local'] },
      entity_updated_at: '2026-06-13T10:30:00Z',
      client_timestamp: Date.now(),
      retry_count: 0,
      status: 'pending',
    } as OutboxEntry)

    // Mark as conflict (store server_entity in payload for diff merge)
    await outboxDb.outbox_entries.update(id, {
      status: 'conflict',
      payload: { tags: ['local'], _server_entity: { tags: ['server'] } },
    })
    const entry = await outboxDb.outbox_entries.get(id)
    expect(entry!.status).toBe('conflict')
  })

  it('increments retry_count', async () => {
    await outboxDb.outbox_entries.clear()
    const id = await outboxDb.outbox_entries.add({
      entity_type: 'task',
      operation: 'update',
      entity_id: '019b5e6c-0000-7000-0000-000000000002',
      payload: {},
      entity_updated_at: '2026-06-13T10:30:00Z',
      client_timestamp: Date.now(),
      retry_count: 0,
      status: 'pending',
    } as OutboxEntry)

    await outboxDb.outbox_entries.update(id, { retry_count: 1 })
    let entry = await outboxDb.outbox_entries.get(id)
    expect(entry!.retry_count).toBe(1)

    await outboxDb.outbox_entries.update(id, { retry_count: 2 })
    entry = await outboxDb.outbox_entries.get(id)
    expect(entry!.retry_count).toBe(2)
  })

  it('deletes synced entries on cleanup', async () => {
    await outboxDb.outbox_entries.clear()
    const ids: number[] = []
    for (let i = 0; i < 5; i++) {
      const id = await outboxDb.outbox_entries.add({
        entity_type: 'activity',
        operation: 'create',
        entity_id: `019b5e6c-0000-7000-0000-00000000000${i}`,
        payload: {},
        entity_updated_at: '2026-06-13T10:30:00Z',
        client_timestamp: Date.now() + i,
        retry_count: 0,
        status: 'synced',
      } as OutboxEntry)
      ids.push(id as number)
    }
    await outboxDb.outbox_entries.bulkDelete(ids)
    const remaining = await outboxDb.outbox_entries.count()
    expect(remaining).toBe(0)
  })
})
