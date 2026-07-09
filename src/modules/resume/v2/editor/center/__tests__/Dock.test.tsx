// T097 — Vitest: Dock (US10 / FR-067).
//
// Smoke test for the bottom-center dock:
// - Renders 8 icon buttons
// - Each button has a tooltip (title attribute + Tooltip wrapper)
// - Zoom in/out callbacks fire with 0.25 steps
// - Hover animation classes (hover:-translate-y-px + hover:scale-[1.04]) present
// - Open AI agent click → calls onOpenAgent (or navigates via mocked useNavigate)
// - Copy URL click → writes to navigator.clipboard.writeText
// - Download JSON click → triggers downloadBlob

import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, fireEvent, cleanup, act } from "@testing-library/react";
import React from "react";
import { defaultResumeDataV2 } from "../../../schema/defaults";
import type { ResumeDataV2 } from "../../../schema/data";
import { Dock } from "../Dock";

const REQUIRED_TESTIDS = [
  "dock-zoom-in",
  "dock-zoom-out",
  "dock-center",
  "dock-stacking",
  "dock-ai-agent",
  "dock-copy-url",
  "dock-download-json",
  "dock-download-pdf",
];

const HOVER_TW_CLASSES = ["hover:-translate-y-px", "hover:scale-[1.04]"];

const mockNavigate = vi.fn();
const mockWriteText = vi.fn().mockResolvedValue(undefined);

vi.mock("react-router-dom", () => ({
  useNavigate: () => mockNavigate,
}));

vi.mock("@/stores/useAuthStore", () => ({
  useAuthStore: (sel: (s: { user: { id: string; display_name: string | null } | null }) => unknown) =>
    sel({ user: { id: "user-1", display_name: "Ada" } }),
}));

vi.mock("@/modules/resume/converter/markdown-export", () => ({
  downloadBlob: vi.fn(),
}));

vi.mock("@/components/ui/Tooltip", () => ({
  Tooltip: ({ children, content }: { children: React.ReactNode; content: React.ReactNode }) => (
    <span data-testid="tooltip" data-tooltip={String(content)}>
      {children}
    </span>
  ),
}));

vi.mock("@/api/token-storage", () => ({
  getAccessToken: () => null,
}));

vi.mock("@/api/device-fingerprint", () => ({
  deviceFingerprint: () => "fp-test",
}));

vi.mock("@/api/env", () => ({
  newRequestId: () => "req-test",
  env: { API_BASE_URL: "" },
}));

// import after mocks so module-level wiring is bound
import { downloadBlob } from "@/modules/resume/converter/markdown-export";

beforeEach(() => {
  mockNavigate.mockReset();
  mockWriteText.mockReset();
  mockWriteText.mockResolvedValue(undefined);
  (downloadBlob as unknown as { mockReset?: () => void }).mockReset?.();
  ((downloadBlob as unknown) as ReturnType<typeof vi.fn>).mockReset?.();
  Object.defineProperty(window.navigator, "clipboard", {
    configurable: true,
    value: { writeText: mockWriteText },
  });
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

const baseData: ResumeDataV2 = defaultResumeDataV2;

function renderDock(overrides: Partial<React.ComponentProps<typeof Dock>> = {}) {
  const onZoomChange = vi.fn();
  const onStackingChange = vi.fn();
  const onCopiedUrl = vi.fn();
  const onOpenAgent = vi.fn();
  const onPdfDownloaded = vi.fn();
  const props: React.ComponentProps<typeof Dock> = {
    data: baseData,
    resumeId: "resume-1",
    slug: "ada-lovelace",
    zoom: 1,
    stacking: "vertical",
    onZoomChange,
    onStackingChange,
    onCopiedUrl,
    onOpenAgent,
    onPdfDownloaded,
    ...overrides,
  };
  const utils = render(<Dock {...props} />);
  return { ...utils, onZoomChange, onStackingChange, onCopiedUrl, onOpenAgent, onPdfDownloaded };
}

describe("Dock (US10 T097)", () => {
  it("renders 8 buttons with the expected test ids", () => {
    renderDock();
    for (const id of REQUIRED_TESTIDS) {
      expect(screen.getByTestId(id)).toBeTruthy();
    }
    // Ensure no extra/missing — count by testid prefix.
    const buttons = screen.getAllByTestId(/^dock-/);
    expect(buttons).toHaveLength(8);
  });

  it("renders tooltips for every button (top-positioned via shared Tooltip)", () => {
    renderDock();
    const tooltips = screen.getAllByTestId("tooltip");
    expect(tooltips.length).toBeGreaterThanOrEqual(8);
  });

  it("applies hover animation classes (y:-1, scale:1.04) on every button", () => {
    renderDock();
    for (const id of REQUIRED_TESTIDS) {
      const btn = screen.getByTestId(id);
      for (const cls of HOVER_TW_CLASSES) {
        expect(btn.className).toContain(cls);
      }
    }
  });

  it("zoom in / out fire onZoomChange with 0.25 steps (clamped 0.5..5)", () => {
    const { onZoomChange } = renderDock({ zoom: 1 });
    act(() => {
      fireEvent.click(screen.getByTestId("dock-zoom-in"));
    });
    // Each click computes from the current `zoom` prop and emits next
    // value to the parent — the parent re-renders with the new value
    // and the next click again adds 0.25 from the new baseline.
    expect(onZoomChange).toHaveBeenLastCalledWith(1.25);
    expect(onZoomChange).toHaveBeenCalledTimes(1);

    act(() => {
      fireEvent.click(screen.getByTestId("dock-zoom-out"));
    });
    expect(onZoomChange).toHaveBeenLastCalledWith(0.75);
    expect(onZoomChange).toHaveBeenCalledTimes(2);
  });

  it("zoom in is clamped to 5x", () => {
    const { onZoomChange } = renderDock({ zoom: 5 });
    act(() => {
      fireEvent.click(screen.getByTestId("dock-zoom-in"));
    });
    expect(onZoomChange).toHaveBeenLastCalledWith(5);
  });

  it("zoom out is clamped to 0.5x", () => {
    const { onZoomChange } = renderDock({ zoom: 0.5 });
    act(() => {
      fireEvent.click(screen.getByTestId("dock-zoom-out"));
    });
    expect(onZoomChange).toHaveBeenLastCalledWith(0.5);
  });

  it("center view resets zoom to 1", () => {
    const { onZoomChange } = renderDock({ zoom: 2.5 });
    act(() => {
      fireEvent.click(screen.getByTestId("dock-center"));
    });
    expect(onZoomChange).toHaveBeenLastCalledWith(1);
  });

  it("stacking toggle flips vertical <-> horizontal", () => {
    const { onStackingChange } = renderDock({ stacking: "vertical" });
    act(() => {
      fireEvent.click(screen.getByTestId("dock-stacking"));
    });
    expect(onStackingChange).toHaveBeenLastCalledWith("horizontal");
  });

  it("stacking toggle flips horizontal -> vertical", () => {
    const { onStackingChange } = renderDock({ stacking: "horizontal" });
    act(() => {
      fireEvent.click(screen.getByTestId("dock-stacking"));
    });
    expect(onStackingChange).toHaveBeenLastCalledWith("vertical");
  });

  it("AI agent click calls onOpenAgent when provided", () => {
    const { onOpenAgent } = renderDock();
    fireEvent.click(screen.getByTestId("dock-ai-agent"));
    expect(onOpenAgent).toHaveBeenCalledTimes(1);
  });

  it("copy URL writes to clipboard and reports via onCopiedUrl", async () => {
    const { onCopiedUrl } = renderDock();
    fireEvent.click(screen.getByTestId("dock-copy-url"));
    // allow microtask
    await Promise.resolve();
    expect(mockWriteText).toHaveBeenCalledTimes(1);
    expect(mockWriteText.mock.calls[0][0]).toMatch(/\/r\/.+\/ada-lovelace$/);
    expect(onCopiedUrl).toHaveBeenCalledTimes(1);
  });

  it("download JSON serializes ResumeDataV2 and triggers downloadBlob", () => {
    const db = vi.mocked(downloadBlob);
    renderDock();
    fireEvent.click(screen.getByTestId("dock-download-json"));
    expect(db).toHaveBeenCalledTimes(1);
    const [blob, filename] = db.mock.calls[0];
    expect(filename).toBe("ada-lovelace.json");
    expect(blob).toBeInstanceOf(Blob);
    expect(blob.type).toBe("application/json;charset=utf-8");
  });
});
