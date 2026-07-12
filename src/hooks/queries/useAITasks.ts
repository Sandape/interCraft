/**
 * REQ-061 (US1) — TanStack Query hooks for the AI Runtime control plane.
 *
 * Query keys are namespaced under `aiTasks` (distinct from business todo `tasks`).
 * Non-terminal detail/events reconnect via polling; events dedupe by sequence.
 */
import { useEffect, useRef, useState } from 'react'
import { useQuery, type UseQueryOptions } from '@tanstack/react-query'
import {
  getAITask,
  listAITaskEvents,
  listAITasks,
  type ListAITaskEventsParams,
} from '@/api/ai-runtime'
import type {
  ListAITasksQuery,
  TaskDetail,
  TaskEvent,
  TaskEventsPage,
  TaskPage,
} from '@/types/ai-runtime'

const DEFAULT_POLL_MS = 2_000
const MIN_POLL_MS = 250
const MAX_POLL_MS = 30_000

/** Canonical TanStack Query key factory (T028 / T032). */
export const aiTaskKeys = {
  all: ['aiTasks'] as const,
  lists: () => [...aiTaskKeys.all, 'list'] as const,
  list: (filters?: ListAITasksQuery) =>
    [...aiTaskKeys.lists(), filters ?? {}] as const,
  details: () => [...aiTaskKeys.all, 'detail'] as const,
  detail: (taskId: string) => [...aiTaskKeys.details(), taskId] as const,
  events: (taskId: string, afterSequence = 0) =>
    [...aiTaskKeys.all, 'events', taskId, afterSequence] as const,
}

/** @deprecated Prefer `aiTaskKeys` — kept as an alias for callers using the OpenAPI module name. */
export const aiRuntimeKeys = {
  all: aiTaskKeys.all,
  tasks: (filters?: ListAITasksQuery) => aiTaskKeys.list(filters),
  task: (taskId: string) => aiTaskKeys.detail(taskId),
  events: (taskId: string) => aiTaskKeys.events(taskId, 0),
}

/** Clamp server-suggested poll delay into the OpenAPI-allowed window. */
export function resolvePollIntervalMs(
  nextPollAfterMs: number | undefined,
  terminal: boolean | undefined,
  fallbackMs: number = DEFAULT_POLL_MS,
): number | false {
  if (terminal) return false
  const raw = nextPollAfterMs ?? fallbackMs
  if (!Number.isFinite(raw) || raw <= 0) return fallbackMs
  return Math.min(MAX_POLL_MS, Math.max(MIN_POLL_MS, Math.floor(raw)))
}

/**
 * Dedupe a flat event list by `sequence` (first occurrence wins) and sort
 * ascending — used for polling/SSE reconnect overlap.
 */
export function dedupeTaskEventsBySequence(
  events: readonly TaskEvent[],
): TaskEvent[] {
  const bySequence = new Map<number, TaskEvent>()
  for (const event of events) {
    if (!bySequence.has(event.sequence)) {
      bySequence.set(event.sequence, event)
    }
  }
  return Array.from(bySequence.values()).sort((a, b) => a.sequence - b.sequence)
}

/** Merge two pages with first-wins sequence dedupe. */
export function dedupeEventsBySequence(
  existing: readonly TaskEvent[],
  incoming: readonly TaskEvent[],
): TaskEvent[] {
  return dedupeTaskEventsBySequence([...existing, ...incoming])
}

/** Highest contiguous sequence starting from 1 (gaps stop the cursor). */
export function nextAfterSequence(events: readonly TaskEvent[]): number {
  let expected = 1
  for (const event of events) {
    if (event.sequence !== expected) break
    expected += 1
  }
  return expected - 1
}

export function useAITasks(
  filters: ListAITasksQuery = {},
  options?: Pick<UseQueryOptions<TaskPage>, 'enabled' | 'staleTime'>,
) {
  return useQuery({
    queryKey: aiTaskKeys.list(filters),
    queryFn: ({ signal }) => listAITasks(filters, signal),
    staleTime: options?.staleTime ?? 15_000,
    enabled: options?.enabled ?? true,
  })
}

/** Detail query with reconnect polling while `terminal === false`. */
export function useAITaskDetail(
  taskId: string | null | undefined,
  options?: {
    enabled?: boolean
    /** Override poll interval while non-terminal (ms). */
    pollMs?: number
  },
) {
  return useQuery({
    queryKey: aiTaskKeys.detail(taskId ?? ''),
    queryFn: ({ signal }) => getAITask(taskId as string, signal),
    enabled: (options?.enabled ?? true) && Boolean(taskId),
    staleTime: 5_000,
    refetchInterval: (query) => {
      const data = query.state.data as TaskDetail | undefined
      if (!data) return options?.pollMs ?? DEFAULT_POLL_MS
      return resolvePollIntervalMs(
        undefined,
        data.terminal,
        options?.pollMs ?? DEFAULT_POLL_MS,
      )
    },
    refetchOnReconnect: true,
    refetchOnWindowFocus: true,
  })
}

/** Alias matching OpenAPI resource naming. */
export const useAITask = useAITaskDetail

export interface UseAITaskEventsResult {
  events: TaskEvent[]
  nextSequence: number
  terminal: boolean
  nextPollAfterMs?: number
  isLoading: boolean
  isFetching: boolean
  isError: boolean
  error: Error | null
  refetch: () => void
}

/**
 * Reconnect-friendly event stream: polls `/events?after_sequence=` and merges
 * with local history via sequence dedupe. Resets when `taskId` changes.
 */
export function useAITaskEvents(
  taskId: string | null | undefined,
  options?: {
    enabled?: boolean
    limit?: number
    /** Seed cursor (e.g. after a prior page). Defaults to 0. */
    initialAfterSequence?: number
  },
): UseAITaskEventsResult {
  const enabled = (options?.enabled ?? true) && Boolean(taskId)
  const [events, setEvents] = useState<TaskEvent[]>([])
  const [terminal, setTerminal] = useState(false)
  const [nextPollAfterMs, setNextPollAfterMs] = useState<number | undefined>()
  const afterSequenceRef = useRef(options?.initialAfterSequence ?? 0)

  useEffect(() => {
    setEvents([])
    setTerminal(false)
    setNextPollAfterMs(undefined)
    afterSequenceRef.current = options?.initialAfterSequence ?? 0
  }, [taskId, options?.initialAfterSequence])

  const query = useQuery({
    queryKey: aiTaskKeys.events(taskId ?? '', 0),
    queryFn: async ({ signal }): Promise<TaskEventsPage> => {
      const params: ListAITaskEventsParams = {
        after_sequence: afterSequenceRef.current,
        limit: options?.limit,
      }
      return listAITaskEvents(taskId as string, params, signal)
    },
    enabled,
    staleTime: 0,
    refetchInterval: (q) => {
      const data = q.state.data
      if (!data) return DEFAULT_POLL_MS
      return resolvePollIntervalMs(data.next_poll_after_ms, data.terminal)
    },
    refetchOnReconnect: true,
    refetchOnWindowFocus: true,
  })

  useEffect(() => {
    const page = query.data
    if (!page) return
    setEvents((prev) => dedupeEventsBySequence(prev, page.events))
    afterSequenceRef.current = page.next_sequence
    setTerminal(page.terminal)
    setNextPollAfterMs(page.next_poll_after_ms)
  }, [query.data])

  const merged = events
  const nextSequence = Math.max(
    afterSequenceRef.current,
    nextAfterSequence(merged),
  )

  return {
    events: merged,
    nextSequence,
    terminal,
    nextPollAfterMs,
    isLoading: query.isLoading,
    isFetching: query.isFetching,
    isError: query.isError,
    error:
      query.error instanceof Error
        ? query.error
        : query.error
          ? new Error(String(query.error))
          : null,
    refetch: () => {
      void query.refetch()
    },
  }
}
