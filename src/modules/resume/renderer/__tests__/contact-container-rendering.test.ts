import { describe, expect, it } from "vitest";
import { renderMarkdown } from "../index";

const contactMarkdown = `# Lin Xi

::: left
icon:phone 13800000000
icon:email linxi@example.com
icon:not-real Unknown channel
Plain note
:::

::: right
[icon:github GitHub](https://github.com/example-linxi)
[icon:link Portfolio](https://example.com/portfolio)
:::
`;

describe("contact container rendering", () => {
  it("emits semantic row groups for left and right contact blocks", () => {
    const result = renderMarkdown(contactMarkdown);

    expect(result.html).toContain('data-contact-side="left"');
    expect(result.html).toContain('data-contact-side="right"');
    expect(result.html.match(/class="resume-contact-row/g)).toHaveLength(6);
    expect(result.html).toContain('class="resume-contact-icon"');
    expect(result.html).toContain('class="resume-contact-text"');
  });

  it("keeps icon-prefixed links in one row and reserves fallback icon slots", () => {
    const result = renderMarkdown(contactMarkdown);

    expect(result.html).toContain('data-contact-icon-status="fallback"');
    expect(result.html).toContain("Unknown channel");
    expect(result.html).toContain('<a href="https://github.com/example-linxi"');
    expect(result.html).toContain('data-contact-row-kind="link"');
  });

  it("renders common resume contact aliases without fallback markers", () => {
    const result = renderMarkdown(`::: left
icon:info Male / 2002.06
:::

::: right
icon:school Tianjin University
:::
`);

    expect(result.html.match(/data-contact-icon-status="known"/g)).toHaveLength(2);
    expect(result.html).not.toContain('data-contact-icon-status="fallback"');
    expect(result.html).toContain("Male / 2002.06");
    expect(result.html).toContain("Tianjin University");
  });

  it("keeps non-contact left and right blocks as ordinary two-column content", () => {
    const result = renderMarkdown(`## 核心项目

::: left
### interCraft
**项目背景**：面向复杂业务流程的 AI 工作台。

- 设计 Agent 自主规划机制
- interCraft 多 Agent 编排
:::

::: right
**角色**：全栈工程师

负责 Markdown 渲染、分页和导出链路。
:::
`);

    expect(result.html).toContain('class="lr-container"');
    expect(result.html).toContain('class="left"');
    expect(result.html).toContain('class="right"');
    expect(result.html).not.toContain("resume-contact-container");
    expect(result.html).not.toContain("resume-contact-row");
    expect(result.html).toContain("<h3>interCraft</h3>");
    expect(result.html).toContain("项目背景");
    expect(result.html).toContain("设计 Agent 自主规划机制");
  });

  it("keeps right columns as siblings when the left column starts with a heading", () => {
    const result = renderMarkdown(`::: left
### 企业级在线 Agent 工作流编排平台「博特」
:::

::: right
核心开发 / 技术产品协同
:::

项目背景正文必须位于双栏之后。
`);
    const root = document.createElement("div");
    root.innerHTML = result.html;
    const container = root.querySelector(".lr-container");

    expect(container?.querySelector(":scope > .left")).not.toBeNull();
    expect(container?.querySelector(":scope > .right")).not.toBeNull();
    expect(container?.querySelector(":scope > .left > .right")).toBeNull();
    expect(container?.textContent).not.toContain("项目背景正文必须位于双栏之后");
    expect(container?.nextElementSibling?.textContent).toContain("项目背景正文必须位于双栏之后");
    expect(result.html).toContain("项目背景正文必须位于双栏之后");
  });

  it("keeps a heading in the left column after a previous h3 section", () => {
    const result = renderMarkdown(`### Previous project

Previous project details.

::: left

### interCraft Project

:::

::: right
Owner / Full stack
:::
`);
    const root = document.createElement("div");
    root.innerHTML = result.html;
    const container = root.querySelector(".lr-container");

    expect(container?.querySelector(":scope > .left h3")?.textContent).toContain("interCraft Project");
    expect(container?.querySelector(":scope > .right")?.textContent).toContain("Owner / Full stack");
    const detachedHeadings = Array.from(root.querySelectorAll("h3")).filter(
      (heading) => heading.textContent?.includes("interCraft") && !container?.contains(heading),
    );
    expect(detachedHeadings).toHaveLength(0);
  });
});
