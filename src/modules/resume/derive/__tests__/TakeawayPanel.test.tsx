import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { TakeawayPanel } from "../TakeawayPanel";

const getDeriveRationaleMock = vi.fn();

vi.mock("../api", () => ({
  getDeriveRationale: (...args: unknown[]) => getDeriveRationaleMock(...args),
}));

describe("TakeawayPanel", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("renders takeaway notes from derive rationale", async () => {
    getDeriveRationaleMock.mockResolvedValue({
      takeaway_notes: ["优先保留 RAG 项目经历", "弱化与岗位无关的社团活动"],
      unused_materials: [{ id: "club-1" }],
      selection_plan: {},
      jd_parse: {},
      supplement_questions: [],
      pending_claims: [],
    });

    render(<TakeawayPanel resumeId="derived-1" />);

    await waitFor(() => {
      expect(screen.getByTestId("takeaway-panel")).toBeInTheDocument();
    });
    expect(screen.getByText("优先保留 RAG 项目经历")).toBeInTheDocument();
    expect(screen.getByText("弱化与岗位无关的社团活动")).toBeInTheDocument();
    expect(screen.getByText(/未采用素材 1 项/)).toBeInTheDocument();
  });

  it("shows empty placeholder when no notes", async () => {
    getDeriveRationaleMock.mockResolvedValue({
      takeaway_notes: [],
      unused_materials: [],
      selection_plan: {},
      jd_parse: {},
      supplement_questions: [],
      pending_claims: [],
    });

    render(<TakeawayPanel resumeId="derived-1" />);

    await waitFor(() => {
      expect(screen.getByText("暂无取舍说明")).toBeInTheDocument();
    });
  });
});
