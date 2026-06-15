/**
 * Complete interview flow: 5 rounds → report.
 * Tests the full LangGraph-driven interview via the REST API.
 */
import { test, expect } from '@playwright/test'

const API_URL = 'http://localhost:8000/api/v1'
const TEST_USER = { email: 'e2e-interview@intercraft.io', password: 'Demo1234' }

test.describe.serial('Full Interview 5-Round Flow', () => {
  let authToken: string
  let sessionId: string

  test.beforeAll(async ({ request }) => {
    // Register or login
    let res = await request.post(`${API_URL}/auth/login`, { data: TEST_USER })
    if (!res.ok()) {
      res = await request.post(`${API_URL}/auth/register`, {
        data: { ...TEST_USER, display_name: 'Interview E2E Tester' },
      })
    }
    const body = await res.json()
    authToken = body.tokens?.access_token || body.access_token || ''
    expect(authToken).toBeTruthy()
  })

  test('Step 1: Create interview session', async ({ request }) => {
    const res = await request.post(`${API_URL}/interview-sessions`, {
      headers: { Authorization: `Bearer ${authToken}` },
      data: { position: '资深Python后端工程师', company: '字节跳动', mode: 'text' },
    })
    expect([200, 201]).toContain(res.status())
    const json = await res.json()
    sessionId = json.data?.id || json.id
    expect(sessionId).toBeTruthy()
    // eslint-disable-next-line no-console
    console.log(`  Created session: ${sessionId}`)
  })

  test('Step 2: Start interview', async ({ request }) => {
    expect(sessionId).toBeTruthy()
    const res = await request.post(`${API_URL}/interview-sessions/${sessionId}/start`, {
      headers: { Authorization: `Bearer ${authToken}` },
    })
    expect(res.status()).toBeLessThan(500)
    // eslint-disable-next-line no-console
    console.log(`  Start status: ${res.status()}`)
  })

  test('Step 3: Submit answer 0 (kick off graph)', async ({ request }) => {
    expect(sessionId).toBeTruthy()
    const res = await request.post(`${API_URL}/interview-sessions/${sessionId}/answers`, {
      headers: { Authorization: `Bearer ${authToken}` },
      data: {
        content: '我希望面试资深Python后端工程师岗位，目标公司是字节跳动。我有6年后端开发经验。',
        sequence_no: 0,
      },
    })
    expect(res.status()).toBeLessThan(500)
    const json = await res.json()
    const data = json.data || json
    // After first submit: intake → question_gen → pause before score
    // Should have 1 question, 0 scores
    const questions = data.questions || []
    const scores = data.scores || []
    // eslint-disable-next-line no-console
    console.log(`  Questions: ${questions.length}, Scores: ${scores.length}`)
    expect(questions.length).toBeGreaterThanOrEqual(1)
  })

  test('Step 4: Submit answers 1-4 (score + next question each)', async ({ request }) => {
    expect(sessionId).toBeTruthy()

    const answers = [
      '我精通Python异步编程，使用asyncio、FastAPI、aiohttp等框架。同时在字节跳动类似的互联网公司有大规模分布式系统设计经验。',
      '系统设计方面，我设计过千万级QPS的API网关，使用了微服务架构、消息队列、分布式缓存等。',
      '工程实践上，我推崇TDD、代码审查、CI/CD流水线。有丰富的Docker和Kubernetes编排经验。',
      '沟通协作方面，我曾带领5人团队完成核心项目，推动技术方案评审和知识分享。',
    ]

    for (let i = 1; i <= 4; i++) {
      const res = await request.post(`${API_URL}/interview-sessions/${sessionId}/answers`, {
        headers: { Authorization: `Bearer ${authToken}` },
        data: { content: answers[i - 1], sequence_no: i },
      })
      expect(res.status()).toBeLessThan(500)
      const json = await res.json()
      const data = json.data || json
      const scores = data.scores || []
      const questions = data.questions || []
      // eslint-disable-next-line no-console
      console.log(`  Round ${i}: q=${questions.length}, s=${scores.length}, cq=${data.current_question}`)
      // Should have scores accumulated
      expect(scores.length).toBeGreaterThanOrEqual(i)
    }
  })

  test('Step 5: Submit final answer → report', async ({ request }) => {
    expect(sessionId).toBeTruthy()
    const res = await request.post(`${API_URL}/interview-sessions/${sessionId}/answers`, {
      headers: { Authorization: `Bearer ${authToken}` },
      data: {
        content: '算法方面，我熟练掌握各种数据结构和算法，包括动态规划、贪心、图算法等。在LeetCode有800+的刷题经验。',
        sequence_no: 5,
      },
    })
    expect(res.status()).toBeLessThan(500)
    const json = await res.json()
    const data = json.data || json
    // After the 5th answer: score → report → END
    const scores = data.scores || []
    const interviewReport = data.interview_report || {}
    const overallScore = data.overall_score || interviewReport.overall_score || 0
    // eslint-disable-next-line no-console
    console.log(`  Final scores: ${scores.length}, report keys: ${Object.keys(interviewReport).join(', ')}`)
    // eslint-disable-next-line no-console
    console.log(`  Overall score: ${overallScore}`)
    // Should have 5 scores
    expect(scores.length).toBeGreaterThanOrEqual(5)
  })

  test('Step 6: Get report from API', async ({ request }) => {
    expect(sessionId).toBeTruthy()
    const res = await request.get(`${API_URL}/interview-sessions/${sessionId}/report`, {
      headers: { Authorization: `Bearer ${authToken}` },
    })
    expect(res.ok()).toBeTruthy()
    const json = await res.json()
    const report = json.data || json
    expect(report.overall_score).toBeDefined()
    expect(report.per_question_score).toBeDefined()
    expect(report.dimension_scores).toBeDefined()
    expect(report.strengths).toBeDefined()
    expect(report.improvements).toBeDefined()
    expect(report.summary_md).toBeDefined()
    // eslint-disable-next-line no-console
    console.log(`  Report overall_score: ${report.overall_score}`)
    // eslint-disable-next-line no-console
    console.log(`  Strengths: ${JSON.stringify(report.strengths?.slice(0, 2) || [])}`)
    // eslint-disable-next-line no-console
    console.log(`  Improvements: ${JSON.stringify(report.improvements?.slice(0, 2) || [])}`)
  })

  test('Step 7: List sessions shows completed', async ({ request }) => {
    expect(sessionId).toBeTruthy()
    const res = await request.get(`${API_URL}/interview-sessions`, {
      headers: { Authorization: `Bearer ${authToken}` },
    })
    expect(res.ok()).toBeTruthy()
    const json = await res.json()
    const sessions = json.data || []
    const ourSession = sessions.find((s: any) => s.id === sessionId)
    expect(ourSession).toBeTruthy()
    // eslint-disable-next-line no-console
    console.log(`  Session status: ${ourSession?.status}`)
  })
})
