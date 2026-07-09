import { expect, type APIRequestContext, type Page, type TestInfo } from '@playwright/test'

export const FRONTEND_BASE = process.env.E2E_FRONTEND_BASE ?? 'http://127.0.0.1:5305'
export const BACKEND_BASE = process.env.E2E_BACKEND_BASE ?? 'http://127.0.0.1:8205'

const DEMO_EMAIL = 'demo@intercraft.io'
const DEMO_PASSWORD = 'Demo1234'

export async function backendReachable(
  request: APIRequestContext,
  healthPath = '/api/v1/admin-console/command-center/health',
): Promise<boolean> {
  try {
    const res = await request.get(`${BACKEND_BASE}${healthPath}`, { timeout: 3_000 })
    return res.ok()
  } catch {
    return false
  }
}

export async function requireBackend(
  request: APIRequestContext,
  testInfo: TestInfo,
  healthPath?: string,
): Promise<boolean> {
  if (await backendReachable(request, healthPath)) return true
  testInfo.skip(true, `INFRA-BLOCKED: backend at ${BACKEND_BASE} not reachable`)
  return false
}

export async function loginAsDemo(
  page: Page,
  request: APIRequestContext,
  role = 'pm',
): Promise<void> {
  const res = await request.post(`${BACKEND_BASE}/api/v1/auth/login`, {
    data: { email: DEMO_EMAIL, password: DEMO_PASSWORD },
  })
  expect(res.status(), `POST /auth/login -> ${res.status()}`).toBeLessThan(400)
  const body = await res.json()
  const tokens = body.tokens as { access_token: string; refresh_token: string }

  await page.addInitScript(
    ({ access, refresh, roleName }) => {
      window.sessionStorage.setItem('ic.access_token', access)
      window.sessionStorage.setItem('ic.refresh_token', refresh)
      window.localStorage.setItem('access_token', access)
      window.localStorage.setItem(
        'auth-user',
        JSON.stringify({ email: 'demo@intercraft.io', role: roleName }),
      )
    },
    { access: tokens.access_token, refresh: tokens.refresh_token, roleName: role },
  )
}

export async function setAdminRole(page: Page, role: string): Promise<void> {
  await page.addInitScript((roleName) => {
    window.localStorage.setItem(
      'auth-user',
      JSON.stringify({ email: 'demo@intercraft.io', role: roleName }),
    )
  }, role)
}
