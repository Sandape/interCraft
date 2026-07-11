import { useEffect, useMemo, useRef, useState } from "react";
import { renderMarkdown } from "@/modules/resume/renderer";
import type {
  LineHeightPreset,
  LegacyConversionStatus,
  MarkdownPaginationState,
  MujiThemeId,
  SmartOnePageStatus,
} from "@/modules/resume/renderer/types";
import { getThemeById } from "@/modules/resume/themes";
import { getEffectiveLineHeight } from "@/modules/resume/pagination/line-height";
import { computeSmartOnePage } from "@/modules/resume/pagination/smart-one-page";
import { paginateMarkdownHtml } from "@/modules/resume/pagination/markdown-pages";
import { ThemeMenu } from "./controls/ThemeMenu";
import { LineSpacingControl } from "./controls/LineSpacingControl";
import { SmartOnePageControl } from "./controls/SmartOnePageControl";
import { useResumeV2Store } from "../store";
import "./markdown-resume.css";

export interface MarkdownResumeEditorProps {
  sourceMarkdown: string;
  themeId: MujiThemeId;
  manualLineHeight: LineHeightPreset;
  smartOnePageEnabled: boolean;
  smartLineHeight: LineHeightPreset | null;
  smartStatus: SmartOnePageStatus;
  onSourceChange: (sourceMarkdown: string) => void;
  onThemeChange: (themeId: MujiThemeId) => void;
  onManualLineHeightChange: (lineHeight: LineHeightPreset) => void;
  onEnableSmartOnePage: (
    selectedLineHeight: LineHeightPreset | null,
    status: Exclude<SmartOnePageStatus, "idle">,
  ) => void;
  onDisableSmartOnePage: () => void;
  onPaginationChange?: (state: MarkdownPaginationState, pageCount: number) => void;
  legacyConversionStatus?: LegacyConversionStatus;
  legacyConversionWarnings?: string[];
}

export function MarkdownResumeEditor({
  sourceMarkdown,
  themeId,
  manualLineHeight,
  smartOnePageEnabled,
  smartLineHeight,
  smartStatus,
  onSourceChange,
  onThemeChange,
  onManualLineHeightChange,
  onEnableSmartOnePage,
  onDisableSmartOnePage,
  onPaginationChange,
  legacyConversionStatus = "not_needed",
  legacyConversionWarnings = [],
}: MarkdownResumeEditorProps) {
  const effectiveLineHeight = getEffectiveLineHeight({
    manualLineHeight,
    smartOnePageEnabled,
    smartLineHeight,
  });
  const theme = getThemeById(themeId);
  const renderResult = useMemo(
    () => renderMarkdown(sourceMarkdown, { themeId, lineHeight: effectiveLineHeight }),
    [effectiveLineHeight, sourceMarkdown, themeId],
  );
  const initialPaginatedPreview = useMemo(
    () => paginateMarkdownHtml({ html: renderResult.html, lineHeight: effectiveLineHeight, themeId }),
    [effectiveLineHeight, renderResult.html, themeId],
  );
  const [paginatedPreview, setPaginatedPreview] = useState(initialPaginatedPreview);
  const latestPageCountRef = useRef(initialPaginatedPreview.pageCount);
  const aiFocusAnchor = useResumeV2Store((state) => state.aiFocusAnchor);

  useEffect(() => {
    latestPageCountRef.current = paginatedPreview.pageCount;
  }, [paginatedPreview.pageCount]);

  useEffect(() => {
    let cancelled = false;
    onPaginationChange?.("measuring", latestPageCountRef.current);

    const runPagination = () => {
      const nextPreview = paginateMarkdownHtml({
        html: renderResult.html,
        lineHeight: effectiveLineHeight,
        themeId,
      });
      if (cancelled) return;
      latestPageCountRef.current = nextPreview.pageCount;
      setPaginatedPreview(nextPreview);
      onPaginationChange?.(
        nextPreview.overflowWarnings.length > 0 ? "warning" : "paginated",
        nextPreview.pageCount,
      );
    };

    if (typeof window !== "undefined" && typeof window.requestAnimationFrame === "function") {
      const frame = window.requestAnimationFrame(runPagination);
      return () => {
        cancelled = true;
        window.cancelAnimationFrame(frame);
      };
    }

    const timer = window.setTimeout(runPagination, 0);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [effectiveLineHeight, onPaginationChange, renderResult.html, themeId]);

  useEffect(() => {
    if (!aiFocusAnchor) return;
    const escaped = typeof CSS !== "undefined" && CSS.escape ? CSS.escape(aiFocusAnchor.nodeId) : aiFocusAnchor.nodeId;
    const target = document.querySelector<HTMLElement>(`[data-node-id="${escaped}"]`);
    if (!target) return;
    target.scrollIntoView({ block: "center", behavior: "smooth" });
    target.setAttribute("data-ai-highlight", "true");
    const timer = window.setTimeout(() => target.removeAttribute("data-ai-highlight"), 1800);
    return () => window.clearTimeout(timer);
  }, [aiFocusAnchor]);

  const handleEnableSmartOnePage = () => {
    const result = computeSmartOnePage({
      preferredLineHeight: 20,
      pageCountAt: (lineHeight) => {
        const candidate = renderMarkdown(sourceMarkdown, { themeId, lineHeight });
        return paginateMarkdownHtml({ html: candidate.html, lineHeight, themeId }).pageCount;
      },
    });
    onEnableSmartOnePage(result.selectedLineHeight, result.status);
  };

  return (
    <div className="markdown-resume-shell flex h-full w-full flex-col bg-surface-muted">
      <div className="flex flex-wrap items-center gap-3 border-b border-surface-border bg-surface px-4 py-2">
        <ThemeMenu value={themeId} onChange={onThemeChange} />
        <LineSpacingControl
          value={manualLineHeight}
          disabled={smartOnePageEnabled}
          onChange={onManualLineHeightChange}
        />
        <SmartOnePageControl
          enabled={smartOnePageEnabled}
          status={smartStatus}
          selectedLineHeight={smartLineHeight}
          onEnable={handleEnableSmartOnePage}
          onDisable={onDisableSmartOnePage}
        />
        {smartStatus === "infeasible" && (
          <span
            data-testid="smart-one-page-feedback"
            role="status"
            className="text-xs text-amber-700"
          >
            One-page fit is unavailable; all pages are preserved.
          </span>
        )}
        {legacyConversionStatus !== "not_needed" && (
          <span
            data-testid="legacy-conversion-status"
            role="status"
            className="text-xs text-amber-700"
          >
            {legacyConversionStatus === "converted"
              ? "Older resume content was converted to Markdown."
              : "Older resume content was converted with warnings."}
            {legacyConversionWarnings.length > 0 ? ` ${legacyConversionWarnings.join(" ")}` : ""}
          </span>
        )}
      </div>

      <div className="grid min-h-0 flex-1 grid-cols-1 gap-0 lg:grid-cols-[minmax(320px,42%)_1fr]">
        <section className="min-h-0 min-w-0 overflow-hidden border-r border-surface-border bg-white">
          <textarea
            data-testid="markdown-source-editor"
            aria-label="Markdown 简历源码"
            value={sourceMarkdown}
            onChange={(event) => onSourceChange(event.target.value)}
            spellCheck={false}
            className="h-full min-h-[520px] w-full resize-none bg-white p-4 font-mono text-sm leading-6 text-ink-1 outline-none"
          />
        </section>
        <section className="min-h-0 min-w-0 overflow-auto bg-surface-muted p-6">
          <div
            className="markdown-preview-pages"
            data-testid="markdown-preview-pages"
            data-page-count={paginatedPreview.pageCount}
          >
            {paginatedPreview.pages.map((page) => (
              <article
                key={page.pageIndex}
                data-testid="markdown-preview-page"
                data-page-index={page.pageIndex}
                data-page-number={page.pageNumber}
                data-theme={themeId}
                data-theme-pattern={theme?.renderPattern ?? ""}
                className={`markdown-resume-preview height${effectiveLineHeight}`}
              >
                <div
                  className="resume-page-content"
                  dangerouslySetInnerHTML={{ __html: page.html }}
                />
              </article>
            ))}
          </div>
          {paginatedPreview.pageCount > 1 && (
            <div className="mt-3 text-xs text-ink-3" data-testid="markdown-page-count">
              {paginatedPreview.pageCount} pages
            </div>
          )}
          {renderResult.warnings.length > 0 && (
            <div className="mt-3 text-xs text-amber-700" data-testid="markdown-render-warnings">
              {renderResult.warnings.map((warning) => warning.message).join(" ")}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
