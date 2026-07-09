// T055 — Top header bar.
//
// Centered breadcrumb: `/` (root) + resume name + caret dropdown
// (clicking caret shows a stub switcher for now). Left + right
// sidebar toggle buttons (eye icons). The toggles collapse/expand
// the corresponding panel via the `onToggleLeft` / `onToggleRight`
// callbacks, which the BuilderShell wires up.
//
// T160 — Duplicate button lives in the header (NOT the bottom dock —
// FR-067 mandates exactly 8 dock buttons). It is placed to the left
// of the breadcrumb so the breadcrumb stays centered.
//
// 2026-06-26 — T031 (02-template-switch E2E) expects
// `data-testid="open-template-gallery"`. We host the TemplateGallery
// dialog inside the Header (single source of truth: the page-level
// resume data drives both the gallery and the live preview re-render).
//
// 2026-06-29 — Batch 3: Added "Export PDF" button on the top-right.
// Calls `renderExport(resumeId, "pdf", html)` with the live preview's
// outerHTML so the PDF reflects the user's unsaved local edits (the
// backend requires non-empty `html` for PDF / PNG / JPEG; without
// this it returns 400 EMPTY_CONTENT). See `handleExportPdf` below.

import { useCallback, useState } from "react";
import { ChevronDown, Copy, Download, Eye, EyeOff, Home, LayoutGrid, Loader2 } from "lucide-react";
import { TemplateGallery } from "./dialogs/TemplateGallery";
import { useResumeV2Store } from "../store";
import { renderExport } from "../api";
import { fireToast } from "./center/toast";
import type { TemplateId } from "../schema/templates";
import { ExportMenu } from "./controls/ExportMenu";

export interface HeaderProps {
  resumeName: string;
  leftCollapsed: boolean;
  rightCollapsed: boolean;
  onToggleLeft: () => void;
  onToggleRight: () => void;
  onSwitcherClick?: () => void;
  /** T160 — when provided, render the Duplicate button next to the breadcrumb. */
  onDuplicate?: () => void;
  /** T160 — disables the Duplicate button while the request is in flight. */
  duplicating?: boolean;
}

export function Header({
  resumeName,
  leftCollapsed,
  rightCollapsed,
  onToggleLeft,
  onToggleRight,
  onSwitcherClick,
  onDuplicate,
  duplicating,
}: HeaderProps) {
  // T031 — open-template-gallery lives in the header so the dock can
  // stay capped at FR-067's 8 buttons. The gallery mutates the store's
  // metadata.template, which is the same source the preview reads from.
  const [galleryOpen, setGalleryOpen] = useState(false);
  // Batch 3 — local loading flag for the Export PDF button. The
  // request can take 2-5s on a slow network (Playwright PDF render
  // is non-trivial); showing a spinner keeps the user from double-
  // clicking and creating a queue of duplicate downloads.
  const [exporting, setExporting] = useState(false);
  const setData = useResumeV2Store((s) => s.setData);
  const data = useResumeV2Store((s) => s.data);
  const resumeId = useResumeV2Store((s) => s.id);
  const currentTemplate = (data?.metadata?.template ?? "pikachu") as TemplateId;
  const markdown = data?.metadata?.markdown;

  // Batch 3 — PDF export. We grab the live preview DOM (rendered by
  // the same template the user is looking at) so the PDF matches what
  // they see, including unsaved local edits — `useResumeV2Store` may
  // be dirty (`isDirty === true`), and we deliberately bypass the
  // server's last-saved snapshot. We never call `flushSave()` first:
  // a) export is intended to be immediate, b) the live DOM is the
  // source of truth the user expects, c) the backend renderer
  // re-sanitizes the HTML before passing to Playwright so injected
  // classes are stripped.
  const handleExportPdf = useCallback(async () => {
    if (exporting || !resumeId) return;
    setExporting(true);
    try {
      // The preview pane renders a `.rs-tpl-stage` node inside
      // `[data-testid="preview-stage"]`. We use the inner stage (not
      // the wrapper) because the wrapper carries the editor's zoom
      // transform which would scale the PDF content down. The live
      // DOM is always present while the editor is mounted.
      const stage = typeof document !== "undefined"
        ? document.querySelector('[data-testid="preview-stage"] .rs-tpl-stage')
        : null;
      const html = stage instanceof HTMLElement ? stage.outerHTML : "";
      const slug = resumeSlugFromData(data) || resumeId;
      const blob = await renderExport(resumeId, "pdf", html);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `resume-${slug}.pdf`;
      a.style.display = "none";
      document.body.appendChild(a);
      a.click();
      // Revoke after a 5s grace period — Safari needs the URL to
      // remain valid until the download dialog has been handed the
      // blob; revoking immediately can cancel the download.
      window.setTimeout(() => {
        try {
          document.body.removeChild(a);
        } catch {
          /* node may already be detached */
        }
        URL.revokeObjectURL(url);
      }, 5_000);
      fireToast("PDF 已开始下载", "info");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "导出失败";
      fireToast(`导出失败: ${msg}`, "error");
    } finally {
      setExporting(false);
    }
  }, [exporting, resumeId, data]);

  return (
    <header
      className="flex h-10 w-full items-center justify-between border-b border-surface-border bg-surface px-2"
      data-testid="editor-header"
    >
      <div className="flex items-center gap-1">
        <button
          type="button"
          data-testid="toggle-left-sidebar"
          onClick={onToggleLeft}
          aria-label={leftCollapsed ? "Show left panel" : "Hide left panel"}
          aria-pressed={leftCollapsed}
          className="flex h-7 w-7 items-center justify-center rounded text-ink-2 hover:bg-surface-muted"
        >
          {leftCollapsed ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
        </button>
        <button
          type="button"
          data-testid="template-gallery-button"
          onClick={() => setGalleryOpen(true)}
          aria-label="Open template gallery"
          title="Open template gallery"
          className="ml-1 flex h-7 items-center gap-1 rounded border border-surface-border bg-white px-2 text-[11px] text-ink-1 hover:bg-surface-muted"
        >
          <LayoutGrid className="h-3.5 w-3.5" />
          <span data-testid="open-template-gallery">模板</span>
        </button>
      </div>

      <nav
        className="flex items-center gap-1 text-xs text-ink-2"
        data-testid="header-breadcrumb"
        aria-label="Breadcrumb"
      >
        <a
          href="/dashboard"
          className="flex h-6 items-center gap-1 rounded px-1.5 text-ink-3 hover:bg-surface-muted hover:text-ink-1"
        >
          <Home className="h-3 w-3" />
          <span className="text-[11px]">Home</span>
        </a>
        <span aria-hidden className="text-ink-3">/</span>
        <span className="font-medium text-ink-1" data-testid="header-resume-name">
          {resumeName}
        </span>
        <button
          type="button"
          data-testid="header-switcher"
          onClick={onSwitcherClick}
          aria-label="Switch resume"
          className="flex h-6 w-6 items-center justify-center rounded text-ink-3 hover:bg-surface-muted hover:text-ink-1"
        >
          <ChevronDown className="h-3 w-3" />
        </button>
        {onDuplicate && (
          <button
            type="button"
            data-testid="header-duplicate"
            onClick={onDuplicate}
            disabled={duplicating}
            aria-label="Duplicate resume"
            title="Duplicate resume"
            className="ml-1 flex h-6 items-center gap-1 rounded border border-surface-border bg-white px-1.5 text-[11px] text-ink-2 hover:bg-surface-muted disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Copy className="h-3 w-3" />
            <span>Duplicate</span>
          </button>
        )}
      </nav>

      <div className="flex items-center gap-1">
        {/* Batch 3 — Export PDF. The button is intentionally positioned
            on the top-right (per spec). We never disable it based on
            `isDirty` because export reflects the live DOM (which is
            always up-to-date), not the last server snapshot. */}
        {markdown && resumeId ? (
          <ExportMenu
            resumeId={resumeId}
            filenameBase={resumeSlugFromData(data) || resumeId}
            sourceMarkdown={markdown.sourceMarkdown}
            previewHtml={() => {
              const pages = Array.from(
                document.querySelectorAll<HTMLElement>('[data-testid="markdown-preview-page"]'),
              );
              return pages.map((page) => page.outerHTML).join("");
            }}
            themeId={markdown.themeId}
            lineHeight={
              markdown.smartOnePageEnabled && markdown.smartLineHeight !== null
                ? markdown.smartLineHeight
                : markdown.manualLineHeight
            }
            smartOnePageEnabled={markdown.smartOnePageEnabled}
            paginationState={markdown.paginationState}
            pageCount={markdown.pageCount}
          />
        ) : (
          <button
            type="button"
            data-testid="export-pdf-button"
            data-state={exporting ? "loading" : "idle"}
            onClick={() => void handleExportPdf()}
            disabled={exporting || !resumeId}
            aria-label="Export PDF"
            title="Export PDF (download current preview)"
            className="flex h-7 items-center gap-1 rounded border border-surface-border bg-white px-2 text-[11px] text-ink-1 hover:bg-surface-muted disabled:cursor-not-allowed disabled:opacity-60"
          >
            {exporting ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" data-testid="export-pdf-spinner" />
            ) : (
              <Download className="h-3.5 w-3.5" />
            )}
            <span>Export PDF</span>
          </button>
        )}
        <button
          type="button"
          data-testid="toggle-right-sidebar"
          onClick={onToggleRight}
          aria-label={rightCollapsed ? "Show right panel" : "Hide right panel"}
          aria-pressed={rightCollapsed}
          className="flex h-7 w-7 items-center justify-center rounded text-ink-2 hover:bg-surface-muted"
        >
          {rightCollapsed ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
        </button>
      </div>

      <TemplateGallery
        open={galleryOpen}
        onClose={() => setGalleryOpen(false)}
        currentId={currentTemplate}
        onSelect={(id: TemplateId) => {
          setData({
            ...data,
            metadata: { ...data.metadata, template: id },
          });
          setGalleryOpen(false);
        }}
      />
    </header>
  );
}

/**
 * Build a filesystem-safe slug for the downloaded filename. Prefers
 * the resume's basics.name (the human-readable title) when present;
 * falls back to the resume id. Mirrors the slug-derivation logic in
 * `ResumeListV2.handleCreate` so the export filename and the create
 * slug stay consistent.
 */
function resumeSlugFromData(data: { basics?: { name?: string } } | null | undefined): string {
  const name = data?.basics?.name?.trim();
  if (!name) return "";
  return name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 80);
}
