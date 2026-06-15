/**
 * ResumeRepository — branch CRUD + refresh-from-parent.
 */
import { apiClient } from '../api/client'
import type {
  CreateBranchInput,
  PatchBranchInput,
  RefreshFromParentResponse,
  ResumeBranch,
} from '../api/types'

export interface ResumeRepository {
  list(): Promise<ResumeBranch[]>
  get(branchId: string): Promise<ResumeBranch>
  create(input: CreateBranchInput): Promise<ResumeBranch>
  patch(branchId: string, input: PatchBranchInput): Promise<ResumeBranch>
  delete(branchId: string): Promise<void>
  refreshFromParent(branchId: string): Promise<RefreshFromParentResponse>
}

export class HttpResumeRepository implements ResumeRepository {
  async list(): Promise<ResumeBranch[]> {
    const res = await apiClient.request<{ data: ResumeBranch[] }>({
      method: 'GET',
      path: '/api/v1/resume-branches',
    })
    return res.data
  }
  async get(branchId: string): Promise<ResumeBranch> {
    const res = await apiClient.request<{ branch: ResumeBranch }>({
      method: 'GET',
      path: `/api/v1/resume-branches/${branchId}`,
    })
    return res.branch
  }
  async create(input: CreateBranchInput): Promise<ResumeBranch> {
    const res = await apiClient.request<{ branch: ResumeBranch }>({
      method: 'POST',
      path: '/api/v1/resume-branches',
      body: input,
    })
    return res.branch
  }
  async patch(branchId: string, input: PatchBranchInput): Promise<ResumeBranch> {
    const res = await apiClient.request<{ branch: ResumeBranch }>({
      method: 'PATCH',
      path: `/api/v1/resume-branches/${branchId}`,
      body: input,
    })
    return res.branch
  }
  async delete(branchId: string): Promise<void> {
    await apiClient.request<void>({ method: 'DELETE', path: `/api/v1/resume-branches/${branchId}` })
  }
  async refreshFromParent(branchId: string): Promise<RefreshFromParentResponse> {
    return apiClient.request<RefreshFromParentResponse>({
      method: 'POST',
      path: `/api/v1/resume-branches/${branchId}/refresh-from-parent`,
    })
  }
}

