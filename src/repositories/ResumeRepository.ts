/**
 * ResumeRepository — branch CRUD + refresh-from-parent.
 */
import { apiClient } from '../api/client'
import type {
  CreateBranchInput,
  PatchBranchInput,
  RefreshFromParentResponse,
  ResumeBranch,
} from '@/modules/resume/api/types'

export interface ListBranchesQuery {
  search?: string
  status_filter?: string
  sort?: 'edited' | 'created' | 'match_score'
}

export interface ResumeRepository {
  list(query?: ListBranchesQuery): Promise<ResumeBranch[]>
  get(branchId: string): Promise<ResumeBranch>
  create(input: CreateBranchInput): Promise<ResumeBranch>
  patch(branchId: string, input: PatchBranchInput): Promise<ResumeBranch>
  delete(branchId: string): Promise<void>
  refreshFromParent(branchId: string): Promise<RefreshFromParentResponse>
}

export class HttpResumeRepository implements ResumeRepository {
  async list(query?: ListBranchesQuery): Promise<ResumeBranch[]> {
    const res = await apiClient.request<{ data: ResumeBranch[] }>({
      method: 'GET',
      path: '/api/v1/resume-branches',
      query: query
        ? {
            search: query.search,
            status_filter: query.status_filter,
            sort: query.sort,
          }
        : undefined,
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

