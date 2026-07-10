import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { PageControlPanel } from "../PageControlPanel";

const getExportGateMock = vi.fn();

vi.mock("../api", () => ({
  getExportGate: (...args: unknown[]) => getExportGateMock(...args),
  resumeGuidance: vi.fn(),
}));

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>(
    "react-router-dom",
  );
  return {
    ...actual,
    useNavigate: () => vi.fn(),
  };
});

describe("PageControlPanel", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("shows blockers when export is not allowed", async () => {
    getExportGateMock.mockResolvedValue({
      exportable: false,
      actual_page_count: 2,
      target_page_count: 1,
      blockers: ["page_count_mismatch"],
    });

    render(<PageControlPanel resumeId="resume-1" />);

    await waitFor(() => {
      expect(screen.getByTestId("page-control-panel")).toBeInTheDocument();
    });
    expect(screen.getByText("未达标，禁止最终导出")).toBeInTheDocument();
    expect(screen.getByText("page_count_mismatch")).toBeInTheDocument();
    expect(screen.queryByText(/可导出/)).not.toBeInTheDocument();
  });

  it("shows exportable message when page gate passes", async () => {
    getExportGateMock.mockResolvedValue({
      exportable: true,
      actual_page_count: 1,
      target_page_count: 1,
      blockers: [],
    });

    render(<PageControlPanel resumeId="resume-1" />);

    await waitFor(() => {
      expect(screen.getByText("页数达标，可导出 PDF")).toBeInTheDocument();
    });
    expect(screen.queryByText("未达标，禁止最终导出")).not.toBeInTheDocument();
  });
});
