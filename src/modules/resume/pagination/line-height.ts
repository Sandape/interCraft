import {
  DEFAULT_LINE_HEIGHT,
  LINE_HEIGHT_PRESETS,
  type LineHeightPreset,
} from "@/modules/resume/renderer/types";

export { DEFAULT_LINE_HEIGHT, LINE_HEIGHT_PRESETS };
export type { LineHeightPreset };

export interface EffectiveLineHeightInput {
  manualLineHeight: number;
  smartOnePageEnabled: boolean;
  smartLineHeight: number | null;
}

export function coerceLineHeightPreset(value: number, fallback: LineHeightPreset = DEFAULT_LINE_HEIGHT): LineHeightPreset {
  return (LINE_HEIGHT_PRESETS as readonly number[]).includes(value)
    ? (value as LineHeightPreset)
    : fallback;
}

export function getEffectiveLineHeight(input: EffectiveLineHeightInput): LineHeightPreset {
  if (input.smartOnePageEnabled && input.smartLineHeight !== null) {
    return coerceLineHeightPreset(input.smartLineHeight);
  }
  return coerceLineHeightPreset(input.manualLineHeight);
}
