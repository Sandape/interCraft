import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { MarkdownResumeEditor } from "../MarkdownResumeEditor";
import { formatLabMarkdown } from "./resumeV3TestData";
import type { MujiThemeId } from "@/modules/resume/renderer/types";

const cases: Array<[MujiThemeId, string]> = [
  ["muji-default-autumn", "dark-header-centered-section"],
  ["muji-minimal-color", "minimal-line"],
  ["muji-flat-atmospheric", "accent-band"],
];

describe("Markdown resume preview themes", () => {
  it.each(cases)("applies %s without mutating source", (themeId, pattern) => {
    render(
      <MarkdownResumeEditor
        sourceMarkdown={formatLabMarkdown}
        themeId={themeId}
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

    const preview = screen.getByTestId("markdown-preview-page");
    expect(preview).toHaveAttribute("data-theme", themeId);
    expect(preview).toHaveAttribute("data-theme-pattern", pattern);
    expect(screen.getByTestId("markdown-source-editor")).toHaveValue(formatLabMarkdown);
  });
});
