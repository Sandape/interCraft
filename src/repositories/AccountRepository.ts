/**
 * AccountRepository — profile read / patch.
 */
import { apiClient } from '../api/client'
import type { PublicUser } from '../api/types'

export interface PatchUserInput {
  display_name?: string | null
  title?: string | null
  years_of_experience?: number | null
  target_role?: string | null
  bio?: string | null
}

export interface AccountRepository {
  getMe(): Promise<PublicUser>
  updateMe(input: PatchUserInput): Promise<PublicUser>
}

export class HttpAccountRepository implements AccountRepository {
  async getMe(): Promise<PublicUser> {
    return apiClient.request<PublicUser>({ method: 'GET', path: '/api/v1/users/me' })
  }
  async updateMe(input: PatchUserInput): Promise<PublicUser> {
    return apiClient.request<PublicUser>({ method: 'PATCH', path: '/api/v1/users/me', body: input })
  }
}

export class MockAccountRepository implements AccountRepository {
  private user: PublicUser = {
    id: '01900000-0000-7000-8000-000000000001',
    email: 'demo@intercraft.io',
    display_name: 'Demo 用户',
    title: '前端工程师',
    years_of_experience: 3,
    target_role: '高级前端工程师',
    bio: null,
    subscription: 'free',
    created_at: '2026-06-01T00:00:00Z',
    updated_at: '2026-06-12T00:00:00Z',
  }
  async getMe(): Promise<PublicUser> {
    return this.user
  }
  async updateMe(input: PatchUserInput): Promise<PublicUser> {
    this.user = { ...this.user, ...input, updated_at: new Date().toISOString() }
    return this.user
  }
}
