import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { expectMarkdownEditor, pasteMarkdown } from "./fixtures/049-markdown-editor-cutover/fixture";

const fixtureDir = join(process.cwd(), "tests/e2e/fixtures/049-markdown-editor-cutover");
const contactMarkdown = readFileSync(join(fixtureDir, "contact-format-lab.md"), "utf8");
const longMarkdown = readFileSync(join(fixtureDir, "long-three-page.md"), "utf8");
const legacyStructured = JSON.parse(
  readFileSync(join(fixtureDir, "legacy-structured-resume.json"), "utf8"),
);

const markdownSettings = {
  sourceMarkdown: contactMarkdown,
  themeId: "muji-default-autumn",
  manualLineHeight: 19,
  smartOnePageEnabled: false,
  smartLineHeight: null,
  previousManualLineHeight: null,
  smartStatus: "idle",
  paginationState: "idle",
  pageCount: 1,
  legacyConversionStatus: "not_needed",
  legacyConversionWarnings: [],
};

function resumeData(sourceMarkdown = contactMarkdown) {
  return {
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
    basics: {
      name: "REQ-049 Resume",
      headline: "",
      email: "",
      phone: "",
      location: "",
      website: { url: "", label: "" },
      customFields: [],
    },
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
      page: {
        gapX: 16,
        gapY: 16,
        marginX: 32,
        marginY: 32,
        format: "a4",
        locale: "zh-CN",
        hideLinkUnderline: false,
        hideIcons: false,
        hideSectionIcons: true,
      },
      design: {
        level: { icon: "circle", type: "circle" },
        colors: {
          primary: "rgba(0, 0, 0, 1)",
          text: "rgba(0, 0, 0, 1)",
          background: "rgba(255, 255, 255, 1)",
        },
      },
      typography: {
        body: { fontFamily: "Inter", fontWeights: ["400"], fontSize: 11, lineHeight: 1.5 },
        heading: { fontFamily: "Inter", fontWeights: ["700"], fontSize: 14, lineHeight: 1.3 },
      },
      notes: "",
      styleRules: [],
      markdown: {
        ...markdownSettings,
        sourceMarkdown,
      },
    },
  };
}

function resumePayload(id: string, sourceMarkdown = contactMarkdown) {
  return {
    id,
    user_id: "u-049",
    name: "REQ-049 Resume",
    slug: id,
    tags: [],
    is_public: false,
    is_locked: false,
    password_set: false,
    version: 1,
    created_at: null,
    updated_at: null,
    data: resumeData(sourceMarkdown),
  };
}

test.describe("REQ-049 Markdown editor cutover", () => {
  let resumes: Map<string, ReturnType<typeof resumePayload>>;
  let exportBody: Record<string, unknown> | null;
  let legacyPutBody: { data?: Record<string, unknown> } | null;

  test.beforeEach(async ({ page }) => {
    exportBody = null;
    legacyPutBody = null;
    resumes = new Map([
      ["r-049", resumePayload("r-049")],
      [
        "legacy-structured",
        {
          ...resumePayload("legacy-structured", ""),
          slug: "legacy-structured",
          data: legacyStructured,
        },
      ],
    ]);

    await page.addInitScript(() => {
      sessionStorage.setItem("ic.access_token", "e2e-token");
      sessionStorage.setItem("ic.refresh_token", "e2e-refresh");
      localStorage.setItem("access_token", "e2e-token");
    });

    await page.route("**/api/v1/users/me", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ id: "u-049", email: "e2e@example.com", display_name: "E2E" }),
      });
    });

    await page.route("**/api/v1/v2/export/render", async (route) => {
      exportBody = route.request().postDataJSON() as Record<string, unknown>;
      await route.fulfill({
        status: 200,
        contentType: "application/pdf",
        headers: { "content-disposition": 'attachment; filename="req-049.pdf"' },
        body: "%PDF-1.4\nreq-049",
      });
    });

    await page.route("**/api/v1/v2/resumes/*", async (route) => {
      const url = new URL(route.request().url());
      const id = url.pathname.split("/").filter(Boolean).at(-1) ?? "";
      const current = resumes.get(id);
      if (!current) {
        await route.fulfill({ status: 404, contentType: "application/json", body: "{}" });
        return;
      }

      if (route.request().method() === "PUT") {
        const body = route.request().postDataJSON() as { data: Record<string, unknown> };
        if (id === "legacy-structured") legacyPutBody = body;
        const next = {
          ...current,
          data: body.data,
          version: current.version + 1,
        };
        resumes.set(id, next);
        await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(next) });
        return;
      }

      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(current) });
    });
  });

  test("stale v2 editor links redirect to the Markdown editor shell", async ({ page }) => {
    await page.goto("/resume/v2/r-049", { waitUntil: "domcontentloaded" });

    await expect(page).toHaveURL(/\/resume\/r-049$/);
    await expectMarkdownEditor(page);
    await expect(page.getByTestId("v2-editor")).toHaveAttribute("data-markdown-cutover", "true");
    await expect(page.getByTestId("legacy-open-v1")).toHaveCount(0);
  });

  test("contact blocks keep semantic rows across themes and PDF payload", async ({ page }) => {
    await page.goto("/resume/r-049", { waitUntil: "domcontentloaded" });
    await expectMarkdownEditor(page);

    await expect(page.locator(".resume-contact-row")).toHaveCount(7);
    await expect(page.locator('.resume-contact-icon[data-contact-icon-status="fallback"]')).toBeVisible();

    for (const theme of ["muji-default-autumn", "muji-minimal-color", "muji-flat-atmospheric"]) {
      await page.getByTestId("theme-menu").selectOption(theme);
      await expect(page.getByTestId("markdown-preview-page").first()).toHaveAttribute("data-theme", theme);
      await page.screenshot({
        path: `docs/evidence/049-markdown-editor-cutover/contact-${theme}.png`,
        fullPage: true,
      });
    }

    const [pdfDownload] = await Promise.all([
      page.waitForEvent("download"),
      page.getByTestId("export-pdf-option").click(),
    ]);
    await pdfDownload.saveAs("docs/evidence/049-markdown-editor-cutover/contact-export.pdf");

    expect(exportBody?.format).toBe("pdf");
    expect(String(exportBody?.html)).toContain("resume-contact-row");
    expect(exportBody?.pagination_state).toBe("paginated");
    expect(exportBody?.preview_page_count).toBe(1);
  });

  test("long Markdown paginates, reports smart one-page fallback, and exports all pages", async ({ page }) => {
    await page.goto("/resume/r-049", { waitUntil: "domcontentloaded" });
    await expectMarkdownEditor(page);

    await pasteMarkdown(page, longMarkdown);
    await expect
      .poll(async () => Number(await page.getByTestId("markdown-preview-pages").getAttribute("data-page-count")))
      .toBeGreaterThanOrEqual(3);

    const initialPageCount = Number(await page.getByTestId("markdown-preview-pages").getAttribute("data-page-count"));
    await expect(page.getByTestId("markdown-preview-page")).toHaveCount(initialPageCount);
    const overflowDeltas = await page.getByTestId("markdown-preview-page").evaluateAll((pages) =>
      pages.map((pageElement) => {
        const content = pageElement.querySelector<HTMLElement>(".resume-page-content");
        return content ? content.scrollHeight - content.clientHeight : 0;
      }),
    );
    expect(Math.max(...overflowDeltas)).toBeLessThanOrEqual(8);

    await page.getByTestId("smart-one-page-toggle").click();
    await expect(page.getByTestId("smart-one-page-feedback")).toBeVisible();
    await expect
      .poll(async () => Number(await page.getByTestId("markdown-preview-pages").getAttribute("data-page-count")))
      .toBeGreaterThanOrEqual(3);
    const pageCount = Number(await page.getByTestId("markdown-preview-pages").getAttribute("data-page-count"));
    await expect(page.getByTestId("markdown-preview-page")).toHaveCount(pageCount);

    await page.screenshot({
      path: "docs/evidence/049-markdown-editor-cutover/long-pagination.png",
      fullPage: true,
    });

    await expect(page.getByTestId("export-pdf-option")).toBeEnabled();
    const [pdfDownload] = await Promise.all([
      page.waitForEvent("download"),
      page.getByTestId("export-pdf-option").click(),
    ]);
    await pdfDownload.saveAs("docs/evidence/049-markdown-editor-cutover/long-pagination-export.pdf");

    expect(exportBody?.format).toBe("pdf");
    expect(exportBody?.preview_page_count).toBe(pageCount);
    expect(String(exportBody?.html)).toContain("data-page-number");
    expect(String(exportBody?.html)).toContain("Page-aware rendering must preserve this bullet.");
    expect(String(exportBody?.html)).toContain("Final third-page sentinel must survive preview and PDF export payload.");
  });

  test("structured-only legacy resumes open as Markdown and persist converted source", async ({ page }) => {
    await page.goto("/resume/legacy-structured", { waitUntil: "domcontentloaded" });

    await expectMarkdownEditor(page);
    await expect(page.getByTestId("legacy-conversion-status")).toBeVisible();
    await expect(page.getByTestId("markdown-source-editor")).toHaveValue(/# Legacy Lin/);
    await expect(page.getByTestId("markdown-source-editor")).toHaveValue(/Old Resume Co/);
    await expect(page.getByTestId("legacy-open-v1")).toHaveCount(0);

    await expect
      .poll(() => {
        const data = legacyPutBody?.data as { metadata?: { markdown?: { sourceMarkdown?: string } } } | undefined;
        return data?.metadata?.markdown?.sourceMarkdown ?? "";
      })
      .toContain("Legacy structured summary that must remain visible.");

    await page.screenshot({
      path: "docs/evidence/049-markdown-editor-cutover/legacy-converted.png",
      fullPage: true,
    });
  });
});
