/**
 * 036 US2 — Resume v2 list hook (replaces `useResumeBranches`).
 *
 * Wraps the v2 `/api/v1/v2/resumes` list endpoint. The v1 `resume_branches`
 * endpoints were retired in REQ-036 Phase A.2; cross-module call sites
 * (Dashboard / InterviewLive / Sidebar / DashboardSuggestions) read from
 * here instead.
 *
 * The hook tolerates both shapes returned by `listResumes`:
 *   - production: `ResumeV2ListItem[]` (already unwrapped by the api helper)
 *   - tests / legacy envelopes: `{ data: ResumeV2ListItem[] }`
 */
import { useQuery } from '@tanstack/react-query'
import { listResumes, type ResumeV2ListItem } from '@/modules/resume/v2/api'

export const RESUMES_V2_LIST_KEY = ['resumes', 'v2', 'list'] as const

interface ResumeListEnvelope {
  data?: ResumeV2ListItem[]
}

function unwrap(payload: unknown): ResumeV2ListItem[] {
  if (Array.isArray(payload)) return payload as ResumeV2ListItem[]
  if (payload && typeof payload === 'object') {
    const env = payload as ResumeListEnvelope
    if (Array.isArray(env.data)) return env.data
  }
  return []
}

export function useResumeV2List() {
  return useQuery<ResumeV2ListItem[]>({
    queryKey: RESUMES_V2_LIST_KEY,
    queryFn: async () => unwrap(await listResumes({ sort: 'updated' })),
    staleTime: 30_000,
  })
}