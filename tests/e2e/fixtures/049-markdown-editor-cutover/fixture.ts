import { expect, type Page } from "@playwright/test";

export async function expectMarkdownEditor(page: Page) {
  await expect(page.getByTestId("markdown-source-editor")).toBeVisible();
  await expect(page.getByTestId("markdown-preview-page").first()).toBeVisible();
  await expect(page.getByTestId("export-pdf-option")).toBeVisible();
  await expect(page.getByTestId("template-gallery-button")).toHaveCount(0);
  await expect(page.getByTestId("right-tab-host")).toHaveCount(0);
}

export async function pasteMarkdown(page: Page, source: string) {
  await page.getByTestId("markdown-source-editor").fill(source);
  await expect(page.getByTestId("markdown-source-editor")).toHaveValue(source);
}
