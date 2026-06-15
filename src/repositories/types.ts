/**
 * Repository factory — toggles between HTTP and Mock implementations
 * based on `VITE_USE_MOCK`. The default for development is `true`
 * so the UI works without a backend; flip to `false` in `.env.local`
 * to test against the real FastAPI service.
 */
import { env } from '../api/env'
import { AuthRepository, HttpAuthRepository } from './AuthRepository'
import { AccountRepository, HttpAccountRepository, MockAccountRepository } from './AccountRepository'
import { SessionRepository, HttpSessionRepository, MockSessionRepository } from './SessionRepository'
import { ResumeRepository, HttpResumeRepository } from './ResumeRepository'
import { ResumeBlockRepository, HttpResumeBlockRepository } from './ResumeBlockRepository'
import {
  ResumeVersionRepository,
  HttpResumeVersionRepository,
} from './ResumeVersionRepository'
import { AbilityRepository, HttpAbilityRepository, MockAbilityRepository } from './AbilityRepository'
import {
  ErrorQuestionRepository,
  HttpErrorQuestionRepository,
  MockErrorQuestionRepository,
} from './ErrorQuestionRepository'
import { JobRepository, HttpJobRepository, MockJobRepository } from './JobRepository'
import { TaskRepository, HttpTaskRepository, MockTaskRepository } from './TaskRepository'
import { ActivityRepository, HttpActivityRepository, MockActivityRepository } from './ActivityRepository'
import {
  InterviewSessionRepository,
  HttpInterviewSessionRepository,
  MockInterviewSessionRepository,
} from './InterviewSessionRepository'

let _auth: AuthRepository | null = null
let _account: AccountRepository | null = null
let _session: SessionRepository | null = null
let _resume: ResumeRepository | null = null
let _block: ResumeBlockRepository | null = null
let _version: ResumeVersionRepository | null = null
let _ability: AbilityRepository | null = null
let _errorQuestion: ErrorQuestionRepository | null = null
let _job: JobRepository | null = null
let _task: TaskRepository | null = null
let _activity: ActivityRepository | null = null
let _interviewSession: InterviewSessionRepository | null = null

export function getAuthRepository(): AuthRepository {
  if (!_auth) _auth = new HttpAuthRepository()
  return _auth
}
export function getAccountRepository(): AccountRepository {
  if (!_account) _account = env.USE_MOCK ? new MockAccountRepository() : new HttpAccountRepository()
  return _account
}
export function getSessionRepository(): SessionRepository {
  if (!_session) _session = env.USE_MOCK ? new MockSessionRepository() : new HttpSessionRepository()
  return _session
}
export function getResumeRepository(): ResumeRepository {
  if (!_resume) _resume = new HttpResumeRepository()
  return _resume
}
export function getResumeBlockRepository(): ResumeBlockRepository {
  if (!_block) _block = new HttpResumeBlockRepository()
  return _block
}
export function getResumeVersionRepository(): ResumeVersionRepository {
  if (!_version) _version = new HttpResumeVersionRepository()
  return _version
}
export function getAbilityRepository(): AbilityRepository {
  if (!_ability) _ability = env.USE_MOCK ? new MockAbilityRepository() : new HttpAbilityRepository()
  return _ability
}
export function getErrorQuestionRepository(): ErrorQuestionRepository {
  if (!_errorQuestion) _errorQuestion = env.USE_MOCK ? new MockErrorQuestionRepository() : new HttpErrorQuestionRepository()
  return _errorQuestion
}
export function getJobRepository(): JobRepository {
  if (!_job) _job = env.USE_MOCK ? new MockJobRepository() : new HttpJobRepository()
  return _job
}
export function getTaskRepository(): TaskRepository {
  if (!_task) _task = env.USE_MOCK ? new MockTaskRepository() : new HttpTaskRepository()
  return _task
}
export function getActivityRepository(): ActivityRepository {
  if (!_activity) _activity = env.USE_MOCK ? new MockActivityRepository() : new HttpActivityRepository()
  return _activity
}
export function getInterviewSessionRepository(): InterviewSessionRepository {
  if (!_interviewSession) _interviewSession = env.USE_MOCK ? new MockInterviewSessionRepository() : new HttpInterviewSessionRepository()
  return _interviewSession
}

export function resetForTests(): void {
  _auth = _account = _session = _resume = _block = _version = _ability = _errorQuestion = _job = _task = _activity = _interviewSession = null
}
