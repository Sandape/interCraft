/**
 * savedViewRepository — REQ-044 FR-006 stub.
 *
 * [CROSS-TEAM-DEBT] saved_view 真实持久化在 Phase 2 US-CROSS 实现.
 *
 * IA 阶段强制要求: 每个方法体必须显式 throw NotImplementedError
 * (铁律 A — memory req_032_v2_repo_stub_trap). 禁止 silent fallback
 * (禁止 silent fallback)。
 *
 * 一旦 Phase 2 US-CROSS 落地真实持久化, 删除每个方法体中的 throw,
 * 替换为真实的 fetch 调用。
 */
import type {
  SavedView,
  SavedViewListResponse,
} from '../types/admin-console'

export interface CreateSavedViewInput {
  name: string
  filters: Record<string, string>
  owner: string
  description: string
  trustStatus: SavedView['trustStatus']
}

export interface UpdateSavedViewInput {
  name?: string
  filters?: Record<string, string>
  description?: string
  trustStatus?: SavedView['trustStatus']
}

export interface SavedViewRepository {
  list(): Promise<SavedViewListResponse>
  get(id: string): Promise<SavedView>
  create(input: CreateSavedViewInput): Promise<SavedView>
  update(id: string, input: UpdateSavedViewInput): Promise<SavedView>
  delete(id: string): Promise<void>
}

export class HttpSavedViewRepository implements SavedViewRepository {
  async list(): Promise<SavedViewListResponse> {
    throw new NotImplementedError('saved_view 持久化 in US-CROSS')
  }
  async get(_id: string): Promise<SavedView> {
    throw new NotImplementedError('saved_view 持久化 in US-CROSS')
  }
  async create(_input: CreateSavedViewInput): Promise<SavedView> {
    throw new NotImplementedError('saved_view 持久化 in US-CROSS')
  }
  async update(_id: string, _input: UpdateSavedViewInput): Promise<SavedView> {
    throw new NotImplementedError('saved_view 持久化 in US-CROSS')
  }
  async delete(_id: string): Promise<void> {
    throw new NotImplementedError('saved_view 持久化 in US-CROSS')
  }
}

export class NotImplementedError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'NotImplementedError'
  }
}

export const savedViewRepository: SavedViewRepository = new HttpSavedViewRepository()