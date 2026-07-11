/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, act } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { DeriveProgress } from "../DeriveProgress";

vi.mock("../api", () => ({
  getDeriveRun: vi.fn(),
}));

vi.mock("@/hooks/queries/useAITasks", () => ({
  useAITask: () => ({ data: undefined, refetch: vi.fn() }),
}));

import { getDeriveRun } from "../api";

const mockedGet = vi.mocked(getDeriveRun);

function renderProgress(runId = "run-1") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[`/resume/derive/${runId}`]}>
        <Routes>
          <Route path="/resume/derive/:runId" element={<DeriveProgress />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("DeriveProgress canonical UX (REQ-061 T067)", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    mockedGet.mockReset();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("shows failed state with back link", async () => {
    mockedGet.mockResolvedValue({
      id: "run-1",
      status: "failed",
      phase: "done",
      progress_pct: 0,
      derived_resume_id: null,
      target_page_count: 1,
      error_code: "ENQUEUE_FAILED",
      error_message: "派生后台暂不可用",
      artifacts: {},
      canonical_status: "failed",
      available_actions: ["system_failure_retry"],
      task_id: "task-derive-1",
      milestones: [{ code: "draft", status: "failed" }],
    });

    renderProgress();
    await act(async () => {
      await Promise.resolve();
    });

    expect(screen.getByTestId("derive-progress-failed")).toBeInTheDocument();
    expect(screen.getByText(/ENQUEUE_FAILED/)).toBeInTheDocument();
    expect(screen.getByTestId("derive-task-link")).toBeInTheDocument();
    expect(screen.getByTestId("derive-milestones")).toBeInTheDocument();
  });

  it("does not show client-timeout banner while still running", async () => {
    mockedGet.mockResolvedValue({
      id: "run-1",
      status: "running",
      phase: "parse_jd",
      progress_pct: 10,
      derived_resume_id: null,
      target_page_count: 1,
      error_code: null,
      error_message: null,
      artifacts: {},
      canonical_status: "running",
      milestones: [
        { code: "draft", status: "delivered" },
        { code: "job_analysis", status: "running" },
        { code: "suggestions", status: "pending" },
      ],
    });

    renderProgress();
    await act(async () => {
      await Promise.resolve();
    });

    await act(async () => {
      vi.advanceTimersByTime(60_000);
    });

    expect(screen.queryByTestId("derive-progress-timeout")).not.toBeInTheDocument();
    expect(screen.getByTestId("derive-milestones")).toBeInTheDocument();
  });

  it("shows needs_guidance testid", async () => {
    mockedGet.mockResolvedValue({
      id: "run-1",
      status: "needs_guidance",
      phase: "calibrate",
      progress_pct: 90,
      derived_resume_id: null,
      target_page_count: 1,
      error_code: null,
      error_message: null,
      artifacts: {},
    });

    renderProgress();
    await act(async () => {
      await Promise.resolve();
    });

    expect(screen.getByTestId("derive-guidance")).toBeInTheDocument();
  });
});
