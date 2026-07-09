import {
  DEFAULT_LINE_HEIGHT,
  LINE_HEIGHT_PRESETS,
  type LineHeightPreset,
  type SmartOnePageStatus,
} from "@/modules/resume/renderer/types";

export interface SmartOnePageInput {
  pageCountAt: (lineHeight: LineHeightPreset) => number;
  preferredLineHeight?: LineHeightPreset;
}

export interface SmartOnePageResult {
  status: Exclude<SmartOnePageStatus, "idle">;
  selectedLineHeight: LineHeightPreset | null;
  pageCount: number;
  message: string | null;
}

export function computeSmartOnePage({
  pageCountAt,
  preferredLineHeight = 20,
}: SmartOnePageInput): SmartOnePageResult {
  const preferredCount = pageCountAt(preferredLineHeight);
  if (preferredCount <= 1) {
    return {
      status: "already-fit",
      selectedLineHeight: preferredLineHeight,
      pageCount: preferredCount,
      message: null,
    };
  }

  const candidates = [...LINE_HEIGHT_PRESETS]
    .filter((lineHeight) => lineHeight <= preferredLineHeight)
    .sort((a, b) => b - a);
  for (const lineHeight of candidates) {
    const pageCount = pageCountAt(lineHeight);
    if (pageCount <= 1) {
      return {
        status: "fit",
        selectedLineHeight: lineHeight,
        pageCount,
        message: null,
      };
    }
  }

  return {
    status: "infeasible",
    selectedLineHeight: null,
    pageCount: Math.max(1, pageCountAt(DEFAULT_LINE_HEIGHT)),
    message: "当前内容无法压缩到一页，已保留全部内容。",
  };
}
