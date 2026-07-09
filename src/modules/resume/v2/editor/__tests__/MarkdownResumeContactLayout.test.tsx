import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { MarkdownResumeEditor } from "../MarkdownResumeEditor";

const sourceMarkdown = `# Lin Xi

::: left
icon:phone 13800000000
icon:not-real Unknown channel
:::

::: right
[icon:github GitHub](https://github.com/example-linxi)
[icon:link Portfolio](https://example.com/very/long/path)
:::
`;

describe("MarkdownResumeEditor contact layout", () => {
  it("renders semantic contact rows across supported themes", () => {
    for (const themeId of [
      "muji-default-autumn",
      "muji-minimal-color",
      "muji-flat-atmospheric",
    ] as const) {
      const { unmount } = render(
        <MarkdownResumeEditor
          sourceMarkdown={sourceMarkdown}
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
      expect(within(preview).getAllByText("GitHub")).toHaveLength(1);
      expect(preview.querySelectorAll(".resume-contact-row")).toHaveLength(4);
      expect(preview.querySelector('[data-contact-icon-status="fallback"]')).not.toBeNull();
      expect(preview.querySelector('[data-contact-side="right"] .resume-contact-text a')).not.toBeNull();
      unmount();
    }
  });
});
