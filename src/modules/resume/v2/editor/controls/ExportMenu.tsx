import { useState } from "react";
import type {
  LineHeightPreset,
  MarkdownPaginationState,
  MujiThemeId,
} from "@/modules/resume/renderer/types";
import { downloadBlob, downloadSourceMarkdown } from "@/modules/resume/converter/markdown-export";
import { renderExport } from "../../api";
import { buildMarkdownPdfHtml } from "./export-html";

export interface ExportMenuProps {
  resumeId: string;
  filenameBase: string;
  sourceMarkdown: string;
  previewHtml: string | (() => string);
  themeId: MujiThemeId;
  lineHeight: LineHeightPreset;
  smartOnePageEnabled: boolean;
  paginationState?: MarkdownPaginationState;
  pageCount?: number;
}

function safeBase(value: string): string {
  return value.replace(/[<>:"/\\|?*]/g, "_").trim() || "resume";
}

export function ExportMenu({
  resumeId,
  filenameBase,
  sourceMarkdown,
  previewHtml,
  themeId,
  lineHeight,
  smartOnePageEnabled,
  paginationState = "paginated",
  pageCount = 1,
}: ExportMenuProps) {
  const [status, setStatus] = useState<"idle" | "pending" | "success" | "failed">("idle");
  const [message, setMessage] = useState("");
  const base = safeBase(filenameBase);

  const resolvePreviewHtml = () =>
    typeof previewHtml === "function" ? previewHtml() : previewHtml;

  const handleMarkdown = () => {
    downloadSourceMarkdown(sourceMarkdown, `${base}.md`);
    setStatus("success");
    setMessage("Markdown 已导出");
  };

  const handlePdf = async () => {
    if (paginationState === "measuring") {
      setStatus("failed");
      setMessage("Preview is still paginating. Try again after it finishes.");
      return;
    }
    setStatus("pending");
    setMessage("正在生成 PDF");
    try {
      const html = buildMarkdownPdfHtml({
        previewHtml: resolvePreviewHtml(),
        themeId,
        lineHeight,
      });
      const blob = await renderExport(resumeId, "pdf", html, {
        sourceMarkdown,
        themeId,
        lineHeight,
        smartOnePageEnabled,
        paginationState,
        pageCount,
      });
      downloadBlob(blob, `${base}.pdf`);
      setStatus("success");
      setMessage("PDF 已开始下载");
    } catch (error) {
      setStatus("failed");
      setMessage(error instanceof Error ? error.message : "PDF 导出失败");
    }
  };

  return (
    <div className="flex items-center gap-2 text-xs">
      <button
        type="button"
        data-testid="export-markdown-option"
        onClick={handleMarkdown}
        className="h-8 rounded border border-surface-border bg-white px-3 text-ink-1 hover:bg-surface-muted"
      >
        导出 MD
      </button>
      <button
        type="button"
        data-testid="export-pdf-option"
        data-state={status}
        disabled={status === "pending" || paginationState === "measuring"}
        onClick={() => void handlePdf()}
        className="h-8 rounded border border-surface-border bg-white px-3 text-ink-1 hover:bg-surface-muted disabled:cursor-wait disabled:opacity-70"
      >
        {status === "pending" ? "导出中" : "导出 PDF"}
      </button>
      {message && (
        <span
          data-testid={status === "failed" ? "export-error-message" : "export-status-message"}
          role={status === "failed" ? "alert" : "status"}
          className={status === "failed" ? "text-red-600" : "text-ink-3"}
        >
          {message}
        </span>
      )}
    </div>
  );
}
