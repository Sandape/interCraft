/** T032 — OutboxReplayService: detect online status and auto-replay.

Listens to `window.addEventListener('online')` and polls every 30s.
Calls `POST /api/v1/outbox/replay` to flush pending entries.
*/
import { outboxRepo } from './OutboxRepository'
import type { OutboxEntry } from './db'

export type ConflictCallback = (entry: OutboxEntry, serverEntity: Record<string, unknown>, conflictFields: string[]) => void

const MAX_RETRY = 3
const REPLAY_BATCH_SIZE = 30

export class OutboxReplayService {
  private _onConflict: ConflictCallback | null = null
  private _watching = false
  private _timer: ReturnType<typeof setInterval> | null = null

  get pendingCount(): Promise<number> {
    return outboxRepo.countPending()
  }

  onConflict(cb: ConflictCallback): void {
    this._onConflict = cb
  }

  startWatching(): void {
    if (this._watching) return
    this._watching = true
    window.addEventListener('online', () => {
      this.replay()
    })
    // Poll every 30s
    this._timer = setInterval(() => {
      if (navigator.onLine) {
        this.replay()
      }
    }, 30_000)
  }

  stopWatching(): void {
    this._watching = false
    if (this._timer) {
      clearInterval(this._timer)
      this._timer = null
    }
  }

  async replay(): Promise<void> {
    if (!navigator.onLine) return

    let pending = await outboxRepo.getPending(REPLAY_BATCH_SIZE)
    while (pending.length > 0) {
      const ids = pending.map((e) => e.id!).filter(Boolean)
      await outboxRepo.markSyncing(ids)

      const entries = pending.map((e) => ({
        client_entry_id: e.id!,
        entity_type: e.entity_type,
        operation: e.operation,
        entity_id: e.entity_id,
        payload: e.payload,
        entity_updated_at: e.entity_updated_at,
        client_timestamp: e.client_timestamp,
      }))

      try {
        const token = localStorage.getItem('access_token') ?? ''
        const res = await fetch('/api/v1/outbox/replay', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({ entries }),
        })

        if (!res.ok) {
          // Mark all as pending for retry
          // Revert to pending for retry
          await outboxRepo.markSynced(
            pending.map((e) => e.id!).filter(Boolean),
          )
          return
        }

        const data = await res.json()
        for (const result of data.results ?? []) {
          const entry = pending.find((e) => e.id === result.client_entry_id)
          if (!entry) continue

          if (result.status === 'ok') {
            await outboxRepo.markSynced([result.client_entry_id])
          } else if (result.status === 'conflict') {
            await outboxRepo.markConflict(
              result.client_entry_id,
              result.server_entity ?? {},
            )
            if (this._onConflict) {
              this._onConflict(
                entry,
                result.server_entity ?? {},
                result.conflict_fields ?? [],
              )
            }
          } else {
            const existing = entry.retry_count ?? 0
            if (existing + 1 >= MAX_RETRY) {
              await outboxRepo.markFailed(
                result.client_entry_id,
                result.error ?? 'Unknown error',
              )
            } else {
              await outboxRepo.incrementRetry(result.client_entry_id)
            }
          }
        }
      } catch (err) {
        // Network error — keep as pending
        break
      }

      pending = await outboxRepo.getPending(REPLAY_BATCH_SIZE)
    }

    // Cleanup old synced entries
    await outboxRepo.cleanup(50)
  }
}

/** Singleton instance for the app. */
export const outboxReplayService = new OutboxReplayService()
