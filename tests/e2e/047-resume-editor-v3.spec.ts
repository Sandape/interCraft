import { test, expect } from "@playwright/test";
import { formatLabMarkdown } from "./fixtures/047-resume-editor-v3/format-lab-inline";

const resumePayload = {
  id: "r-047",
  user_id: "u-047",
  name: "REQ-047 Demo",
  slug: "req-047-demo",
  tags: [],
  is_public: false,
  is_locked: false,
  password_set: false,
  version: 1,
  created_at: null,
  updated_at: null,
  data: {
    picture: {
      hidden: true,
      url: "",
      size: 96,
      rotation: 0,
      aspectRatio: 1,
      borderRadius: 0,
      borderColor: "rgba(0, 0, 0, 1)",
      borderWidth: 0,
      shadowColor: "rgba(0, 0, 0, 0)",
      shadowWidth: 0,
    },
    basics: { name: "林溪", headline: "", email: "", phone: "", location: "", website: { url: "", label: "" }, customFields: [] },
    summary: { title: "Summary", icon: "user", columns: 1, hidden: false, content: "" },
    sections: {
      profiles: { title: "Profiles", icon: "user", columns: 1, hidden: false, items: [] },
      experience: { title: "Experience", icon: "briefcase", columns: 1, hidden: false, items: [] },
      education: { title: "Education", icon: "graduation-cap", columns: 1, hidden: false, items: [] },
      projects: { title: "Projects", icon: "folder", columns: 1, hidden: false, items: [] },
      skills: { title: "Skills", icon: "wrench", columns: 1, hidden: false, items: [] },
      languages: { title: "Languages", icon: "languages", columns: 1, hidden: false, items: [] },
      interests: { title: "Interests", icon: "heart", columns: 1, hidden: false, items: [] },
      awards: { title: "Awards", icon: "trophy", columns: 1, hidden: false, items: [] },
      certifications: { title: "Certifications", icon: "badge-check", columns: 1, hidden: false, items: [] },
      publications: { title: "Publications", icon: "book", columns: 1, hidden: false, items: [] },
      volunteer: { title: "Volunteer", icon: "hand-heart", columns: 1, hidden: false, items: [] },
      references: { title: "References", icon: "users", columns: 1, hidden: false, items: [] },
    },
    customSections: [],
    metadata: {
      template: "onyx",
      layout: { sidebarWidth: 30, pages: [{ fullWidth: false, main: [], sidebar: [] }] },
      page: { gapX: 16, gapY: 16, marginX: 32, marginY: 32, format: "a4", locale: "zh-CN", hideLinkUnderline: false, hideIcons: false, hideSectionIcons: true },
      design: { level: { icon: "circle", type: "circle" }, colors: { primary: "rgba(0, 0, 0, 1)", text: "rgba(0, 0, 0, 1)", background: "rgba(255, 255, 255, 1)" } },
      typography: { body: { fontFamily: "Inter", fontWeights: ["400"], fontSize: 11, lineHeight: 1.5 }, heading: { fontFamily: "Inter", fontWeights: ["700"], fontSize: 14, lineHeight: 1.3 } },
      notes: "",
      styleRules: [],
      markdown: {
        sourceMarkdown: formatLabMarkdown,
        themeId: "muji-default-autumn",
        manualLineHeight: 19,
        smartOnePageEnabled: false,
        smartLineHeight: null,
        previousManualLineHeight: null,
        smartStatus: "idle",
      },
    },
  },
};

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    sessionStorage.setItem("ic.access_token", "e2e-token");
    sessionStorage.setItem("ic.refresh_token", "e2e-refresh");
    localStorage.setItem("access_token", "e2e-token");
  });

  await page.route("**/api/v1/users/me", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ id: "u-047", email: "e2e@example.com", display_name: "E2E" }) });
  });
  await page.route("**/api/v1/v2/resumes/r-047", async (route) => {
    if (route.request().method() === "PUT") {
      const body = route.request().postDataJSON();
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ ...resumePayload, data: body.data, version: 2 }) });
      return;
    }
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(resumePayload) });
  });
  await page.route("**/api/v1/v2/export/render", async (route) => {
    const body = route.request().postDataJSON();
    expect(body.format).toBe("pdf");
    expect(body.html).toContain("markdown-resume-preview");
    await route.fulfill({
      status: 200,
      contentType: "application/pdf",
      headers: { "content-disposition": "attachment; filename=\"req-047.pdf\"" },
      body: "%PDF-1.4\nreq-047",
    });
  });
});

test("REQ-047 full simulated browser acceptance", async ({ page }) => {
  await page.goto("/resume/r-047", { waitUntil: "domcontentloaded" });

  await expect(page.getByTestId("markdown-source-editor")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByTestId("markdown-preview-page")).toContainText("林溪 - Markdown 渲染测试");
  await expect(page.getByTestId("markdown-preview-page").locator("table")).toBeVisible();
  await expect(page.getByTestId("markdown-preview-page")).toContainText("[x] 已完成任务项");

  const originalSource = await page.getByTestId("markdown-source-editor").inputValue();
  await page.getByTestId("theme-menu").selectOption("muji-minimal-color");
  await expect(page.getByTestId("markdown-preview-page")).toHaveAttribute("data-theme", "muji-minimal-color");
  expect(await page.getByTestId("markdown-source-editor").inputValue()).toBe(originalSource);

  await page.getByTestId("theme-menu").selectOption("muji-flat-atmospheric");
  await expect(page.getByTestId("markdown-preview-page")).toHaveAttribute("data-theme", "muji-flat-atmospheric");

  await page.getByTestId("line-spacing-control").selectOption("12");
  await expect(page.getByTestId("markdown-preview-page")).toHaveClass(/height12/);

  await page.getByTestId("smart-one-page-toggle").click();
  await expect(page.getByTestId("smart-one-page-status")).toContainText(/已适配一页|压缩到一页|无法压缩到一页/);

  const [mdDownload] = await Promise.all([
    page.waitForEvent("download"),
    page.getByTestId("export-markdown-option").click(),
  ]);
  expect(mdDownload.suggestedFilename()).toContain(".md");
  await mdDownload.saveAs("docs/evidence/047-resume-editor-v3/req-047-export.md");

  const [pdfDownload] = await Promise.all([
    page.waitForEvent("download"),
    page.getByTestId("export-pdf-option").click(),
  ]);
  expect(pdfDownload.suggestedFilename()).toContain(".pdf");
  await pdfDownload.saveAs("docs/evidence/047-resume-editor-v3/req-047-export.pdf");

  await page.screenshot({
    path: "docs/evidence/047-resume-editor-v3/req-047-chromium-final.png",
    fullPage: true,
  });
});
