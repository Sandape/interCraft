/** Mutation hooks for jobs (US8). */
import { useMutation, useQueryClient } from '@tanstack/react-query'
import type { Job } from '../../repositories/JobRepository'
import { getJobRepository } from '../../repositories/types'

export function useCreateJob() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (input: {
      company: string
      position: string
      jd_url?: string
      branch_id?: string
      notes_md?: string | null
      base_location?: string | null
      requirements_md?: string | null
      employment_type?: string
      salary_range_text?: string | null
      headcount?: number | null
    }) => getJobRepository().create(input),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['jobs'] })
      qc.invalidateQueries({ queryKey: ['jobStats'] })
    },
  })
}

/** 019 — bind / unbind a resume branch on a job (US2, FR-008). */
export function useBindBranchToJob() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ jobId, branchId }: { jobId: string; branchId: string | null }) =>
      getJobRepository().patch(jobId, { branch_id: branchId }),
    onSuccess: (data: Job) => {
      qc.setQueryData(['job', data.id], data)
      qc.invalidateQueries({ queryKey: ['jobs'] })
    },
  })
}

export function useUpdateJobStatus() {
  const qc = useQueryClient()
  return useMutation({
    // REQ-053: status advances to interview rounds carry an `interview_time`
    // payload. Terminal advances (failed/passed) pass null/undefined.
    mutationFn: ({
      id,
      to,
      note,
      interview_time,
    }: {
      id: string
      to: string
      note?: string
      interview_time?: string | null
    }) => getJobRepository().updateStatus(id, to, note, interview_time),
    onSuccess: (data: Job) => {
      qc.setQueryData(['job', data.id], data)
      qc.invalidateQueries({ queryKey: ['jobs'] })
      qc.invalidateQueries({ queryKey: ['jobStats'] })
      qc.invalidateQueries({ queryKey: ['tasks'] })
    },
  })
}

export function useDeleteJob() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => getJobRepository().delete(id),
    onSuccess: (_data, id) => {
      qc.removeQueries({ queryKey: ['job', id] })
      qc.invalidateQueries({ queryKey: ['jobs'] })
      qc.invalidateQueries({ queryKey: ['jobStats'] })
    },
  })
}
