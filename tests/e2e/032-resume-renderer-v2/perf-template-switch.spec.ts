/**
 * T188 — Verify SC-002: template switch latency < 1s.
 *
 * Playwright perf trace test: measure time from gallery card click to
 * preview re-render across all 10 templates. Assert p95 < 1000ms.
 *
 * Skip-if-down: returns early if backend is not reachable. The test is
 * tagged so CI can collect it as "skip" rather than "fail".
 */
import { test, expect, type Page } from "@playwright/test";

const FRONTEND = process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:5173";
const BACKEND = process.env.PLAYWRIGHT_API_BASE ?? "http://127.0.0.1:8000";

const TEMPLATE_IDS = [
  "onyx",
  "azurill",
  "kakuna",
  "chikorita",
  "ditgar",
  "bronzor",
  "pikachu",
  "lapras",
  "scizor",
  "rhyhorn",
];

async function isBackendUp(): Promise<boolean> {
  try {
    const res = await fetch(`${BACKEND}/api/v1/openapi.json`);
    return res.ok || res.status < 500;
  } catch {
    return false;
  }
}

async function registerAndCreateV2Resume(page: Page): Promise<string> {
  const stamp = Date.now();
  const email = `e2e032sc002-${stamp}@example.com`;
  const password = "Demo1234";

  await page.goto(`${FRONTEND}/register`);
  await page.fill('input[name="email"]', email);
  await page.fill('input[name="password"]', password);
  await page.click('button[type="submit"]');
  await page.waitForURL(/\/(dashboard|resumes|$)/, { timeout: 15000 });

  // Login to obtain Bearer token (v2 API requires JWT, not cookie session)
  const loginRes = await page.request.post(`${BACKEND}/api/v1/auth/login`, {
    data: { email, password },
  });
  expect(loginRes.status(), `POST /auth/login → ${loginRes.status()}`).toBeLessThan(400);
  const loginBody = (await loginRes.json()) as { tokens?: { access_token?: string } };
  const token = loginBody.tokens?.access_token;
  if (!token) throw new Error("No access_token returned from POST /auth/login");

  // Create a v2 resume via the API directly (faster than UI).
  const createRes = await page.request.post(`${BACKEND}/api/v1/v2/resumes`, {
    headers: { Authorization: `Bearer ${token}` },
    data: { name: "SC-002 perf", slug: `sc002-${stamp}`, template: "pikachu", from_sample: true },
  });
  expect(createRes.ok()).toBeTruthy();
  const body = await createRes.json();
  return body.resume?.id ?? body.id;
}

test.describe("SC-002: template switch < 1s (p95)", () => {
  test.beforeAll(async () => {
    if (!(await isBackendUp())) {
      test.skip(true, "Backend not reachable — skipping SC-002 perf trace.");
    }
  });

  test("switches all 10 templates within p95 < 1000ms", async ({ page }) => {
    if (!(await isBackendUp())) {
      test.skip(true, "Backend not reachable — skipping SC-002.");
      return;
    }
    const resumeId = await registerAndCreateV2Resume(page);
    await page.goto(`${FRONTEND}/resume/v2/${resumeId}`);

    // Wait for preview to be visible
    await page.waitForSelector('[data-template-id]', { timeout: 10000 });

    const samples: number[] = [];
    for (const tpl of TEMPLATE_IDS) {
      // Open template gallery
      const t0 = performance.now();
      await page.click('[data-testid="template-gallery-button"]');
      await page.waitForSelector('[data-template-gallery]', { timeout: 5000 });
      // Click the template card
      await page.click(`[data-template-id="${tpl}"]`);
      // Wait for preview to reflect the new template
      await page.waitForFunction(
        (id) => {
          const preview = document.querySelector("[data-template-id]");
          return preview?.getAttribute("data-template-id") === id;
        },
        tpl,
        { timeout: 5000 },
      );
      const t1 = performance.now();
      samples.push(t1 - t0);
    }

    // p95 < 1000ms
    samples.sort((a, b) => a - b);
    const p95 = samples[Math.floor(samples.length * 0.95) - 1] ?? samples[samples.length - 1];
    console.log(`SC-002 template-switch samples (ms): ${samples.join(", ")}; p95=${p95}`);
    expect(p95).toBeLessThan(1000);
  });
});