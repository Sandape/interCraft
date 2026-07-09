// T099 — Bottom-center floating dock (US10 / FR-067).
//
// Fixed `bottom-4 center`, `rounded-full`, white background with shadow.
// 8 icon buttons (lucide-react):
//   1. ZoomIn    2. ZoomOut    3. Crosshair (Center view)
//   4. Rows      5. Columns    6. Sparkles (Open AI agent)
//   7. Copy      8. FileJson   9. FileDown
// (Row+Col is one toggle button per the spec's 8-button cap; Total
//  unique on-screen affordances = 8.)
//
// Each button has a Tooltip (top-positioned via the shared Tooltip
// primitive from src/components/ui/) and a hover animation
// (y: -1, scale: 1.04 per FR-067 + spec US10).

import { useState, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import {
  ZoomIn,
  ZoomOut,
  Crosshair,
  Rows,
  Columns,
  Sparkles,
  Copy as CopyIcon,
  FileJson,
  FileDown,
} from "lucide-react";

import { Tooltip } from "@/components/ui/Tooltip";
import { downloadBlob } from "@/modules/resume/converter/markdown-export";
import { useAuthStore } from "@/stores/useAuthStore";
import { fireToast } from "./toast";
import { jsonToHtml } from "../../renderer/jsonToHtml";
import type { ResumeDataV2 } from "../../schema/data";

const ZOOM_MIN = 0.5;
const ZOOM_MAX = 5;
const ZOOM_STEP = 0.25;

function clampZoom(z: number): number {
  return Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, +z.toFixed(2)));
}

function getShareUrl(username: string | undefined, slug: string): string {
  const origin = typeof window !== "undefined" ? window.location.origin : "";
  const user = username || "user";
  return `${origin}/r/${user}/${slug}`;
}

function getDateStamp(): string {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

// `fireToast` is imported from `./toast` above (shared with the store).

export interface DockProps {
  data: ResumeDataV2;
  resumeId: string;
  slug: string;
  /** Current zoom (0.5..5). */
  zoom: number;
  /** Current stacking direction. */
  stacking: "horizontal" | "vertical";
  onZoomChange: (next: number) => void;
  onStackingChange: (next: "horizontal" | "vertical") => void;
  /** Ref to the scrollable preview stage — used by the "center view" button. */
  scrollRef?: React.RefObject<HTMLElement>;
  /** Optional override for the share URL username (test hook). */
  username?: string;
  /** Called when the user clicks the AI agent icon (T103). Defaults to navigate. */
  onOpenAgent?: () => void;
  /** Called when the user copies the public share URL (T104). */
  onCopiedUrl?: (url: string) => void;
  /** Called after a successful PDF download (T106). */
  onPdfDownloaded?: (filename: string) => void;
}

export function Dock({
  data,
  resumeId,
  slug,
  zoom,
  stacking,
  onZoomChange,
  onStackingChange,
  scrollRef,
  username,
  onOpenAgent,
  onCopiedUrl,
  onPdfDownloaded,
}: DockProps): ReactNode {
  const navigate = useNavigate();
  const authUser = useAuthStore((s) => s.user);
  const resolvedUsername = username ?? authUser?.display_name ?? authUser?.id;
  const [pdfBusy, setPdfBusy] = useState(false);

  const handleZoomIn = () => onZoomChange(clampZoom(zoom + ZOOM_STEP));
  const handleZoomOut = () => onZoomChange(clampZoom(zoom - ZOOM_STEP));
  const handleCenter = () => {
    onZoomChange(1);
    if (scrollRef?.current) {
      scrollRef.current.scrollTo({ top: 0, behavior: "smooth" });
    }
  };
  const handleStacking = () =>
    onStackingChange(stacking === "vertical" ? "horizontal" : "vertical");
  const handleOpenAgent = () => {
    if (onOpenAgent) {
      onOpenAgent();
      return;
    }
    navigate(`/agent/new?resumeId=${encodeURIComponent(resumeId)}`);
  };
  const handleCopyUrl = async () => {
    const url = getShareUrl(resolvedUsername, slug);
    try {
      if (navigator?.clipboard?.writeText) {
        await navigator.clipboard.writeText(url);
      } else {
        // Fallback for environments without clipboard API
        const ta = document.createElement("textarea");
        ta.value = url;
        ta.setAttribute("readonly", "");
        ta.style.position = "absolute";
        ta.style.left = "-9999px";
        document.body.appendChild(ta);
        ta.select();
        document.execCommand("copy");
        document.body.removeChild(ta);
      }
      fireToast("Copied");
      onCopiedUrl?.(url);
    } catch (err) {
      fireToast("Copy failed");
      // eslint-disable-next-line no-console
      console.error("[dock] clipboard.writeText failed", err);
    }
  };
  const handleDownloadJson = () => {
    const json = JSON.stringify(data, null, 2);
    const blob = new Blob([json], { type: "application/json;charset=utf-8" });
    const safeSlug = (slug || "resume").replace(/[<>:"/\\|?*]/g, "_");
    downloadBlob(blob, `${safeSlug}.json`);
  };
  const handleDownloadPdf = async () => {
    if (pdfBusy) return;
    setPdfBusy(true);
    try {
      const apiBase = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "";
      const access = (await import("@/api/token-storage")).getAccessToken?.() ?? null;
      const fingerprint = (await import("@/api/device-fingerprint")).deviceFingerprint?.() ?? "";
      const newReqId = (await import("@/api/env")).newRequestId?.() ?? "";
      const headers: Record<string, string> = {
        "Content-Type": "application/json",
        Accept: "application/pdf",
        "X-Request-ID": newReqId,
        "X-Device-Fingerprint": fingerprint,
      };
      if (access) headers["Authorization"] = `Bearer ${access}`;
      // T123 — use the US15 renderer to produce a full HTML document
      // (CSS variables inlined, template component statically rendered
      // via the dispatcher). The 027 export gateway will then render
      // this HTML headlessly to PDF.
      const html = jsonToHtml(data);
      const body = JSON.stringify({
        html,
        format: "pdf",
        locale: data.metadata?.page?.locale ?? "zh",
      });
      const res = await fetch(`${apiBase}/api/v1/export/render`, {
        method: "POST",
        headers,
        body,
      });
      if (!res.ok) {
        throw new Error(`Export failed: ${res.status} ${res.statusText}`);
      }
      const blob = await res.blob();
      const safeSlug = (slug || "resume").replace(/[<>:"/\\|?*]/g, "_");
      const filename = `${safeSlug}-${getDateStamp()}.pdf`;
      downloadBlob(blob, filename);
      onPdfDownloaded?.(filename);
    } catch (err) {
      fireToast("PDF export failed");
      // eslint-disable-next-line no-console
      console.error("[dock] PDF export failed", err);
    } finally {
      setPdfBusy(false);
    }
  };

  return (
    <div
      className="flex items-center gap-1 rounded-full border border-surface-border bg-white px-2 py-1.5 shadow-notion"
      data-testid="dock"
      role="toolbar"
      aria-label="Resume dock"
    >
      <DockButton
        testid="dock-zoom-in"
        label="Zoom in"
        onClick={handleZoomIn}
        icon={<ZoomIn className="h-4 w-4" />}
      />
      <DockButton
        testid="dock-zoom-out"
        label="Zoom out"
        onClick={handleZoomOut}
        icon={<ZoomOut className="h-4 w-4" />}
      />
      <DockButton
        testid="dock-center"
        label="Center view"
        onClick={handleCenter}
        icon={<Crosshair className="h-4 w-4" />}
      />
      <DockDivider />
      <DockButton
        testid="dock-stacking"
        label={stacking === "vertical" ? "Stack horizontally" : "Stack vertically"}
        onClick={handleStacking}
        icon={
          stacking === "vertical" ? (
            <Rows className="h-4 w-4" />
          ) : (
            <Columns className="h-4 w-4" />
          )
        }
      />
      <DockButton
        testid="dock-ai-agent"
        label="Open AI agent"
        onClick={handleOpenAgent}
        icon={<Sparkles className="h-4 w-4" />}
      />
      <DockButton
        testid="dock-copy-url"
        label="Copy public URL"
        onClick={handleCopyUrl}
        icon={<CopyIcon className="h-4 w-4" />}
      />
      <DockDivider />
      <DockButton
        testid="dock-download-json"
        label="Download JSON"
        onClick={handleDownloadJson}
        icon={<FileJson className="h-4 w-4" />}
      />
      <DockButton
        testid="dock-download-pdf"
        label="Download PDF"
        onClick={handleDownloadPdf}
        icon={<FileDown className="h-4 w-4" />}
        busy={pdfBusy}
      />
    </div>
  );
}

interface DockButtonProps {
  testid: string;
  label: string;
  icon: ReactNode;
  onClick: () => void;
  busy?: boolean;
}

function DockButton({ testid, label, icon, onClick, busy }: DockButtonProps) {
  return (
    <Tooltip content={label}>
      <button
        type="button"
        data-testid={testid}
        aria-label={label}
        title={label}
        disabled={busy}
        onClick={onClick}
        className={[
          "inline-flex h-8 w-8 items-center justify-center rounded-full text-ink-2",
          "transition-transform duration-150 ease-out",
          "hover:-translate-y-px hover:scale-[1.04] hover:bg-surface-muted hover:text-ink-1",
          "active:scale-95",
          "disabled:cursor-wait disabled:opacity-60",
          "focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-300",
        ].join(" ")}
      >
        {icon}
      </button>
    </Tooltip>
  );
}

function DockDivider() {
  return <span aria-hidden className="mx-1 h-5 w-px bg-surface-border" />;
}
