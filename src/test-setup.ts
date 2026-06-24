/**
 * Vitest setup — runs before each test file.
 * - Imports `@testing-library/jest-dom` for `toBeInTheDocument` etc.
 * - Stubs env so token-storage + repositories operate in HTTP mode
 *   (which then routes to MSW handlers).
 */
import '@testing-library/jest-dom/vitest'
import { vi } from 'vitest'

// 027 US6: monaco-editor's clipboard module probes document.queryCommandSupported
// during contribution registration. jsdom lacks this API; polyfill it.
if (typeof document !== 'undefined' && !document.queryCommandSupported) {
  document.queryCommandSupported = () => true
}

// env must be mocked BEFORE any module that imports it loads.
vi.mock('./api/env', async () => {
  return {
    env: {
      USE_MOCK: false,
      API_BASE_URL: 'http://localhost:8000',
      WS_URL: 'ws://localhost:8000',
    },
    newRequestId: () => 'test-request-id',
  }
})

// MSW Node server — set up per test file via handlers.
import { beforeAll, afterAll, afterEach } from 'vitest'
import { setupServer } from 'msw/node'
import { handlers } from '../tests/msw/handlers'

const server = setupServer(...handlers)
beforeAll(() => server.listen({ onUnhandledRequest: 'warn' }))
afterEach(() => {
  server.resetHandlers()
  vi.clearAllMocks()
})
afterAll(() => server.close())
