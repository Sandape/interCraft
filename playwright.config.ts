import { defineConfig, devices } from '@playwright/test';

/**
 * Read environment variables from file.
 * https://github.com/motdotla/dotenv
 */
// import dotenv from 'dotenv';
// import path from 'path';
// dotenv.config({ path: path.resolve(__dirname, '.env') });

/**
 * See https://playwright.dev/docs/test-configuration.
 */
export default defineConfig({
  testDir: './tests/e2e',
  /* Run tests in files in parallel */
  fullyParallel: true,
  /* Fail the build on CI if you accidentally left test.only in the source code. */
  forbidOnly: !!process.env.CI,
  /* Retry on CI only */
  retries: process.env.CI ? 2 : 0,
  /* Opt out of parallel tests on CI. */
  workers: process.env.CI ? 1 : undefined,
  /* Reporter to use. See https://playwright.dev/docs/test-reporters */
  reporter: [['list'], ['json', { outputFile: 'test-results/round-1-results.json' }], ['html', { outputFolder: 'test-results/html-report', open: 'never' }]],
  /* Shared settings for all the projects below. See https://playwright.dev/docs/api/class-testoptions. */
  use: {
    /* Base URL for `page.goto('/login')` and friends. */
    baseURL: process.env.E2E_BASE_URL ?? 'http://localhost:5173',

    /* Collect trace, video, and screenshot for every test (preserved for evidence) */
    trace: 'on',
    video: 'retain-on-failure',
    screenshot: 'on',
  },

  /* Preserve test output even on success (for evidence/audit) */
  outputDir: './test-results/output',
  /* Video dir under tests/e2e/ (per spec: D:\Project\eGGG\tests\e2e\videos) */
  // video path is configured via use.video; default location is test-results/

  /* Configure projects for major browsers */
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },

    {
      name: 'firefox',
      use: { ...devices['Desktop Firefox'] },
    },

    {
      name: 'webkit',
      use: { ...devices['Desktop Safari'] },
    },

    /* Test against mobile viewports. */
    // {
    //   name: 'Mobile Chrome',
    //   use: { ...devices['Pixel 5'] },
    // },
    // {
    //   name: 'Mobile Safari',
    //   use: { ...devices['iPhone 12'] },
    // },

    /* Test against branded browsers. */
    // {
    //   name: 'Microsoft Edge',
    //   use: { ...devices['Desktop Edge'], channel: 'msedge' },
    // },
    // {
    //   name: 'Google Chrome',
    //   use: { ...devices['Desktop Chrome'], channel: 'chrome' },
    // },
  ],

  /* Run your local dev server before starting the tests.
     REQ-048 verification: backend (8001) + frontend (5173) already running
     externally (started via ``uvicorn`` and Vite). Playwright skips its own
     webServer startup by commenting this block out; tests use the existing
     frontend on http://127.0.0.1:5173. */
  // webServer: { ... disabled for REQ-048 manual verification ... },
});
