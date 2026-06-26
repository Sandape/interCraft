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

import { useState } from "react";
import { ChevronDown, Copy, Eye, EyeOff, Home, LayoutGrid } from "lucide-react";
import { TemplateGallery } from "./dialogs/TemplateGallery";
import { useResumeV2Store } from "../store";
import type { TemplateId } from "../schema/templates";

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
  const setData = useResumeV2Store((s) => s.setData);
  const data = useResumeV2Store((s) => s.data);
  const currentTemplate = (data?.metadata?.template ?? "pikachu") as TemplateId;

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
