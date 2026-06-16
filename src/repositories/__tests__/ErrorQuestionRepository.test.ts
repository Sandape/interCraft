/** ErrorQuestionRepository contract tests (US6 + Feature 016). */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { HttpErrorQuestionRepository, MockErrorQuestionRepository } from '../ErrorQuestionRepository'

const QUESTION_ID = '00000000-0000-7000-8000-000000000010'

function errorQuestion(overrides: Record<string, unknown> = {}) {
  return {
    id: QUESTION_ID,
    source_session_id: null,
    dimension: 'algorithm',
    question_text: 'What is the time complexity of quicksort?',
    answer_text: 'O(n log n) average, O(n^2) worst',
    reference_answer_md: null,
    status: 'fresh',
    frequency: 3,
    score: 0,
    tags: null,
    archived_at: null,
    last_practiced_at: null,
    created_at: '2026-06-13T00:00:00Z',
    updated_at: '2026-06-13T00:00:00Z',
    ...overrides,
  }
}

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input)
    const method = init?.method ?? 'GET'
    const body = init?.body ? JSON.parse(String(init.body)) as Record<string, unknown> : {}

    if (method === 'GET' && url.includes('/api/v1/error-questions?')) {
      return jsonResponse({ data: [errorQuestion()], next_cursor: null, has_more: false })
    }

    if (method === 'POST' && url.endsWith('/api/v1/error-questions')) {
      return jsonResponse(errorQuestion({
        id: '00000000-0000-7000-8000-000000000011',
        dimension: body.dimension ?? 'algorithm',
        question_text: body.question_text,
        answer_text: body.answer_text ?? null,
      }), 201)
    }

    if (method === 'GET' && url.endsWith(`/api/v1/error-questions/${QUESTION_ID}`)) {
      return jsonResponse(errorQuestion({ status: 'practicing', frequency: 2 }))
    }

    if (method === 'PATCH' && url.endsWith(`/api/v1/error-questions/${QUESTION_ID}`)) {
      return jsonResponse(errorQuestion({
        question_text: body.question_text ?? 'test',
        status: body.status ?? 'fresh',
        frequency: body.frequency ?? 3,
      }))
    }

    if (method === 'DELETE' && url.endsWith(`/api/v1/error-questions/${QUESTION_ID}`)) {
      return new Response(null, { status: 204 })
    }

    if (method === 'POST' && url.endsWith(`/api/v1/error-questions/${QUESTION_ID}/reset`)) {
      return jsonResponse(errorQuestion({ status: 'fresh', frequency: 3 }))
    }

    if (method === 'POST' && url.endsWith(`/api/v1/error-questions/${QUESTION_ID}/recall`)) {
      return jsonResponse(errorQuestion({
        status: 'practicing',
        frequency: 2,
        last_practiced_at: '2026-06-13T00:05:00Z',
        updated_at: '2026-06-13T00:05:00Z',
      }))
    }

    return jsonResponse({ error: { code: 'not_found', message: 'Unhandled test URL' } }, 404)
  }))
})

describe('HttpErrorQuestionRepository', () => {
  const repo = new HttpErrorQuestionRepository()

  it('lists error questions', async () => {
    const result = await repo.list({ dimension: 'algorithm' })

    expect(result.data).toHaveLength(1)
    expect(result.data[0].dimension).toBe('algorithm')
  })

  it('creates an error question', async () => {
    const created = await repo.create({ question_text: 'New error?', dimension: 'algorithm' })

    expect(created.status).toBe('fresh')
    expect(created.frequency).toBe(3)
    expect(created.question_text).toBe('New error?')
  })

  it('gets a single error question', async () => {
    const item = await repo.get(QUESTION_ID)

    expect(item.status).toBe('practicing')
    expect(item.frequency).toBe(2)
  })

  it('patches an error question', async () => {
    const patched = await repo.patch(QUESTION_ID, { status: 'mastered', frequency: 0 })

    expect(patched.status).toBe('mastered')
    expect(patched.frequency).toBe(0)
  })

  it('archives an error question', async () => {
    await expect(repo.archive(QUESTION_ID)).resolves.toBeUndefined()
  })

  it('resets an error question', async () => {
    const reset = await repo.reset(QUESTION_ID)

    expect(reset.status).toBe('fresh')
    expect(reset.frequency).toBe(3)
  })

  it('recalls an error question', async () => {
    const recalled = await repo.recall(QUESTION_ID)

    expect(recalled.status).toBe('practicing')
    expect(recalled.frequency).toBe(2)
    expect(recalled.last_practiced_at).toBe('2026-06-13T00:05:00Z')
  })
})

describe('MockErrorQuestionRepository', () => {
  it('recalls a mock error question', async () => {
    const repo = new MockErrorQuestionRepository()
    const created = await repo.create({
      question_text: 'Mock recall',
      dimension: 'algorithm',
    })

    const recalled = await repo.recall(created.id)

    expect(recalled.status).toBe('practicing')
    expect(recalled.frequency).toBe(2)
    expect(recalled.last_practiced_at).toBeTruthy()
  })

  it('rejects recall for already mastered mock questions', async () => {
    const repo = new MockErrorQuestionRepository()
    const created = await repo.create({
      question_text: 'Mock mastered recall',
      dimension: 'algorithm',
    })
    await repo.patch(created.id, { status: 'mastered', frequency: 0 })

    await expect(repo.recall(created.id)).rejects.toThrow('already mastered')
  })
})
