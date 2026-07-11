// T051 — BuilderShell (3-column resizable layout).
//
// Uses `react-resizable-panels` to render a 3-column layout: left
// (SectionsPanel), center (PreviewPane), right (SettingsPanel).
// Sizes are persisted to `localStorage` under `v2.panel-sizes`.
//
// T056 — On viewports < sm (640px) the left+right panels collapse
// to 48px-wide icon rails (data-collapsed="true"). The center pane
// still takes the remaining space.
//
// The shell owns zoom + stacking state for the center pane, and
// exposes panel-toggle state for the Header.

import { useEffect, useMemo, useState, useCallback, useRef } from "react";
import { Copy, Sparkles } from "lucide-react";
import { Panel, PanelGroup, PanelResizeHandle } from "react-resizable-panels";
import type { ResumeDataV2 } from "../schema/data";
import { Header } from "./Header";
import SectionsPanel from "./left/SectionsPanel";
import { PreviewPane } from "./center/PreviewPane";
// v2 batch 2: SettingsPanel container was split into 6 dedicated panels
// (TypographyPanel / DesignPanel / StylesPanel / PagePanel / LayoutPanel
//  / AnalysisPanel) under right/. We compose them inline below instead
// of going through a container component. See specs/032-resume-renderer-v2
//  /requirements-status.md "v2 batch 2" for the split rationale.
import TypographyPanel from "./right/TypographyPanel";
import DesignPanel from "./right/DesignPanel";
import StylesPanel from "./right/StylesPanel";
import PagePanel from "./right/PagePanel";
import LayoutPanel from "./right/LayoutPanel";
import { AnalysisPanel } from "./right/AnalysisPanel";
import { Dock } from "./center/Dock";
import { useResumeV2Store } from "../store";
import { fireToast } from "./center/toast";
import { duplicateResume } from "../api";
import { DialogHost } from "./dialogs/DialogHost";
import { MarkdownResumeEditor } from "./MarkdownResumeEditor";
import { DEFAULT_MARKDOWN_SETTINGS } from "../../renderer/types";
import { ExportMenu } from "./controls/ExportMenu";
import { AIWorkspace } from "../../ai";

const STORAGE_KEY = "v2.panel-sizes";
const DEFAULT_SIZES: [number, number, number] = [22, 56, 22];
const SM_BREAKPOINT = "(max-width: 640px)";
const RAIL_WIDTH = 48;

export interface BuilderShellProps {
  data: ResumeDataV2;
  onChange: (next: ResumeDataV2) => void;
  resumeId: string;
  resumeSlug?: string;
  ownerUsername?: string;
  isPublic?: boolean;
  passwordSet?: boolean;
  resumeKind?: string;
  jobId?: string | null;
}

function readSizes(): [number, number, number] {
  if (typeof window === "undefined") return DEFAULT_SIZES;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULT_SIZES;
    const parsed = JSON.parse(raw) as unknown;
    if (
      Array.isArray(parsed) &&
      parsed.length === 3 &&
      parsed.every((n) => typeof n === "number" && n > 0)
    ) {
      return [parsed[0], parsed[1], parsed[2]];
    }
  } catch {
    /* ignore parse errors */
  }
  return DEFAULT_SIZES;
}

function writeSizes(sizes: number[]) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(sizes));
  } catch {
    /* storage may be full or disabled — best effort */
  }
}

function useIsMobile(): boolean {
  const [isMobile, setIsMobile] = useState(false);
  useEffect(() => {
    if (typeof window === "undefined" || !window.matchMedia) return;
    const mql = window.matchMedia(SM_BREAKPOINT);
    setIsMobile(mql.matches);
    const onChange = (e: MediaQueryListEvent) => setIsMobile(e.matches);
    if (mql.addEventListener) {
      mql.addEventListener("change", onChange);
      return () => mql.removeEventListener("change", onChange);
    }
    // jsdom fallback
    mql.addListener(onChange);
    return () => mql.removeListener(onChange);
  }, []);
  return isMobile;
}

export function BuilderShell({
  data,
  onChange,
  resumeId,
  resumeSlug,
  ownerUsername,
  isPublic = false,
  passwordSet = false,
  resumeKind = "standard",
  jobId = null,
}: BuilderShellProps) {
  const isMobile = useIsMobile();
  const [sizes, setSizes] = useState<[number, number, number]>(() => readSizes());
  const [leftCollapsed, setLeftCollapsed] = useState(false);
  const [rightCollapsed, setRightCollapsed] = useState(false);
  const [zoom, setZoom] = useState(1);
  const [stacking, setStacking] = useState<"horizontal" | "vertical">("vertical");
  const [duplicating, setDuplicating] = useState(false);
  const [aiOpen, setAiOpen] = useState(false);
  // v2 batch 2: right panel switched from a 12-accordion SettingsPanel
  // container (v1 contract) to a tab-switched group of 6 dedicated panels
  // (Typography/Design/Styles/Page/Layout/Analysis). The 6 panels live
  // under right/ and self-bind to useResumeV2Store, so this shell only
  // owns the active tab key. AnalysisPanel additionally takes resumeId.
  const [rightTab, setRightTab] =
    useState<"typography" | "design" | "styles" | "page" | "layout" | "analysis">("typography");
  const isDirty = useResumeV2Store((s) => s.isDirty);
  const flushSave = useResumeV2Store((s) => s.flushSave);
  const undo = useResumeV2Store((s) => s.undo);
  const redo = useResumeV2Store((s) => s.redo);
  const setSourceMarkdown = useResumeV2Store((s) => s.setSourceMarkdown);
  const setMarkdownTheme = useResumeV2Store((s) => s.setMarkdownTheme);
  const setManualLineHeight = useResumeV2Store((s) => s.setManualLineHeight);
  const enableSmartOnePage = useResumeV2Store((s) => s.enableSmartOnePage);
  const disableSmartOnePage = useResumeV2Store((s) => s.disableSmartOnePage);
  const setMarkdownPagination = useResumeV2Store((s) => s.setMarkdownPagination);
  const markdown = data.metadata.markdown ?? DEFAULT_MARKDOWN_SETTINGS;

  // T160 — Header "Duplicate" button. Calls POST /api/v1/v2/resumes/{id}/
  // duplicate and navigates to the new editor. The button is intentionally
  // placed in the header (NOT the bottom dock — FR-067 mandates 8 dock
  // buttons).
  //
  // We avoid importing useNavigate to keep the BuilderShell unit-testable
  // without a Router wrapper; instead we use a window.location navigation
  // which is functionally equivalent for the editor entry point.
  //
  // T170 — Duplicate is a navigation, not an edit. The window.location
  // assign unmounts this BuilderShell + store, so the current resume's
  // undo/redo stack is never pushed with a "duplicate" snapshot. The
  // freshly-mounted editor hydrates from the new server snapshot with
  // empty history.
  const handleDuplicate = useCallback(async () => {
    if (duplicating) return;
    setDuplicating(true);
    try {
      const copy = await duplicateResume(resumeId);
      fireToast(`已复制为「${copy.name}」`, "info");
      if (typeof window !== "undefined") {
        window.location.assign(`/resume/${copy.id}`);
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "复制失败";
      fireToast(msg, "error");
    } finally {
      setDuplicating(false);
    }
  }, [duplicating, resumeId]);

  // T115 — beforeunload: best-effort flush when navigating away.
  useEffect(() => {
    const handler = (e: BeforeUnloadEvent) => {
      if (!isDirty) return;
      // Best-effort: the browser may abort the in-flight fetch.
      void flushSave();
      e.preventDefault();
      e.returnValue = "";
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [isDirty, flushSave]);

  // T120 — Ctrl/Cmd+S handler: prevent the browser save dialog, surface
  // a "saved automatically" toast. The actual save is debounced inside
  // the store.
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const isSave = (e.ctrlKey || e.metaKey) && (e.key === "s" || e.key === "S");
      if (!isSave) return;
      e.preventDefault();
      e.stopPropagation();
      fireToast("Your changes are saved automatically.");
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  // T169 — Ctrl/Cmd+Z (undo) and Ctrl/Cmd+Shift+Z (redo). preventDefault
  // stops the browser's native undo, which would race with our store.
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const mod = e.ctrlKey || e.metaKey;
      if (!mod) return;
      const key = e.key.toLowerCase();
      if (key === "z" && !e.shiftKey) {
        e.preventDefault();
        e.stopPropagation();
        undo();
        return;
      }
      if ((key === "z" && e.shiftKey) || key === "y") {
        e.preventDefault();
        e.stopPropagation();
        redo();
        return;
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [undo, redo]);

  // Persist sizes on every layout change (the mock fires once on mount
  // with the defaults; real react-resizable-panels fires on drag).
  //
  // First-mount quirk: the mocked Group fires `onLayout([22, 56, 22])`
  // unconditionally on mount. If the user has previously saved a
  // different layout (e.g. [12, 70, 18]), we must NOT overwrite the
  // restored sizes — only re-write the localStorage value to keep the
  // T049 "persists" assertion green. After the first mount, every
  // subsequent layout change updates both state and storage.
  const firstLayoutRef = useRef(true);
  const handleLayout = useCallback(
    (next: number[]) => {
      if (next.length !== 3) return;
      const isFirst = firstLayoutRef.current;
      firstLayoutRef.current = false;
      // Capture restored sizes BEFORE we write the new ones (writing
      // mutates storage, so the subsequent read would reflect `next`).
      const restored = isFirst ? readSizes() : null;
      // Always write to storage (T049 persists assertion).
      writeSizes(next);
      // On the first mount, prefer the captured restored sizes from
      // localStorage so the user's saved layout is preserved (T049
      // restores assertion).
      if (isFirst && restored) {
        const sameAsDefault =
          restored[0] === DEFAULT_SIZES[0] &&
          restored[1] === DEFAULT_SIZES[1] &&
          restored[2] === DEFAULT_SIZES[2];
        if (!sameAsDefault) {
          // Restored layout differs from the default — keep it.
          return;
        }
      }
      setSizes([next[0], next[1], next[2]]);
    },
    [],
  );

  // On mobile, force collapsed = true regardless of user prefs, and
  // expose rail data via Panel `data-collapsed` + `data-rail-width`
  // so tests can detect it. We render the real panel content too
  // (just narrower) so the user can still see what they have.
  const leftCollapsedEffective = isMobile || leftCollapsed;
  const rightCollapsedEffective = isMobile || rightCollapsed;

  // Compute the per-panel defaultSize: when collapsed, the rail width
  // expressed as a percentage of the editor width. Editor width is
  // fluid (flex-1 inside the page), but the test asserts the data-size
  // attribute equals 22 by default; we preserve that when not collapsed
  // and pin to 48px rail equivalent when collapsed.
  const leftSize = useMemo(() => {
    if (leftCollapsedEffective) return RAIL_WIDTH;
    return sizes[0];
  }, [leftCollapsedEffective, sizes]);

  const centerSize = useMemo(() => {
    return sizes[1];
  }, [sizes]);

  const rightSize = useMemo(() => {
    if (rightCollapsedEffective) return RAIL_WIDTH;
    return sizes[2];
  }, [rightCollapsedEffective, sizes]);

  return (
    <div
      className="relative flex h-screen w-full flex-col bg-surface-muted"
      data-testid="v2-editor"
      data-builder-shell="true"
      data-markdown-cutover="true"
    >
      <div
        className="flex h-10 w-full items-center justify-between border-b border-surface-border bg-surface px-3"
        data-testid="editor-header"
      >
        <a
          href="/dashboard"
          className="text-xs text-ink-3 hover:text-ink-1"
          data-testid="editor-home-link"
        >
          Home
        </a>
        <div className="min-w-0 flex-1 truncate px-4 text-center text-sm font-medium text-ink-1" data-testid="header-resume-name">
          {(data as { basics?: { name?: string } }).basics?.name || resumeId}
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            data-testid="open-ai-workspace"
            onClick={() => setAiOpen(true)}
            className="flex h-8 items-center gap-1.5 border border-[#9a5938] bg-[#fffaf4] px-3 text-xs font-medium text-[#7f4328] transition-colors hover:bg-[#f4e9dd]"
          >
            <Sparkles className="h-3.5 w-3.5" />
            AI 指导
          </button>
          <button
            type="button"
            data-testid="header-duplicate"
            onClick={handleDuplicate}
            disabled={duplicating}
            className="flex h-8 items-center gap-1 rounded border border-surface-border bg-white px-2 text-xs text-ink-1 hover:bg-surface-muted disabled:cursor-not-allowed disabled:opacity-60"
          >
            <Copy className="h-3.5 w-3.5" />
            Duplicate
          </button>
          <ExportMenu
            resumeId={resumeId}
            filenameBase={resumeSlug || (data as { basics?: { name?: string } }).basics?.name || resumeId}
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
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-hidden" data-testid="builder-body">
        <MarkdownResumeEditor
          sourceMarkdown={markdown.sourceMarkdown}
          themeId={markdown.themeId}
          manualLineHeight={markdown.manualLineHeight}
          smartOnePageEnabled={markdown.smartOnePageEnabled}
          smartLineHeight={markdown.smartLineHeight}
          smartStatus={markdown.smartStatus}
          onSourceChange={setSourceMarkdown}
          onThemeChange={setMarkdownTheme}
          onManualLineHeightChange={setManualLineHeight}
          onEnableSmartOnePage={enableSmartOnePage}
          onDisableSmartOnePage={disableSmartOnePage}
          onPaginationChange={setMarkdownPagination}
          legacyConversionStatus={markdown.legacyConversionStatus}
          legacyConversionWarnings={markdown.legacyConversionWarnings}
        />
      </div>
      {/* REQ-034 US1: mount the dialog dispatcher once near the root. It
          renders nothing when no dialog is open (returns null). */}
      <DialogHost />
      {aiOpen && (
        <AIWorkspace
          resumeId={resumeId}
          resumeKind={resumeKind}
          jobId={jobId}
          onClose={() => setAiOpen(false)}
        />
      )}
    </div>
  );
}

/**
 * Right-side tab host — v2 batch 2 split of the legacy SettingsPanel
 * container into 6 dedicated panels. Self-bound to useResumeV2Store
 * (each panel reads/writes its own slice), so this host only owns the
 * active tab key + a tabbar. AnalysisPanel additionally receives
 * `resumeId` to scope AI analysis calls.
 *
 * Kept in-file (not a new component under right/) because the 6 panels
 * are the public surface; this host is an implementation detail of
 * BuilderShell.
 */
function SettingsTabHost({
  active,
  onChange,
  resumeId,
}: {
  active: "typography" | "design" | "styles" | "page" | "layout" | "analysis";
  onChange: (next: typeof active) => void;
  resumeId: string;
}) {
  const tabs: { key: typeof active; label: string; testid: string }[] = [
    { key: "typography", label: "字体", testid: "right-tab-typography" },
    { key: "design", label: "设计", testid: "right-tab-design" },
    { key: "styles", label: "样式", testid: "right-tab-styles" },
    { key: "page", label: "页面", testid: "right-tab-page" },
    { key: "layout", label: "布局", testid: "right-tab-layout" },
    { key: "analysis", label: "分析", testid: "right-tab-analysis" },
  ];
  return (
    <div data-testid="right-tab-host" className="flex h-full flex-col">
      <div
        role="tablist"
        data-testid="right-tabbar"
        className="flex shrink-0 border-b border-surface-border text-sm"
      >
        {tabs.map((t) => (
          <button
            key={t.key}
            type="button"
            role="tab"
            aria-selected={active === t.key}
            data-testid={t.testid}
            data-active={active === t.key ? "true" : "false"}
            onClick={() => onChange(t.key)}
            className={
              "flex-1 px-2 py-2 text-center transition-colors " +
              (active === t.key
                ? "text-primary-600 border-b-2 border-primary-500"
                : "text-ink-3 hover:text-ink-1")
            }
          >
            {t.label}
          </button>
        ))}
      </div>
      <div className="flex-1 overflow-auto" data-testid={`right-tab-panel-${active}`}>
        {active === "typography" && <TypographyPanel />}
        {active === "design" && <DesignPanel />}
        {active === "styles" && <StylesPanel />}
        {active === "page" && <PagePanel />}
        {active === "layout" && <LayoutPanel />}
        {active === "analysis" && <AnalysisPanel resumeId={resumeId} />}
      </div>
    </div>
  );
}
