/**
 * AuthRepository — register / login / refresh / logout / me.
 */
import { apiClient } from '../api/client'
import type { AuthLoginResponse, AuthRegisterResponse, PublicUser, RefreshResponse } from '../api/types'

export interface RegisterInput {
  email: string
  password: string
  display_name?: string | null
  device_name?: string | null
  device_fingerprint: string
}

export interface LoginInput {
  email: string
  password: string
  device_name?: string | null
  device_fingerprint: string
}

export interface AuthRepository {
  register(input: RegisterInput): Promise<AuthRegisterResponse>
  login(input: LoginInput): Promise<AuthLoginResponse>
  refresh(refreshToken: string): Promise<RefreshResponse>
  logout(): Promise<void>
  me(): Promise<PublicUser>
}

export class HttpAuthRepository implements AuthRepository {
  async register(input: RegisterInput): Promise<AuthRegisterResponse> {
    return apiClient.request<AuthRegisterResponse>({
      method: 'POST',
      path: '/api/v1/auth/register',
      body: input,
    })
  }
  async login(input: LoginInput): Promise<AuthLoginResponse> {
    return apiClient.request<AuthLoginResponse>({
      method: 'POST',
      path: '/api/v1/auth/login',
      body: input,
    })
  }
  async refresh(refreshToken: string): Promise<RefreshResponse> {
    return apiClient.request<RefreshResponse>({
      method: 'POST',
      path: '/api/v1/auth/refresh',
      body: { refresh_token: refreshToken },
    })
  }
  async logout(): Promise<void> {
    await apiClient.request<void>({ method: 'POST', path: '/api/v1/auth/logout' })
  }
  async me(): Promise<PublicUser> {
    return apiClient.request<PublicUser>({ method: 'GET', path: '/api/v1/users/me' })
  }
}

/* ---- Mock (VITE_USE_MOCK=true) ---- */

const MOCK_USER: PublicUser = {
  id: '01900000-0000-7000-8000-000000000001',
  email: 'demo@intercraft.io',
  display_name: 'Demo 用户',
  title: '前端工程师',
  years_of_experience: 3,
  target_role: '高级前端工程师',
  bio: null,
  subscription: 'free',
  avatar_url: null,
  created_at: '2026-06-01T00:00:00Z',
  updated_at: '2026-06-12T00:00:00Z',
}

export class MockAuthRepository implements AuthRepository {
  async register(_input: RegisterInput): Promise<AuthRegisterResponse> {
    return {
      user: { ...MOCK_USER, email: _input.email, display_name: _input.display_name ?? MOCK_USER.display_name },
      tokens: MOCK_TOKEN_PAIR,
    }
  }
  async login(_input: LoginInput): Promise<AuthLoginResponse> {
    return { user: MOCK_USER, tokens: MOCK_TOKEN_PAIR, evicted_session_id: null }
  }
  async refresh(_t: string): Promise<RefreshResponse> {
    return { tokens: MOCK_TOKEN_PAIR }
  }
  async logout(): Promise<void> {
    /* noop */
  }
  async me(): Promise<PublicUser> {
    return MOCK_USER
  }
}

export const MOCK_TOKEN_PAIR = {
  access_token: 'mock-access-token',
  refresh_token: 'mock-refresh-token',
  token_type: 'Bearer' as const,
  expires_in: 900,
}
