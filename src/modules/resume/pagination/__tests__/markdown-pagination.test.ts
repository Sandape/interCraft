import { describe, expect, it } from "vitest";
import { renderMarkdown } from "@/modules/resume/renderer";
import { paginateMarkdownHtml } from "../markdown-pages";

describe("markdown preview pagination", () => {
  it("splits rendered blocks into ordered pages", () => {
    const html = Array.from({ length: 10 })
      .map((_, index) => `<h2>Section ${index + 1}</h2><p>${"Long content ".repeat(18)}</p>`)
      .join("");

    const result = paginateMarkdownHtml({
      html,
      lineHeight: 19,
      pageContentHeightPx: 220,
    });

    expect(result.pageCount).toBeGreaterThan(1);
    expect(result.pages[0].pageNumber).toBe(1);
    expect(result.pages.at(-1)?.pageNumber).toBe(result.pageCount);
    expect(result.pages.map((page) => page.html).join("")).toContain("Section 10");
  });

  it("continues producing pages after page 2 for a long paragraph", () => {
    const paragraph = Array.from({ length: 180 })
      .map((_, index) => `paragraph-token-${index}`)
      .join(" ");
    const result = paginateMarkdownHtml({
      html: `<p>${paragraph}</p>`,
      lineHeight: 19,
      pageContentHeightPx: 150,
    });

    expect(result.pageCount).toBeGreaterThanOrEqual(3);
    expect(textFromPages(result.pages.map((page) => page.html))).toContain("paragraph-token-0");
    expect(textFromPages(result.pages.map((page) => page.html))).toContain("paragraph-token-179");
  });

  it("preserves Markdown soft line breaks inside unsplit paragraphs", () => {
    const rendered = renderMarkdown(
      `## 技能
5 年 AI 应用与全栈工程经验
5 年 AI 应用与全栈工程经验，
5 年 AI 应用与全栈工程经验，。`,
      { themeId: "muji-default-autumn", lineHeight: 19 },
    );

    expect(rendered.html).toContain("<br");

    const result = paginateMarkdownHtml({
      html: rendered.html,
      lineHeight: 19,
      pageContentHeightPx: 400,
    });
    const html = result.pages.map((page) => page.html).join("");

    expect(html).toContain("<br");
    expect(countOccurrences(html, "<br")).toBeGreaterThanOrEqual(2);
  });

  it("preserves Markdown soft line breaks after a paragraph is split across pages", () => {
    const lines = Array.from(
      { length: 18 },
      (_, index) => `5 年 AI 应用与全栈工程经验 ${String(index + 1).padStart(2, "0")}`,
    );
    const rendered = renderMarkdown(`## 技能\n${lines.join("\n")}`, {
      themeId: "muji-default-autumn",
      lineHeight: 19,
    });

    expect(rendered.html).toContain("<br");

    const result = paginateMarkdownHtml({
      html: rendered.html,
      lineHeight: 19,
      pageContentHeightPx: 135,
    });
    const html = result.pages.map((page) => page.html).join("");
    const text = textFromPages(result.pages.map((page) => page.html));
    const pagesWithBreaks = result.pages.filter((page) => page.html.includes("<br"));

    expect(result.pageCount).toBeGreaterThanOrEqual(2);
    expect(pagesWithBreaks.length).toBeGreaterThanOrEqual(2);
    for (const line of lines) {
      expect(text).toContain(line);
    }
  });

  it("preserves inline Markdown formatting after a paragraph is split across pages", () => {
    const phrases = Array.from({ length: 24 }, (_, index) => {
      const item = String(index + 1).padStart(2, "0");
      return `plain-${item} **bold-${item}** *em-${item}* \`code-${item}\``;
    }).join(" ");
    const rendered = renderMarkdown(`## Skills\n${phrases}`, {
      themeId: "muji-default-autumn",
      lineHeight: 19,
    });

    expect(rendered.html).toContain("<strong>");

    const result = paginateMarkdownHtml({
      html: rendered.html,
      lineHeight: 19,
      pageContentHeightPx: 135,
    });
    const html = result.pages.map((page) => page.html).join("");
    const text = textFromPages(result.pages.map((page) => page.html));

    expect(result.pageCount).toBeGreaterThanOrEqual(2);
    expect(countOccurrences(html, "<strong>")).toBeGreaterThanOrEqual(2);
    expect(html).toContain("<strong>bold-01</strong>");
    expect(html).toContain("<em>em-12</em>");
    expect(html).toContain("<code>code-24</code>");
    expect(text).toContain("plain-01 bold-01 em-01 code-01");
    expect(text).toContain("plain-24 bold-24 em-24 code-24");
  });

  it("splits long lists across all needed pages without dropping or duplicating items", () => {
    const items = Array.from(
      { length: 36 },
      (_, index) => `List item ${String(index + 1).padStart(2, "0")} with scoped evidence`,
    );
    const result = paginateMarkdownHtml({
      html: `<ul>${items.map((item) => `<li>${item}</li>`).join("")}</ul>`,
      lineHeight: 19,
      pageContentHeightPx: 130,
    });
    const text = textFromPages(result.pages.map((page) => page.html));

    expect(result.pageCount).toBeGreaterThanOrEqual(3);
    for (const item of items) {
      expect(countOccurrences(text, item)).toBe(1);
    }
  });

  it("uses remaining page space by splitting an oversized first list item", () => {
    const longItem = Array.from({ length: 220 }, (_, index) => `long-token-${index}`).join(" ");
    const result = paginateMarkdownHtml({
      html: `<h2>Experience</h2><ul><li>${longItem}</li><li>second item survives</li></ul>`,
      lineHeight: 12,
      pageContentHeightPx: 100,
    });
    const firstPageText = textFromPages([result.pages[0].html]);
    const allText = textFromPages(result.pages.map((page) => page.html));

    expect(result.pageCount).toBeGreaterThanOrEqual(2);
    expect(firstPageText).toContain("long-token-0");
    expect(allText).toContain("long-token-219");
    expect(allText).toContain("second item survives");
  });

  it("uses leftover page space by splitting the next oversized list item", () => {
    const longItem = Array.from({ length: 180 }, (_, index) => `next-token-${index}`).join(" ");
    const result = paginateMarkdownHtml({
      html: `<ul><li>first short item</li><li>${longItem}</li><li>tail item survives</li></ul>`,
      lineHeight: 12,
      pageContentHeightPx: 120,
    });
    const firstPageText = textFromPages([result.pages[0].html]);
    const allText = textFromPages(result.pages.map((page) => page.html));

    expect(result.pageCount).toBeGreaterThanOrEqual(2);
    expect(firstPageText).toContain("first short item");
    expect(firstPageText).toContain("next-token-0");
    expect(allText).toContain("next-token-179");
    expect(allText).toContain("tail item survives");
  });

  it("splits long tables by row and repeats the table header on continuation pages", () => {
    const rows = Array.from({ length: 30 }, (_, index) => {
      const rowNumber = String(index + 1).padStart(2, "0");
      return `<tr><td>Project ${rowNumber}</td><td>Outcome ${rowNumber}</td></tr>`;
    }).join("");
    const result = paginateMarkdownHtml({
      html: `<table><thead><tr><th>Project</th><th>Outcome</th></tr></thead><tbody>${rows}</tbody></table>`,
      lineHeight: 19,
      pageContentHeightPx: 150,
    });
    const text = textFromPages(result.pages.map((page) => page.html));

    expect(result.pageCount).toBeGreaterThanOrEqual(3);
    expect(result.pages.slice(1).every((page) => page.html.includes("<thead>"))).toBe(true);
    for (let index = 1; index <= 30; index += 1) {
      const rowNumber = String(index).padStart(2, "0");
      expect(countOccurrences(text, `Project ${rowNumber}`)).toBe(1);
      expect(countOccurrences(text, `Outcome ${rowNumber}`)).toBe(1);
    }
  });

  it("keeps a heading with following content when the current page is full", () => {
    const html = `<p>${"Intro ".repeat(120)}</p><h2>Experience</h2><p>First role details.</p>`;

    const result = paginateMarkdownHtml({
      html,
      lineHeight: 19,
      pageContentHeightPx: 160,
    });

    const experiencePage = result.pages.find((page) => page.html.includes("Experience"));
    expect(experiencePage?.html).toContain("First role details.");
    expect(result.breaks.some((decision) => decision.reason === "avoid_orphan_heading")).toBe(true);
  });

  it("keeps only the first related block with a heading instead of moving the whole section", () => {
    const html = [
      `<p>${"Intro ".repeat(80)}</p>`,
      "<h2>Experience</h2>",
      "<p>First role details.</p>",
      `<p>Second role details ${"more ".repeat(140)}</p>`,
    ].join("");

    const result = paginateMarkdownHtml({
      html,
      lineHeight: 19,
      pageContentHeightPx: 150,
    });

    const headingPage = result.pages.find((page) => page.html.includes("Experience"));
    expect(headingPage?.html).toContain("First role details.");
    expect(headingPage?.html).not.toContain("Second role details");
    expect(result.pages.some((page) => page.html.includes("Second role details"))).toBe(true);
  });

  it("splits oversized contact containers by contact row", () => {
    const rows = Array.from({ length: 24 }, (_, index) => {
      const rowNumber = String(index + 1).padStart(2, "0");
      return `<div class="resume-contact-row" data-contact-row-kind="text"><span class="resume-contact-text">Contact row ${rowNumber}</span></div>`;
    }).join("");
    const result = paginateMarkdownHtml({
      html: `<div class="lr-container resume-contact-container"><div class="left resume-contact-side" data-contact-side="left">${rows}</div></div>`,
      lineHeight: 19,
      pageContentHeightPx: 120,
    });
    const text = textFromPages(result.pages.map((page) => page.html));

    expect(result.pageCount).toBeGreaterThanOrEqual(3);
    for (let index = 1; index <= 24; index += 1) {
      const rowNumber = String(index).padStart(2, "0");
      expect(countOccurrences(text, `Contact row ${rowNumber}`)).toBe(1);
    }
  });

  it("does not rebuild mixed contact containers in a way that drops non-row content", () => {
    const html = [
      '<div class="lr-container resume-contact-container">',
      '<div class="left resume-contact-side" data-contact-side="left">',
      '<h3>interCraft</h3>',
      '<p><strong>项目背景</strong>：面向复杂业务流程的 AI 工作台。</p>',
      '<div class="resume-contact-row" data-contact-row-kind="text"><span class="resume-contact-text">Contact-looking row</span></div>',
      '<ul><li>设计 Agent 自主规划机制</li><li>interCraft 多 Agent 编排</li></ul>',
      "</div>",
      '<div class="right resume-contact-side" data-contact-side="right">',
      "<p>负责 Markdown 渲染、分页和导出链路。</p>",
      "</div>",
      "</div>",
    ].join("");

    const result = paginateMarkdownHtml({
      html,
      lineHeight: 19,
      pageContentHeightPx: 220,
    });
    const text = textFromPages(result.pages.map((page) => page.html));

    expect(text).toContain("interCraft");
    expect(text).toContain("项目背景");
    expect(text).toContain("设计 Agent 自主规划机制");
    expect(text).toContain("负责 Markdown 渲染、分页和导出链路");
    expect(countOccurrences(text, "Contact-looking row")).toBe(1);
  });

  it("keeps a heading inside the left side of a generic two-column section after pagination", () => {
    const intro = Array.from({ length: 10 }, (_, index) => `Intro paragraph ${index + 1} ${"content ".repeat(16)}`)
      .join("\n\n");
    const rendered = renderMarkdown(
      `${intro}

::: left

### interCraft Project

:::

::: right
Owner / Full stack
:::
`,
      { themeId: "muji-default-autumn", lineHeight: 19 },
    );

    const result = paginateMarkdownHtml({
      html: rendered.html,
      lineHeight: 19,
      pageContentHeightPx: 180,
    });
    const container = htmlContainer(result.pages.map((page) => page.html));
    const lrContainer = container.querySelector(".lr-container");

    expect(result.pageCount).toBeGreaterThanOrEqual(2);
    expect(lrContainer?.querySelector(".left h3")?.textContent).toContain("interCraft Project");
    expect(lrContainer?.querySelector(".right")?.textContent).toContain("Owner / Full stack");
    const detachedHeadings = Array.from(container.querySelectorAll("h3")).filter(
      (heading) => !lrContainer?.contains(heading),
    );
    expect(detachedHeadings).toHaveLength(0);
  });

  it("splits oversized CJK list items even when the text has no spaces", () => {
    const chunk = "\u8fde\u7eed\u4e2d\u6587\u5185\u5bb9\u7528\u4e8e\u9a8c\u8bc1\u5206\u9875";
    const longItem = Array.from({ length: 90 }, (_, index) => `${chunk}${index}`).join("");

    const result = paginateMarkdownHtml({
      html: `<ul><li>${longItem}</li><li>tail item survives</li></ul>`,
      lineHeight: 12,
      pageContentHeightPx: 96,
    });
    const allText = textFromPages(result.pages.map((page) => page.html));

    expect(result.pageCount).toBeGreaterThan(1);
    expect(textFromPages([result.pages[0].html])).toContain(`${chunk}0`);
    expect(allText).toContain(`${chunk}89`);
    expect(allText).toContain("tail item survives");
  });

  it("preserves contact, generic two-column sections, and long lists after render and pagination", () => {
    const markdown = `# 林溪

::: left
icon:phone 13800000000
icon:email linxi@example.com
:::

::: right
[icon:github GitHub](https://github.com/example-linxi)
:::

## 工作经历

::: left
### AI 平台工程师
**公司**：InterCraft

- 负责 Markdown 渲染、分页和导出链路
:::

::: right
2023 - 至今

技术方向：React / FastAPI / Agent Workflow
:::

## 核心项目

::: left
### interCraft
**项目背景**：面向复杂业务流程的 AI 工作台。

- 设计 Agent 自主规划机制
- 打通 Markdown 预览与 PDF 导出
:::

::: right
### 第二项目

- 第二项目 bullet 不丢
- 技术栈覆盖 React、FastAPI、LangGraph
:::

## 技术栈

${Array.from({ length: 36 }, (_, index) => `- 长列表条目 ${index + 1}：分页保留完整文本`).join("\n")}
`;
    const rendered = renderMarkdown(markdown, { themeId: "muji-default-autumn", lineHeight: 19 });
    const result = paginateMarkdownHtml({
      html: rendered.html,
      lineHeight: 19,
      pageContentHeightPx: 180,
    });
    const text = textFromPages(result.pages.map((page) => page.html));

    expect(result.pageCount).toBeGreaterThanOrEqual(2);
    expect(text).toContain("核心项目");
    expect(text).toContain("项目背景");
    expect(text).toContain("设计 Agent 自主规划机制");
    expect(text).toContain("interCraft");
    expect(text).toContain("第二项目 bullet 不丢");
    expect(text).toContain("长列表条目 36");
  });
});

function textFromPages(pages: string[]): string {
  const container = htmlContainer(pages);
  return container.textContent?.replace(/\s+/g, " ").trim() ?? "";
}

function htmlContainer(pages: string[]): HTMLDivElement {
  const container = document.createElement("div");
  container.innerHTML = pages.join("");
  return container;
}

function countOccurrences(text: string, needle: string): number {
  return text.split(needle).length - 1;
}
