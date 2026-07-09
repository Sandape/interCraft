import { test, expect } from "@playwright/test";

test("seed for custom + settings i18n audit", async ({ page }) => {
  const BACKEND = "http://localhost:8000";
  const FRONTEND = "http://localhost:5173";
  const loginRes = await page.request.post(`${BACKEND}/api/v1/auth/login`, {
    data: { email: "demo@intercraft.io", password: "Demo1234" },
  });
  const json = await loginRes.json();
  const token = json.tokens.access_token;
  const userId = json.user.id;
  await page.addInitScript(
    ({ token, userId }) => {
      const user = {
        id: userId,
        email: "demo@intercraft.io",
        display_name: "Demo",
        subscription: "free",
      };
      window.sessionStorage.setItem("ic.access_token", token);
      window.sessionStorage.setItem("ic.refresh_token", token);
      window.localStorage.setItem("access_token", token);
      window.localStorage.setItem("current_user", JSON.stringify(user));
    },
    { token, userId },
  );
  await page.goto(
    `${FRONTEND}/resume/019f156b-0239-7623-baa4-10bea3981f6f`,
  );
  await page.waitForSelector('[data-testid="v2-editor"]', { timeout: 45000 });
  await expect(page).toHaveURL(/resume\/019f156b-0239-7623-baa4-10bea3981f6f/);
});
