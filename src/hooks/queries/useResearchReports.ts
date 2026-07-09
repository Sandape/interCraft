/** REQ-053 (US6) — Research report React Query hooks. */
import { useQuery } from '@tanstack/react-query'
import { getResearchReport, listResearchReports } from '@/api/research'
import type {
  ResearchReportDetail,
  ResearchReportListResponse,
} from '@/types/research'

export function useResearchReports(jobId: string | null | undefined) {
  return useQuery<ResearchReportListResponse>({
    queryKey: ['researchReports', jobId],
    queryFn: () => listResearchReports(jobId as string),
    enabled: !!jobId,
    staleTime: 30_000,
  })
}

export function useResearchReport(
  jobId: string | null | undefined,
  reportId: string | null | undefined,
) {
  return useQuery<ResearchReportDetail>({
    queryKey: ['researchReport', jobId, reportId],
    queryFn: () => getResearchReport(jobId as string, reportId as string),
    enabled: !!jobId && !!reportId,
    staleTime: 30_000,
  })
}
