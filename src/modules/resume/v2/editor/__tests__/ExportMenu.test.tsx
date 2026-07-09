import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ExportMenu } from "../controls/ExportMenu";

const renderExportMock = vi.fn();
const downloadBlobMock = vi.fn();
const downloadSourceMarkdownMock = vi.fn();

vi.mock("../../api", () => ({
  renderExport: (...args: unknown[]) => renderExportMock(...args),
}));

vi.mock("@/modules/resume/converter/markdown-export", () => ({
  downloadBlob: (...args: unknown[]) => downloadBlobMock(...args),
  downloadSourceMarkdown: (...args: unknown[]) => downloadSourceMarkdownMock(...args),
}));

describe("ExportMenu", () => {
  it("exports Markdown source without transforming it", () => {
    render(
      <ExportMenu
        resumeId="r1"
        filenameBase="linxi"
        sourceMarkdown="# 林溪"
        previewHtml="<div>preview</div>"
        themeId="muji-default-autumn"
        lineHeight={19}
        smartOnePageEnabled={false}
        paginationState="paginated"
        pageCount={1}
      />,
    );

    fireEvent.click(screen.getByTestId("export-markdown-option"));
    expect(downloadSourceMarkdownMock).toHaveBeenCalledWith("# 林溪", "linxi.md");
  });

  it("sends current preview HTML and settings for PDF export", async () => {
    renderExportMock.mockResolvedValue(new Blob(["%PDF-1.4"], { type: "application/pdf" }));
    render(
      <ExportMenu
        resumeId="r1"
        filenameBase="linxi"
        sourceMarkdown="# 林溪"
        previewHtml={'<div data-theme="muji-minimal-color">preview</div>'}
        themeId="muji-minimal-color"
        lineHeight={12}
        smartOnePageEnabled={true}
        paginationState="paginated"
        pageCount={2}
      />,
    );

    fireEvent.click(screen.getByTestId("export-pdf-option"));

    await waitFor(() => expect(renderExportMock).toHaveBeenCalled());
    const html = renderExportMock.mock.calls[0]?.[2] as string;
    expect(html).toContain('<style data-resume-export-style="markdown">');
    expect(html).toContain(".markdown-resume-preview");
    expect(html).toContain("@page");
    expect(html).toContain("break-after: page");
    expect(html).toContain('data-theme="muji-minimal-color"');
    expect(html).toContain('data-export-line-height="12"');
    expect(renderExportMock).toHaveBeenCalledWith("r1", "pdf", expect.stringContaining("muji-minimal-color"), {
      sourceMarkdown: "# 林溪",
      themeId: "muji-minimal-color",
      lineHeight: 12,
      smartOnePageEnabled: true,
      paginationState: "paginated",
      pageCount: 2,
    });
    expect(downloadBlobMock).toHaveBeenCalledWith(expect.any(Blob), "linxi.pdf");
  });

  it("blocks PDF export while pagination is measuring", () => {
    render(
      <ExportMenu
        resumeId="r1"
        filenameBase="linxi"
        sourceMarkdown="# Lin"
        previewHtml="<div>preview</div>"
        themeId="muji-default-autumn"
        lineHeight={19}
        smartOnePageEnabled={false}
        paginationState="measuring"
        pageCount={1}
      />,
    );

    expect(screen.getByTestId("export-pdf-option")).toBeDisabled();
    expect(renderExportMock).not.toHaveBeenCalled();
  });
});
