import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AnalysisHistory } from "../AnalysisHistory";
import type { ResumeAnalysis } from "../types";

function analysis(overrides: Partial<ResumeAnalysis> = {}): ResumeAnalysis {
  return {
    id: "a1",
    resume_id: "r1",
    resume_version: 3,
    mode: "job_fit",
    status: "complete",
    is_stale: false,
    stale_reasons: [],
    overall_score: 70,
    confidence_score: 0.8,
    confidence_band: "high",
    confidence_reasons: [],
    job_context: null,
    dimensions: [],
    gaps: [],
    hard_blockers: [],
    disclaimer: "不是 ATS 分数。",
    created_at: "2026-07-11T00:00:00Z",
    ...overrides,
  };
}

describe("AnalysisHistory", () => {
  it("shows stale banner and refresh action", () => {
    const onRefresh = vi.fn();
    render(
      <AnalysisHistory
        analyses={[analysis({ is_stale: true, stale_reasons: ["resume_changed"] })]}
        currentAnalysisId="a1"
        onRefresh={onRefresh}
      />,
    );

    expect(screen.getByRole("alert")).toHaveTextContent("基于旧版本");
    fireEvent.click(screen.getByRole("button", { name: "基于最新版本重新分析" }));
    expect(onRefresh).toHaveBeenCalledOnce();
  });

  it("requests accessible before-after comparison", () => {
    const onCompare = vi.fn();
    render(
      <AnalysisHistory
        analyses={[analysis({ id: "old", resume_version: 2 }), analysis({ id: "new", resume_version: 3 })]}
        currentAnalysisId="new"
        onRefresh={vi.fn()}
        onCompare={onCompare}
      />,
    );

    fireEvent.click(screen.getByLabelText(/选择 v2 .* 作为比较基准/));
    fireEvent.click(screen.getByRole("button", { name: "比较所选历史与当前" }));
    expect(onCompare).toHaveBeenCalledWith("old", "new");
  });
});
