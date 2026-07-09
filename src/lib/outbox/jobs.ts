/** 024 US2 — Outbox enqueue adapters for job write operations. */
import { outboxRepo } from './OutboxRepository'
import { outboxDb } from './db'
import type { OutboxEntry } from './db'

function makeEntry(opts: {
  operation: 'create' | 'update' | 'delete'
  entityId: string
  payload: Record<string, unknown>
}): OutboxEntry {
  return {
    entity_type: 'job',
    operation: opts.operation,
    entity_id: opts.entityId,
    payload: opts.payload,
    entity_updated_at: new Date().toISOString(),
    client_timestamp: Date.now(),
    retry_count: 0,
    status: 'pending',
  }
}

export async function enqueueCreateJob(input: Record<string, unknown>): Promise<string> {
  const tempId = crypto.randomUUID()
  await outboxRepo.add(makeEntry({
    operation: 'create',
    entityId: tempId,
    payload: input,
  }))
  return tempId
}

export interface UpdateParams {
  id: string
  patch: Record<string, unknown>
}

export async function enqueueUpdateJob(params: UpdateParams): Promise<void> {
  await outboxRepo.add(makeEntry({
    operation: 'update',
    entityId: params.id,
    payload: params.patch,
  }))
}

export async function enqueueAdvanceStatus(params: {
  id: string
  to: string
  note?: string
}): Promise<void> {
  // 024 — payload shape must match backend UpdateJobStatusInput schema
  // ({to, note}) so OutboxService._replay_job can route status advances
  // through JobService.update_status (FSM + status_history + task triggers).
  await outboxRepo.add(makeEntry({
    operation: 'update',
    entityId: params.id,
    payload: { to: params.to, note: params.note ?? null },
  }))
}

export async function enqueueDeleteJob(jobId: string): Promise<void> {
  await outboxRepo.add(makeEntry({
    operation: 'delete',
    entityId: jobId,
    payload: {},
  }))
}

/** Get the set of job IDs that have pending outbox entries. */
export async function getPendingJobIds(): Promise<Set<string>> {
  const pending = await outboxRepo.getPending(100)
  const ids = new Set<string>()
  for (const entry of pending) {
    if (entry.entity_type === 'job') {
      ids.add(entry.entity_id)
    }
  }
  return ids
}

/** Count dead-letter (failed) entries for jobs. */
export async function getFailedJobEntries(): Promise<OutboxEntry[]> {
  return outboxDb.outbox_entries
    .where({ entity_type: 'job', status: 'failed' })
    .toArray()
}

/** Cancel a pending outbox entry by its entity_id. */
export async function cancelPendingEntry(entityId: string): Promise<void> {
  const entries = await outboxDb.outbox_entries
    .where({ entity_type: 'job', entity_id: entityId, status: 'pending' })
    .toArray()
  await outboxDb.outbox_entries.bulkDelete(entries.map((e) => e.id!).filter(Boolean))
}

/** Reset all failed job entries back to pending for retry. */
export async function resetFailedEntries(): Promise<number> {
  const failed = await outboxDb.outbox_entries
    .where({ entity_type: 'job', status: 'failed' })
    .toArray()
  for (const entry of failed) {
    if (entry.id) {
      await outboxDb.outbox_entries.update(entry.id, {
        status: 'pending',
        retry_count: 0,
        error_message: undefined,
      })
    }
  }
  return failed.length
}
