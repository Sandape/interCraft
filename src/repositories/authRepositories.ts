/**
 * Lightweight repository factory for auth and current-user bootstrap.
 *
 * Keep this separate from `repositories/types.ts`: the full factory imports
 * every business repository, which makes the public login route pay a large
 * Vite cold-transform cost before the user can see the page.
 */
import { env } from '../api/env'
import { AuthRepository, HttpAuthRepository } from './AuthRepository'
import { AccountRepository, HttpAccountRepository, MockAccountRepository } from './AccountRepository'

let _auth: AuthRepository | null = null
let _account: AccountRepository | null = null

export function getAuthRepository(): AuthRepository {
  if (!_auth) _auth = new HttpAuthRepository()
  return _auth
}

export function getAccountRepository(): AccountRepository {
  if (!_account) _account = env.USE_MOCK ? new MockAccountRepository() : new HttpAccountRepository()
  return _account
}

export function resetAuthRepositoriesForTests(): void {
  _auth = null
  _account = null
}
