/** apiErrorToMessage — 统一错误码 → 用户可见中文文案。 */
import { zhCN } from './i18n/zh-CN'

export class ExportError extends Error {
  readonly status: number
  readonly code?: string
  readonly requestId?: string
  constructor(message: string, status: number, code?: string, requestId?: string) {
    super(message)
    this.name = 'ExportError'
    this.status = status
    this.code = code
    this.requestId = requestId
  }
}

export function exportErrorToMessage(e: unknown): string {
  if (e instanceof ExportError) {
    if (e.status === 401) return zhCN.export.unauthorized
    if (e.status === 404) return zhCN.export.notFound
    if (e.status === 422) return zhCN.export.invalid
    if (e.status === 502 || e.status === 503 || e.status === 504) return zhCN.export.unavailable
    if (e.status >= 500) return zhCN.export.unavailable
    if (e.status >= 400) return e.message || zhCN.export.failed
    return zhCN.export.failed
  }
  if (e instanceof Error) return e.message || zhCN.export.failed
  return zhCN.export.failed
}

export function interviewErrorToMessage(e: unknown): string {
  if (e instanceof Error) return e.message || '面试操作失败'
  return '面试操作失败'
}

export function coachErrorToMessage(e: unknown): string {
  if (e instanceof Error) {
    if (e.message.includes('timeout') || e.message.includes('TIMEOUT')) return zhCN.errorCoach.timeout
    return e.message || zhCN.errorCoach.failed
  }
  return zhCN.errorCoach.failed
}

export function jobErrorToMessage(e: unknown): string {
  if (e instanceof Error) return e.message || '求职记录操作失败'
  return '求职记录操作失败'
}
