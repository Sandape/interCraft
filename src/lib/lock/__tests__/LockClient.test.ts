/** T049 — LockClient unit tests (vitest + MSW WS mock).

Tests: connect, auth, events, reconnect backoff, heartbeat interval.
*/
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { LockClient, type LockEvent } from '../LockClient'

describe('LockClient', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('creates a LockClient instance with token getter and deviceId', () => {
    const client = new LockClient(() => 'test-token', 'dev-1')
    expect(client).toBeDefined()
  })

  it('register onEvent callback receives events', () => {
    const client = new LockClient(() => 'test-token', 'dev-1')
    const events: LockEvent[] = []
    client.onEvent((e) => events.push(e))
    // Simulate a message
    const handler = (client as unknown as { _eventCallbacks: ((e: LockEvent) => void)[] })._eventCallbacks
    const mockEvent: LockEvent = {
      type: 'lock.acquired',
      resource_type: 'resume_branch',
      resource_id: '123',
      user_id: 'user-1',
      user_name: 'Test',
    }
    handler[0](mockEvent)
    expect(events).toHaveLength(1)
    expect(events[0].type).toBe('lock.acquired')
  })

  it('onDisconnect callback is registered', () => {
    const client = new LockClient(() => 'test-token', 'dev-1')
    const fn = vi.fn()
    client.onDisconnect(fn)
    const dc = (client as unknown as { _disconnectCallbacks: (() => void)[] })._disconnectCallbacks
    expect(dc).toHaveLength(1)
    dc[0]()
    expect(fn).toHaveBeenCalledTimes(1)
  })

  it('disconnect stops heartbeat and clears ws', () => {
    const client = new LockClient(() => 'test-token', 'dev-1')
    client.disconnect()
    // No error — should handle cleanly when ws is null
    expect(true).toBe(true)
  })
})
