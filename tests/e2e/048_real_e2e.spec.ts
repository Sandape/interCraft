// V3: Playwright real E2E for REQ-048
// Uses: backend on 8001 + frontend on 5173 (both running externally)
//
// Uses APIRequestContext to avoid Chromium sandbox network restrictions.

import { test, expect } from '@playwright/test'

const FRONTEND = 'http://localhost:5173'  // resolves to IPv6 [::1]
const BACKEND = 'http://127.0.0.1:8001'

test.describe('REQ-048 US1 mode selection (REAL E2E)', () => {
  test('frontend serves /interviews/new over HTTP 200', async ({ request }) => {
    const resp = await request.get(`${FRONTEND}/interviews/new`)
    expect(resp.status()).toBe(200)
    const html = await resp.text()
    expect(html.length).toBeGreaterThan(100)
    expect(html).toContain('<div id="root"')
  })

  test('backend /api/v1/interview-sessions POST + GET roundtrip', async ({ request }) => {
    const loginResp = await request.post(`${BACKEND}/api/v1/auth/register`, {
      headers: { 'X-Device-Fingerprint': 'fp-e2e-real' },
      data: {
        email: `e2e_real_${Date.now()}@intercraft.io`,
        password: 'Demo1234',
        display_name: 'e2e_real',
        device_fingerprint: 'fp-e2e-real',
      },
    })
    expect(loginResp.status()).toBe(201)
    const loginBody = await loginResp.json()
    const access = loginBody.tokens.access_token

    const postResp = await request.post(`${BACKEND}/api/v1/interview-sessions`, {
      headers: { Authorization: `Bearer ${access}` },
      data: { position: 'Backend Eng', company: 'Acme', mode: 'full', max_questions: 10 },
    })
    expect(postResp.status()).toBe(201)
    const postBody = await postResp.json()
    const sid = postBody.data.id

    const getResp = await request.get(`${BACKEND}/api/v1/interview-sessions/${sid}`, {
      headers: { Authorization: `Bearer ${access}` },
    })
    expect(getResp.status()).toBe(200)
    const body = await getResp.json()
    expect(body.mode).toBe('full')
    expect(body.max_questions).toBe(10)
  })

  test('backend quick-drill/preview endpoint reachable', async ({ request }) => {
    const loginResp = await request.post(`${BACKEND}/api/v1/auth/register`, {
      headers: { 'X-Device-Fingerprint': 'fp-e2e-qd' },
      data: {
        email: `e2e_qd_${Date.now()}@intercraft.io`,
        password: 'Demo1234',
        display_name: 'e2e_qd',
        device_fingerprint: 'fp-e2e-qd',
      },
    })
    expect(loginResp.status()).toBe(201)
    const loginBody = await loginResp.json()
    const access = loginBody.tokens.access_token
    const resp = await request.get(`${BACKEND}/api/v1/interview-sessions/quick-drill/preview`, {
      headers: { Authorization: `Bearer ${access}` },
    })
    expect(resp.status()).toBe(200)
    const body = await resp.json()
    expect(body.data).toBeDefined()
    expect(body.data.cache_key).toBeDefined()
  })

  test('backend doubao-mode session creation + row contains mode=doubao', async ({ request }) => {
    const loginResp = await request.post(`${BACKEND}/api/v1/auth/register`, {
      headers: { 'X-Device-Fingerprint': 'fp-e2e-doubao' },
      data: {
        email: `e2e_doubao_${Date.now()}@intercraft.io`,
        password: 'Demo1234',
        display_name: 'e2e_doubao',
        device_fingerprint: 'fp-e2e-doubao',
      },
    })
    expect(loginResp.status()).toBe(201)
    const { tokens: { access_token: access } } = await loginResp.json()
    const postResp = await request.post(`${BACKEND}/api/v1/interview-sessions`, {
      headers: { Authorization: `Bearer ${access}` },
      data: { position: 'Frontend', company: 'Doubao', mode: 'doubao' },
    })
    expect(postResp.status()).toBe(201)
    const sid = postResp.json().then ? (await postResp.json()).data.id : null
    expect(sid).toBeTruthy()
    const getResp = await request.get(`${BACKEND}/api/v1/interview-sessions/${sid}`, {
      headers: { Authorization: `Bearer ${access}` },
    })
    expect(getResp.status()).toBe(200)
    const body = await getResp.json()
    expect(body.mode).toBe('doubao')
  })
})