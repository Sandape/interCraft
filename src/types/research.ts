/** REQ-053 (US6) — Research report TypeScript contracts. */

export type DeliveryStatus = 'pending' | 'sent' | 'failed' | 'delayed'

export interface ResearchReportListItem {
  id: string
  report_type: 'pre_interview_research'
  job_id: string
  interview_time: string
  company: string
  position: string
  status: string
  generated_at: string
  delivery_status: DeliveryStatus
  rating: number | null
}

export interface ResearchReportListResponse {
  data: ResearchReportListItem[]
}

export interface ResearchReportDetail {
  id: string
  report_type: 'pre_interview_research'
  job_id: string
  interview_time: string
  summary_md: string
  research_task_id: string
  rating: number | null
  generated_at: string
  delivery_status: DeliveryStatus
  delivered_at: string | null
  quality_check_passed: boolean
}
