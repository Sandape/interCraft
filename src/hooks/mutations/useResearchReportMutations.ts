/** REQ-053 (US6) — Submit a 1-5 star rating for a research report (SC-009). */
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { rateResearchReport } from '@/api/research'

export function useRateResearchReport(jobId: string, reportId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (rating: number) => rateResearchReport(reportId, rating),
    onSuccess: (data) => {
      qc.setQueryData(['researchReport', jobId, reportId], data)
      qc.invalidateQueries({ queryKey: ['researchReports', jobId] })
    },
  })
}
