import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { MarkdownResumeEditor } from "../MarkdownResumeEditor";
import { formatLabMarkdown } from "./resumeV3TestData";

describe("MarkdownResumeEditor", () => {
  it("renders a Markdown source editor and synchronized resume preview", () => {
    const onSourceChange = vi.fn();
    render(
      <MarkdownResumeEditor
        sourceMarkdown={formatLabMarkdown}
        themeId="muji-default-autumn"
        manualLineHeight={19}
        smartOnePageEnabled={false}
        smartLineHeight={null}
        smartStatus="idle"
        onSourceChange={onSourceChange}
        onThemeChange={vi.fn()}
        onManualLineHeightChange={vi.fn()}
        onEnableSmartOnePage={vi.fn()}
        onDisableSmartOnePage={vi.fn()}
      />,
    );

    const editor = screen.getByTestId("markdown-source-editor");
    expect(editor).toHaveValue(formatLabMarkdown);
    expect(screen.getByTestId("markdown-preview-page")).toHaveClass("height19");
    expect(screen.getByTestId("markdown-preview-page")).toHaveAttribute("data-theme", "muji-default-autumn");
    expect(within(screen.getByTestId("markdown-preview-page")).getByText("林溪 - Markdown 渲染测试")).toBeTruthy();

    fireEvent.change(editor, { target: { value: "# 新标题" } });
    expect(onSourceChange).toHaveBeenCalledWith("# 新标题");
  });
});
