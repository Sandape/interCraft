/**
 * ResumeVersionRepository — list, save, get, rollback.
 */
import { apiClient } from '../api/client'
import type {
  CreateVersionInput,
  ResumeVersionDetail,
  ResumeVersionSummary,
  RollbackResponse,
} from '../api/types'

export interface ResumeVersionRepository {
  list(branchId: string): Promise<ResumeVersionSummary[]>
  get(branchId: string, versionNo: number): Promise<ResumeVersionDetail>
  save(branchId: string, input: CreateVersionInput): Promise<ResumeVersionSummary>
  rollback(branchId: string, versionNo: number, newName?: string): Promise<RollbackResponse>
}

export class HttpResumeVersionRepository implements ResumeVersionRepository {
  async list(branchId: string): Promise<ResumeVersionSummary[]> {
    const res = await apiClient.request<{ data: ResumeVersionSummary[] }>({
      method: 'GET',
      path: `/api/v1/resume-branches/${branchId}/versions`,
    })
    return res.data
  }
  async get(branchId: string, versionNo: number): Promise<ResumeVersionDetail> {
    const res = await apiClient.request<{ version: ResumeVersionDetail }>({
      method: 'GET',
      path: `/api/v1/resume-branches/${branchId}/versions/${versionNo}`,
    })
    return res.version
  }
  async save(branchId: string, input: CreateVersionInput): Promise<ResumeVersionSummary> {
    const res = await apiClient.request<{ version: ResumeVersionSummary }>({
      method: 'POST',
      path: `/api/v1/resume-branches/${branchId}/versions`,
      body: input,
    })
    return res.version
  }
  async rollback(branchId: string, versionNo: number, newName?: string): Promise<RollbackResponse> {
    return apiClient.request<RollbackResponse>({
      method: 'POST',
      path: `/api/v1/resume-branches/${branchId}/versions/${versionNo}/rollback`,
      body: { new_name: newName },
    })
  }
}

