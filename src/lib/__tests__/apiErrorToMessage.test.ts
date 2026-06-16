import { describe, it, expect } from 'vitest'
import {
  ExportError,
  exportErrorToMessage,
  interviewErrorToMessage,
  coachErrorToMessage,
  jobErrorToMessage,
} from '../apiErrorToMessage'

describe('apiErrorToMessage', () => {
  describe('ExportError + exportErrorToMessage', () => {
    it('401 → unauthorized', () => {
      const e = new ExportError('x', 401)
      expect(exportErrorToMessage(e)).toBe('会话已过期，请重新登录')
    })
    it('404 → notFound', () => {
      const e = new ExportError('x', 404)
      expect(exportErrorToMessage(e)).toBe('导出服务未启动 (404)')
    })
    it('422 → invalid', () => {
      const e = new ExportError('x', 422)
      expect(exportErrorToMessage(e)).toBe('导出参数无效')
    })
    it('500 → unavailable', () => {
      const e = new ExportError('x', 500)
      expect(exportErrorToMessage(e)).toBe('导出服务暂不可用，请稍后重试')
    })
    it('502 → unavailable', () => {
      const e = new ExportError('x', 502)
      expect(exportErrorToMessage(e)).toBe('导出服务暂不可用，请稍后重试')
    })
    it('503 → unavailable', () => {
      const e = new ExportError('x', 503)
      expect(exportErrorToMessage(e)).toBe('导出服务暂不可用，请稍后重试')
    })
    it('preserves message for 4xx with non-empty message', () => {
      const e = new ExportError('EMPTY_CONTENT: 简历为空', 400)
      expect(exportErrorToMessage(e)).toBe('EMPTY_CONTENT: 简历为空')
    })
    it('plain Error → uses message', () => {
      expect(exportErrorToMessage(new Error('foo'))).toBe('foo')
    })
    it('non-Error → fallback', () => {
      expect(exportErrorToMessage('raw string')).toBe('导出失败')
    })
  })

  describe('interviewErrorToMessage', () => {
    it('uses Error.message', () => {
      expect(interviewErrorToMessage(new Error('foo bar'))).toBe('foo bar')
    })
    it('non-Error → fallback', () => {
      expect(interviewErrorToMessage(null)).toBe('面试操作失败')
    })
  })

  describe('coachErrorToMessage', () => {
    it('timeout message → timeout copy', () => {
      expect(coachErrorToMessage(new Error('TIMEOUT after 30s'))).toBe('启动超时，请重试')
    })
    it('generic message → preserves', () => {
      expect(coachErrorToMessage(new Error('网络错误'))).toBe('网络错误')
    })
    it('non-Error → fallback', () => {
      expect(coachErrorToMessage(undefined)).toBe('启动失败，请重试')
    })
  })

  describe('jobErrorToMessage', () => {
    it('uses Error.message', () => {
      expect(jobErrorToMessage(new Error('权限不足'))).toBe('权限不足')
    })
    it('non-Error → fallback', () => {
      expect(jobErrorToMessage(42)).toBe('求职记录操作失败')
    })
  })
})
