import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { MarkdownResumeEditor } from "../MarkdownResumeEditor";

const longMarkdown = `# Long Resume

${Array.from({ length: 80 })
  .map((_, index) => `## Section ${index + 1}\n\n- Detail ${index + 1}\n- ${"Evidence ".repeat(12)}`)
  .join("\n\n")}
`;

const mixedTwoColumnMarkdown = `# 林溪

::: left
icon:phone 13800000000
icon:email linxi@example.com
:::

::: right
[icon:github GitHub](https://github.com/example-linxi)
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

${Array.from({ length: 70 }, (_, index) => `## Section ${index + 1}\n\n- Evidence ${index + 1}`).join("\n\n")}
`;

describe("MarkdownResumeEditor pagination", () => {
  it("renders ordered page containers and reports page count", async () => {
    const onPaginationChange = vi.fn();
    render(
      <MarkdownResumeEditor
        sourceMarkdown={longMarkdown}
        themeId="muji-default-autumn"
        manualLineHeight={19}
        smartOnePageEnabled={false}
        smartLineHeight={null}
        smartStatus="idle"
        onSourceChange={vi.fn()}
        onThemeChange={vi.fn()}
        onManualLineHeightChange={vi.fn()}
        onEnableSmartOnePage={vi.fn()}
        onDisableSmartOnePage={vi.fn()}
        onPaginationChange={onPaginationChange}
      />,
    );

    const pages = screen.getAllByTestId("markdown-preview-page");
    expect(pages.length).toBeGreaterThanOrEqual(3);
    expect(pages[0]).toHaveAttribute("data-page-number", "1");
    expect(pages.at(-1)).toHaveAttribute("data-page-number", String(pages.length));
    expect(onPaginationChange).toHaveBeenCalledWith("measuring", pages.length);
    await waitFor(() => expect(onPaginationChange).toHaveBeenCalledWith("paginated", pages.length));
  });

  it("preserves generic two-column project content in multi-page preview DOM", () => {
    render(
      <MarkdownResumeEditor
        sourceMarkdown={mixedTwoColumnMarkdown}
        themeId="muji-default-autumn"
        manualLineHeight={19}
        smartOnePageEnabled={false}
        smartLineHeight={null}
        smartStatus="idle"
        onSourceChange={vi.fn()}
        onThemeChange={vi.fn()}
        onManualLineHeightChange={vi.fn()}
        onEnableSmartOnePage={vi.fn()}
        onDisableSmartOnePage={vi.fn()}
      />,
    );

    const previewRoot = screen.getByTestId("markdown-preview-pages");
    expect(Number(previewRoot.getAttribute("data-page-count"))).toBeGreaterThanOrEqual(2);
    expect(previewRoot).toHaveTextContent("核心项目");
    expect(previewRoot).toHaveTextContent("项目背景");
    expect(previewRoot).toHaveTextContent("设计 Agent 自主规划机制");
    expect(previewRoot).toHaveTextContent("interCraft");
    expect(previewRoot).toHaveTextContent("第二项目 bullet 不丢");
  });

  it("marks pagination as measuring before updating page count after line-height changes", async () => {
    const onPaginationChange = vi.fn();
    const props = {
      sourceMarkdown: longMarkdown,
      themeId: "muji-default-autumn" as const,
      smartOnePageEnabled: false,
      smartLineHeight: null,
      smartStatus: "idle" as const,
      onSourceChange: vi.fn(),
      onThemeChange: vi.fn(),
      onManualLineHeightChange: vi.fn(),
      onEnableSmartOnePage: vi.fn(),
      onDisableSmartOnePage: vi.fn(),
      onPaginationChange,
    };
    const { rerender } = render(<MarkdownResumeEditor {...props} manualLineHeight={12} />);

    await waitFor(() => expect(onPaginationChange).toHaveBeenCalledWith("paginated", expect.any(Number)));
    const initialCount = Number(screen.getByTestId("markdown-preview-pages").getAttribute("data-page-count"));
    onPaginationChange.mockClear();

    rerender(<MarkdownResumeEditor {...props} manualLineHeight={25} />);

    await waitFor(() => expect(onPaginationChange).toHaveBeenCalledWith("measuring", initialCount));
    await waitFor(() => expect(onPaginationChange).toHaveBeenCalledWith("paginated", expect.any(Number)));
    expect(Number(screen.getByTestId("markdown-preview-pages").getAttribute("data-page-count"))).toBeGreaterThanOrEqual(
      initialCount,
    );
  });

  it("surfaces smart one-page infeasible feedback without hiding pages", () => {
    render(
      <MarkdownResumeEditor
        sourceMarkdown={longMarkdown}
        themeId="muji-default-autumn"
        manualLineHeight={19}
        smartOnePageEnabled={true}
        smartLineHeight={null}
        smartStatus="infeasible"
        onSourceChange={vi.fn()}
        onThemeChange={vi.fn()}
        onManualLineHeightChange={vi.fn()}
        onEnableSmartOnePage={vi.fn()}
        onDisableSmartOnePage={vi.fn()}
      />,
    );

    expect(screen.getByTestId("smart-one-page-feedback")).toBeInTheDocument();
    expect(screen.getAllByTestId("markdown-preview-page").length).toBeGreaterThanOrEqual(3);
  });

  it("preserves inline formatting in paginated preview when smart one-page is disabled", () => {
    const formattedMarkdown = `# Formatted Resume

${Array.from({ length: 180 }, (_, index) => {
  const item = String(index + 1).padStart(2, "0");
  return `plain-${item} **bold-${item}** *em-${item}* \`code-${item}\``;
}).join(" ")}
`;

    render(
      <MarkdownResumeEditor
        sourceMarkdown={formattedMarkdown}
        themeId="muji-default-autumn"
        manualLineHeight={19}
        smartOnePageEnabled={false}
        smartLineHeight={null}
        smartStatus="idle"
        onSourceChange={vi.fn()}
        onThemeChange={vi.fn()}
        onManualLineHeightChange={vi.fn()}
        onEnableSmartOnePage={vi.fn()}
        onDisableSmartOnePage={vi.fn()}
      />,
    );

    const previewRoot = screen.getByTestId("markdown-preview-pages");
    expect(screen.getAllByTestId("markdown-preview-page").length).toBeGreaterThanOrEqual(2);
    expect(previewRoot.querySelectorAll("strong").length).toBeGreaterThanOrEqual(2);
    expect(previewRoot.querySelector("strong")?.textContent).toBe("bold-01");
    expect(previewRoot.querySelector("em")?.textContent).toBe("em-01");
    expect(previewRoot.querySelector("code")?.textContent).toBe("code-01");
  });

  it("surfaces legacy conversion status without offering a legacy editor", () => {
    render(
      <MarkdownResumeEditor
        sourceMarkdown="# Converted Resume"
        themeId="muji-default-autumn"
        manualLineHeight={19}
        smartOnePageEnabled={false}
        smartLineHeight={null}
        smartStatus="idle"
        legacyConversionStatus="converted"
        onSourceChange={vi.fn()}
        onThemeChange={vi.fn()}
        onManualLineHeightChange={vi.fn()}
        onEnableSmartOnePage={vi.fn()}
        onDisableSmartOnePage={vi.fn()}
      />,
    );

    expect(screen.getByTestId("legacy-conversion-status")).toHaveTextContent(
      "Older resume content was converted to Markdown.",
    );
    expect(screen.queryByTestId("legacy-open-v1")).not.toBeInTheDocument();
  });
});
