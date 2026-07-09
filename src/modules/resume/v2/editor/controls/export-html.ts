import markdownResumeCss from "../markdown-resume.css?raw";
import type { LineHeightPreset, MujiThemeId } from "@/modules/resume/renderer/types";

export interface MarkdownPdfHtmlOptions {
  previewHtml: string;
  themeId: MujiThemeId;
  lineHeight: LineHeightPreset;
}

const PDF_EXPORT_CSS = `
@page {
  size: A4;
  margin: 0;
}

html,
body {
  width: 794px;
  min-height: 1122px;
  margin: 0;
  padding: 0;
  background: #ffffff;
}

body {
  print-color-adjust: exact;
  -webkit-print-color-adjust: exact;
}

.markdown-pdf-export {
  width: 794px;
  margin: 0;
  padding: 0;
  background: #ffffff;
}

.markdown-pdf-export .markdown-resume-preview {
  display: block;
  margin: 0;
  box-shadow: none;
  break-after: page;
  page-break-after: always;
}

.markdown-pdf-export .markdown-resume-preview:last-child {
  break-after: auto;
  page-break-after: auto;
}
`;

export function buildMarkdownPdfHtml({
  previewHtml,
  themeId,
  lineHeight,
}: MarkdownPdfHtmlOptions): string {
  return [
    '<style data-resume-export-style="markdown">',
    markdownResumeCss,
    PDF_EXPORT_CSS,
    "</style>",
    `<div class="markdown-pdf-export" data-export-theme="${themeId}" data-export-line-height="${lineHeight}">`,
    previewHtml,
    "</div>",
  ].join("\n");
}
