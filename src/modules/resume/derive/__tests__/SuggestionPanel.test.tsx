import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { SuggestionPanel } from "../SuggestionPanel";

const listSuggestionsMock = vi.fn();
const previewSuggestionMock = vi.fn();
const applySuggestionMock = vi.fn();

vi.mock("../api", () => ({
  listSuggestions: (...args: unknown[]) => listSuggestionsMock(...args),
  previewSuggestion: (...args: unknown[]) => previewSuggestionMock(...args),
  applySuggestion: (...args: unknown[]) => applySuggestionMock(...args),
}));

vi.mock("@/modules/resume/v2/store", () => ({
  useResumeV2Store: (selector: (s: { version: number }) => unknown) =>
    selector({ version: 2 }),
}));

const directSuggestion = {
  id: "sug-1",
  priority: "high",
  type: "bullet_trim",
  problem: "项目描述过长，建议压缩",
  apply_mode: "direct",
  status: "pending",
};

describe("SuggestionPanel", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("runs preview then apply for direct suggestions", async () => {
    listSuggestionsMock.mockResolvedValue({ suggestions: [directSuggestion] });
    previewSuggestionMock.mockResolvedValue({
      suggestion_id: "sug-1",
      apply_mode: "direct",
      preview_data: {},
      diff_summary: "将删除 2 条次要 bullet",
      preview_token: "token-abc",
    });
    applySuggestionMock.mockResolvedValue({ ok: true });

    render(<SuggestionPanel resumeId="derived-1" />);

    await waitFor(() => {
      expect(screen.getByTestId("suggestion-panel")).toBeInTheDocument();
    });
    expect(screen.getByText("项目描述过长，建议压缩")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "预览" }));

    await waitFor(() => {
      expect(previewSuggestionMock).toHaveBeenCalledWith("derived-1", {
        suggestion_id: "sug-1",
        client_version: 2,
      });
    });
    expect(screen.getByText("将删除 2 条次要 bullet")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "确认采纳" }));

    await waitFor(() => {
      expect(applySuggestionMock).toHaveBeenCalledWith("derived-1", {
        suggestion_id: "sug-1",
        client_version: 2,
        preview_token: "token-abc",
      });
    });
    expect(listSuggestionsMock).toHaveBeenCalledTimes(2);
  });

  it("shows empty state when no suggestions", async () => {
    listSuggestionsMock.mockResolvedValue({ suggestions: [] });

    render(<SuggestionPanel resumeId="derived-1" />);

    await waitFor(() => {
      expect(screen.getByText("暂无建议")).toBeInTheDocument();
    });
  });
});
