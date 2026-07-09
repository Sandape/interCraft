/** REQ-053 (US6) — Research report API client.
 *
 * Endpoints follow the contract in `specs/053-interview-intelligence/contracts/api.yaml`:
 *  - GET   /api/v1/jobs/{jobId}/research-reports
 *  - GET   /api/v1/jobs/{jobId}/research-reports/{reportId}
 *  - PATCH /api/v1/research-reports/{reportId}/rating
 */
import { apiClient } from './client'
import type {
  ResearchReportDetail,
  ResearchReportListResponse,
} from '@/types/research'

export async function listResearchReports(jobId: string): Promise<ResearchReportListResponse> {
  return apiClient.request<ResearchReportListResponse>(
    'GET',
    `/api/v1/jobs/${jobId}/research-reports`,
  )
}

export async function getResearchReport(
  jobId: string,
  reportId: string,
): Promise<ResearchReportDetail> {
  return apiClient.request<ResearchReportDetail>(
    'GET',
    `/api/v1/jobs/${jobId}/research-reports/${reportId}`,
  )
}

export async function rateResearchReport(
  reportId: string,
  rating: number,
): Promise<ResearchReportDetail> {
  return apiClient.request<ResearchReportDetail>(
    'PATCH',
    `/api/v1/research-reports/${reportId}/rating`,
    { rating },
  )
}
