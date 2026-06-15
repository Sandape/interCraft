/**
 * Playwright E2E configuration. Spins up the Vite dev server and the
 * FastAPI backend (assumed already running) before running specs.
 */
import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './',
  timeout: 60_000,
  retries: 0,
  reporter: 'list',
  use: {
    baseURL: 'http://localhost:5173',
    trace: 'on-first-retry',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: [
    {
      command: 'npm run dev',
      url: 'http://localhost:5173',
      reuseExistingServer: true,
      timeout: 60_000,
    },
  ],
})
