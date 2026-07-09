import { describe, expect, it } from "vitest";
import { DEFAULT_LINE_HEIGHT, LINE_HEIGHT_PRESETS, coerceLineHeightPreset, getEffectiveLineHeight } from "../line-height";

describe("line-height presets", () => {
  it("exposes integer presets from 12 through 25", () => {
    expect(LINE_HEIGHT_PRESETS).toEqual([12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25]);
    expect(DEFAULT_LINE_HEIGHT).toBe(19);
  });

  it("coerces invalid values and derives smart effective line-height", () => {
    expect(coerceLineHeightPreset(11)).toBe(19);
    expect(coerceLineHeightPreset(12)).toBe(12);
    expect(coerceLineHeightPreset(25)).toBe(25);
    expect(coerceLineHeightPreset(26)).toBe(19);
    expect(getEffectiveLineHeight({ manualLineHeight: 12, smartOnePageEnabled: true, smartLineHeight: 20 })).toBe(20);
    expect(getEffectiveLineHeight({ manualLineHeight: 12, smartOnePageEnabled: false, smartLineHeight: 20 })).toBe(12);
  });
});
