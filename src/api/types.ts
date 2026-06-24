/**
 * Shared domain types — mirror the backend Pydantic schemas.
 * Keep field names in sync with backend/app/modules/.../schemas.py.
 */

export type Subscription = 'free' | 'pro' | 'enterprise'

export type BranchStatus = 'draft' | 'optimizing' | 'ready' | 'submitted' | 'archived'

export interface PublicUser {
  id: string
  email: string
  display_name: string | null
  title: string | null
  years_of_experience: number | null
  target_role: string | null
  bio: string | null
  subscription: Subscription
  avatar_url: string | null
  created_at: string
  updated_at: string
}

export interface TokenPair {
  access_token: string
  refresh_token: string
  token_type: 'Bearer'
  expires_in: number
}

export interface AuthRegisterResponse {
  user: PublicUser
  tokens: TokenPair
}

export interface AuthLoginResponse {
  user: PublicUser
  tokens: TokenPair
  evicted_session_id: string | null
}

export interface RefreshResponse {
  tokens: TokenPair
}

export interface DeviceSession {
  id: string
  device_id: string
  device_name: string | null
  ip: string | null
  user_agent: string | null
  created_at: string
  last_seen_at: string | null
  is_current: boolean
}
