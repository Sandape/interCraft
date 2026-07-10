/**
 * Shared helpers for REQ-055/056 resume-root-derive Playwright specs.
 */
import { expect, type APIRequestContext, type Page } from "@playwright/test";
import { API_BASE } from "./round-1/fixtures/auth";

/** Client-side poll timeout for derive progress (SC-005 / US6). */
export const DERIVE_POLL_TIMEOUT_MS = 30_000;

export async function waitForRootSurface(page: Page) {
  await expect(page.getByTestId("resume-list-page")).toBeVisible({
    timeout: 15_000,
  });
  await expect(
    page
      .getByTestId("root-resume-empty")
      .or(page.getByTestId("root-resume-card")),
  ).toBeVisible({ timeout: 15_000 });
}

export async function ensureRootResume(
  request: APIRequestContext,
  token: string,
  name = "E2E Root",
) {
  const rootRes = await request.post(`${API_BASE}/api/v1/v2/resumes/root`, {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      name,
      slug: `root-${Date.now()}`,
      data: {
        basics: { name: "测试用户" },
        summary: { content: "Python backend" },
        sections: {},
        metadata: {},
      },
    },
  });
  expect([201, 409]).toContain(rootRes.status());
  return rootRes;
}
