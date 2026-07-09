import { describe, expect, it } from "vitest";
import { computeSmartOnePage } from "../smart-one-page";

describe("smart one-page", () => {
  it("returns already-fit for content that fits at the readable default", () => {
    const result = computeSmartOnePage({ pageCountAt: (lineHeight) => (lineHeight <= 20 ? 1 : 2), preferredLineHeight: 20 });
    expect(result.status).toBe("already-fit");
    expect(result.selectedLineHeight).toBe(20);
  });

  it("selects the roomiest fitting line-height when possible", () => {
    const result = computeSmartOnePage({ pageCountAt: (lineHeight) => (lineHeight <= 17 ? 1 : 2), preferredLineHeight: 20 });
    expect(result.status).toBe("fit");
    expect(result.selectedLineHeight).toBe(17);
  });

  it("reports infeasible without hiding content", () => {
    const result = computeSmartOnePage({ pageCountAt: () => 3, preferredLineHeight: 20 });
    expect(result.status).toBe("infeasible");
    expect(result.selectedLineHeight).toBeNull();
    expect(result.message).toContain("无法");
  });
});
