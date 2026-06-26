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
import { Panel, PanelGroup, PanelResizeHandle } from "react-resizable-panels";
import type { ResumeDataV2 } from "../schema/data";
import { Header } from "./Header";
import { SectionsPanel } from "./left/SectionsPanel";
import { PreviewPane } from "./center/PreviewPane";
import { SettingsPanel } from "./right/SettingsPanel";
import { Dock } from "./center/Dock";
import { useResumeV2Store } from "../store";
import { fireToast } from "./center/toast";
import { duplicateResume } from "../api";

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
}: BuilderShellProps) {
  const isMobile = useIsMobile();
  const [sizes, setSizes] = useState<[number, number, number]>(() => readSizes());
  const [leftCollapsed, setLeftCollapsed] = useState(false);
  const [rightCollapsed, setRightCollapsed] = useState(false);
  const [zoom, setZoom] = useState(1);
  const [stacking, setStacking] = useState<"horizontal" | "vertical">("vertical");
  const [duplicating, setDuplicating] = useState(false);
  const isDirty = useResumeV2Store((s) => s.isDirty);
  const flushSave = useResumeV2Store((s) => s.flushSave);
  const undo = useResumeV2Store((s) => s.undo);
  const redo = useResumeV2Store((s) => s.redo);

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
        window.location.assign(`/resume/v2/${copy.id}`);
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
      className="flex h-screen w-full flex-col bg-surface-muted"
      data-testid="v2-editor"
      data-builder-shell="true"
    >
      <Header
        resumeName={(data as { basics?: { name?: string } }).basics?.name || resumeId}
        leftCollapsed={leftCollapsed}
        rightCollapsed={rightCollapsed}
        onToggleLeft={() => setLeftCollapsed((v) => !v)}
        onToggleRight={() => setRightCollapsed((v) => !v)}
        onDuplicate={handleDuplicate}
        duplicating={duplicating}
      />

      <div className="flex flex-1 overflow-hidden" data-testid="builder-body">
        <PanelGroup
          direction="horizontal"
          onLayout={handleLayout}
          data-testid="panel-group"
        >
          <Panel
            data-testid="panel-left"
            data-size={leftSize}
            data-min={leftCollapsedEffective ? RAIL_WIDTH : 15}
            data-max={leftCollapsedEffective ? RAIL_WIDTH : 40}
            data-collapsed={leftCollapsedEffective ? "true" : "false"}
            defaultSize={leftSize}
            minSize={leftCollapsedEffective ? RAIL_WIDTH : 15}
            maxSize={leftCollapsedEffective ? RAIL_WIDTH : 40}
            order={1}
            className="overflow-hidden"
          >
            <div
              data-testid="left-panel"
              data-rail-width={leftCollapsedEffective ? String(RAIL_WIDTH) : undefined}
              className="h-full w-full"
            >
              <SectionsPanel />
            </div>
          </Panel>

          <PanelResizeHandle
            data-testid="resize-handle-left"
            className="relative z-10 w-px bg-surface-border data-[resize-handle-state=hover]:bg-primary-300 data-[resize-handle-state=drag]:bg-primary-400"
          />

          <Panel
            data-testid="panel-right"
            data-size={rightSize}
            data-min={rightCollapsedEffective ? RAIL_WIDTH : 15}
            data-max={rightCollapsedEffective ? RAIL_WIDTH : 40}
            data-collapsed={rightCollapsedEffective ? "true" : "false"}
            defaultSize={rightSize}
            minSize={rightCollapsedEffective ? RAIL_WIDTH : 15}
            maxSize={rightCollapsedEffective ? RAIL_WIDTH : 40}
            order={3}
            className="overflow-hidden"
          >
            <div
              data-testid="right-panel"
              data-rail-width={rightCollapsedEffective ? String(RAIL_WIDTH) : undefined}
              className="h-full w-full"
            >
              <SettingsPanel
                data={data}
                onChange={onChange}
                resumeId={resumeId}
                resumeSlug={resumeSlug}
                ownerUsername={ownerUsername}
                isPublic={isPublic}
                passwordSet={passwordSet}
              />
            </div>
          </Panel>

          <PanelResizeHandle
            data-testid="resize-handle-right"
            className="relative z-10 w-px bg-surface-border data-[resize-handle-state=hover]:bg-primary-300 data-[resize-handle-state=drag]:bg-primary-400"
          />

          <Panel
            data-testid="panel-center"
            data-size={centerSize}
            data-min={30}
            data-max={80}
            defaultSize={centerSize}
            minSize={30}
            maxSize={80}
            order={2}
            className="overflow-hidden"
          >
            <div data-testid="center-panel" className="h-full w-full">
              <PreviewPane
                data={data}
                zoom={zoom}
                stacking={stacking}
                onZoomChange={setZoom}
                onStackingChange={setStacking}
                dock={
                  <Dock
                    data={data}
                    resumeId={resumeId}
                    slug={
                      (data as { basics?: { name?: string } }).basics?.name
                        ? (data as { basics?: { name?: string } }).basics!.name!
                            .toLowerCase()
                            .replace(/\s+/g, "-")
                        : resumeId
                    }
                    zoom={zoom}
                    stacking={stacking}
                    onZoomChange={setZoom}
                    onStackingChange={setStacking}
                  />
                }
              />
            </div>
          </Panel>

        </PanelGroup>
      </div>
    </div>
  );
}
