/**
 * ResumeBlockRepository — block CRUD + reorder.
 */
import { apiClient } from '../api/client'
import type { BlockType, CreateBlockInput, PatchBlockInput, ReorderBlocksInput, ResumeBlock } from '../api/types'

export interface ResumeBlockRepository {
  list(branchId: string, type?: BlockType): Promise<ResumeBlock[]>
  get(blockId: string): Promise<ResumeBlock>
  create(branchId: string, input: CreateBlockInput): Promise<ResumeBlock>
  patch(blockId: string, input: PatchBlockInput): Promise<ResumeBlock>
  reorder(blockId: string, input: ReorderBlocksInput): Promise<ResumeBlock>
  delete(blockId: string): Promise<void>
}

export class HttpResumeBlockRepository implements ResumeBlockRepository {
  async list(branchId: string, type?: BlockType): Promise<ResumeBlock[]> {
    const res = await apiClient.request<{ data: ResumeBlock[] }>({
      method: 'GET',
      path: `/api/v1/resume-branches/${branchId}/blocks`,
      query: type ? { type } : undefined,
    })
    return res.data
  }
  async get(blockId: string): Promise<ResumeBlock> {
    const res = await apiClient.request<{ block: ResumeBlock }>({
      method: 'GET',
      path: `/api/v1/resume-blocks/${blockId}`,
    })
    return res.block
  }
  async create(branchId: string, input: CreateBlockInput): Promise<ResumeBlock> {
    const res = await apiClient.request<{ block: ResumeBlock }>({
      method: 'POST',
      path: `/api/v1/resume-branches/${branchId}/blocks`,
      body: input,
    })
    return res.block
  }
  async patch(blockId: string, input: PatchBlockInput): Promise<ResumeBlock> {
    const res = await apiClient.request<{ block: ResumeBlock }>({
      method: 'PATCH',
      path: `/api/v1/resume-blocks/${blockId}`,
      body: input,
    })
    return res.block
  }
  async reorder(blockId: string, input: ReorderBlocksInput): Promise<ResumeBlock> {
    const res = await apiClient.request<{ block: ResumeBlock }>({
      method: 'PATCH',
      path: `/api/v1/resume-blocks/${blockId}/reorder`,
      body: input,
    })
    return res.block
  }
  async delete(blockId: string): Promise<void> {
    await apiClient.request<void>({ method: 'DELETE', path: `/api/v1/resume-blocks/${blockId}` })
  }
}

